const DEFAULT_API_BASE_URL = "http://localhost:8000"

const isServer = typeof window === "undefined"
const API_BASE_URL = isServer
    ? process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL
    : process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL

export interface RunMetric {
    label: string
    value: string
    change?: string
    trend?: "up" | "down" | "neutral"
}

export interface RunEquityPoint {
    date: string
    value: number
}

export interface RunData {
    id: string
    title: string
    date: string
    tags: string[]
    metrics: RunMetric[]
    equity?: RunEquityPoint[]
}

interface BacktestOut {
    run_id: string
    name?: string | null
    status: string
    created_at: string
    started_at?: string | null
    finished_at?: string | null
    data_snapshot_id: string
    seed: number
}

interface RunMetricOut {
    cagr?: number | null
    volatility?: number | null
    sharpe?: number | null
    sortino?: number | null
    max_drawdown?: number | null
    turnover?: number | null
    gross_return?: number | null
    net_return?: number | null
    fee_drag?: number | null
    tax_drag?: number | null
    borrow_drag?: number | null
    margin_interest_drag?: number | null
}

interface RunDailyEquityOut {
    date: string
    equity_base: number
}

// Mock data for demo/fallback purposes
const MOCK_RUNS: Record<string, RunData> = {
    "mock-buy-hold-us": {
        id: "buy-hold-us",
        title: "Buy & Hold — US Mega Cap (Demo)",
        date: "Ran on Mar 10, 2024 at 09:00",
        tags: ["Passive", "US Equity", "Quarterly Rebalance"],
        metrics: [
            { label: "Total Return", value: "+12.4%", change: "Benchmark", trend: "up" },
            { label: "Sharpe Ratio", value: "0.85", change: "Market aligned", trend: "neutral" },
            { label: "Max Drawdown", value: "-18.2%", change: "Standard", trend: "down" },
            { label: "Win Rate", value: "N/A", trend: "neutral" },
        ],
    },
    "mock-equal-weight-in": {
        id: "equal-weight-in",
        title: "Equal Weight — India Top 10 (Demo)",
        date: "Ran on Mar 11, 2024 at 10:30",
        tags: ["Smart Beta", "India Equity", "Monthly Rebalance"],
        metrics: [
            { label: "Total Return", value: "+22.1%", change: "+5.4% vs NIFTY", trend: "up" },
            { label: "Sharpe Ratio", value: "1.12", change: "Top 20%", trend: "up" },
            { label: "Max Drawdown", value: "-15.5%", change: "Moderate", trend: "neutral" },
            { label: "Win Rate", value: "62%", trend: "up" },
        ],
    },
    "mock-momentum": {
        id: "momentum",
        title: "Momentum — Top K Monthly (Demo)",
        date: "Ran on Mar 10, 2024 at 14:30",
        tags: ["Momentum", "US Equity", "Monthly Rebalance"],
        metrics: [
            { label: "Total Return", value: "+18.5%", change: "+2.3% vs SPY", trend: "up" },
            { label: "Sharpe Ratio", value: "1.45", change: "Top 5%", trend: "up" },
            { label: "Max Drawdown", value: "-12.4%", change: "Within limits", trend: "neutral" },
            { label: "Win Rate", value: "58%", trend: "up" },
        ],
    },
}

function formatPercent(value?: number | null): string {
    if (value === undefined || value === null) {
        return "N/A"
    }
    const pct = value * 100
    const sign = pct > 0 ? "+" : ""
    return `${sign}${pct.toFixed(2)}%`
}

function formatNumber(value?: number | null): string {
    if (value === undefined || value === null) {
        return "N/A"
    }
    return value.toFixed(2)
}

function formatDateLabel(iso: string): string {
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) {
        return iso
    }
    return date.toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
    })
}

function metricTrend(value?: number | null): "up" | "down" | "neutral" {
    if (value === undefined || value === null) {
        return "neutral"
    }
    if (value > 0) return "up"
    if (value < 0) return "down"
    return "neutral"
}

function mapMetrics(metrics: RunMetricOut | null): RunMetric[] {
    if (!metrics) {
        return [
            { label: "Total Return", value: "N/A", trend: "neutral" },
            { label: "Sharpe Ratio", value: "N/A", trend: "neutral" },
            { label: "Max Drawdown", value: "N/A", trend: "neutral" },
            { label: "Volatility", value: "N/A", trend: "neutral" },
        ]
    }

    const totalReturn = metrics.net_return ?? metrics.gross_return ?? null
    return [
        {
            label: "Total Return",
            value: formatPercent(totalReturn),
            change: metrics.net_return !== null && metrics.net_return !== undefined ? "Net" : "Gross",
            trend: metricTrend(totalReturn),
        },
        {
            label: "Sharpe Ratio",
            value: formatNumber(metrics.sharpe),
            trend: metricTrend(metrics.sharpe),
        },
        {
            label: "Max Drawdown",
            value: formatPercent(metrics.max_drawdown),
            trend: metricTrend(metrics.max_drawdown ? -Math.abs(metrics.max_drawdown) : metrics.max_drawdown),
        },
        {
            label: "Volatility",
            value: formatPercent(metrics.volatility),
            trend: "neutral",
        },
    ]
}

function mapEquity(equity: RunDailyEquityOut[] | null): RunEquityPoint[] | undefined {
    if (!equity || equity.length === 0) {
        return undefined
    }
    return equity.map((row) => ({
        date: row.date,
        value: row.equity_base,
    }))
}

export async function getRun(runId: string): Promise<RunData | null> {
    if (runId.startsWith("mock-")) {
        return MOCK_RUNS[runId] || MOCK_RUNS["mock-momentum"]
    }

    try {
        const [runRes, metricsRes, equityRes] = await Promise.all([
            fetch(`${API_BASE_URL}/runs/${runId}`, { cache: "no-store" }),
            fetch(`${API_BASE_URL}/runs/${runId}/metrics`, { cache: "no-store" }),
            fetch(`${API_BASE_URL}/runs/${runId}/equity`, { cache: "no-store" }),
        ])

        if (!runRes.ok) {
            console.error(`Failed to fetch run ${runId}: ${runRes.status} ${runRes.statusText}`)
            return null
        }

        const run: BacktestOut = await runRes.json()
        const metrics: RunMetricOut | null = metricsRes.ok ? await metricsRes.json() : null
        const equity: RunDailyEquityOut[] | null = equityRes.ok ? await equityRes.json() : null

        const title = run.name?.trim() || `Run ${run.run_id.slice(0, 8)}`
        const dateSource = run.finished_at || run.started_at || run.created_at
        const date = `Ran on ${formatDateLabel(dateSource)}`
        const tags = [
            run.status,
            `Snapshot: ${run.data_snapshot_id}`,
            `Seed: ${run.seed}`,
        ].filter(Boolean)

        return {
            id: run.run_id,
            title,
            date,
            tags,
            metrics: mapMetrics(metrics),
            equity: mapEquity(equity),
        }
    } catch (error) {
        console.error("Error fetching run:", error)
        return null
    }
}
