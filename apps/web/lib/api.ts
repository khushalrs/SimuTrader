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
    gross_exposure_base?: number
    net_exposure_base?: number
    drawdown?: number
    fees_cum_base?: number
    taxes_cum_base?: number
    borrow_fees_cum_base?: number
    margin_interest_cum_base?: number
}

export interface RunData {
    id: string
    title: string
    date: string
    tags: string[]
    metrics: RunMetric[]
    equity?: RunEquityPoint[]
    costs?: {
        fee_drag?: number | null
        tax_drag?: number | null
        borrow_drag?: number | null
        margin_interest_drag?: number | null
    }
    config_snapshot?: any
    requested_start_date?: string
    requested_end_date?: string
    effective_start_date?: string
    effective_end_date?: string
    baseCurrency?: string
    status?: string
    error?: string | null
}

interface BacktestOut {
    run_id: string
    name?: string | null
    status: string
    error?: string | null
    created_at: string
    started_at?: string | null
    finished_at?: string | null
    data_snapshot_id: string
    seed: number
    config_snapshot?: any
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
    gross_exposure_base: number
    net_exposure_base: number
    drawdown: number
    fees_cum_base: number
    taxes_cum_base: number
    borrow_fees_cum_base: number
    margin_interest_cum_base: number
}

export interface RunPositionOut {
    date: string
    symbol: string
    qty: number
    avg_cost_native: number
    market_value_base: number
    unrealized_pnl_base: number
    weight?: number | null
}

export interface RunFillOut {
    date: string
    symbol: string
    side?: string | null
    qty: number
    price: number
    notional: number
    commission: number
    slippage: number
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
        gross_exposure_base: row.gross_exposure_base,
        net_exposure_base: row.net_exposure_base,
        drawdown: row.drawdown,
        fees_cum_base: row.fees_cum_base,
        taxes_cum_base: row.taxes_cum_base,
        borrow_fees_cum_base: row.borrow_fees_cum_base,
        margin_interest_cum_base: row.margin_interest_cum_base,
    }))
}

export async function getRun(runId: string): Promise<RunData | null> {

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

        const configSnapshot = run.config_snapshot || {};
        const requested_start_date = configSnapshot.backtest?.start_date;
        const requested_end_date = configSnapshot.backtest?.end_date;

        let effective_start_date: string | undefined = undefined;
        let effective_end_date: string | undefined = undefined;

        if (equity && equity.length > 0) {
            effective_start_date = equity[0].date;
            effective_end_date = equity[equity.length - 1].date;
        }

        return {
            id: run.run_id,
            title,
            date,
            tags,
            metrics: mapMetrics(metrics),
            equity: mapEquity(equity),
            costs: metrics ? {
                fee_drag: metrics.fee_drag,
                tax_drag: metrics.tax_drag,
                borrow_drag: metrics.borrow_drag,
                margin_interest_drag: metrics.margin_interest_drag,
            } : undefined,
            config_snapshot: run.config_snapshot,
            requested_start_date,
            requested_end_date,
            effective_start_date,
            effective_end_date,
            baseCurrency: configSnapshot.base_currency || "USD",
            status: run.status,
            error: run.error,
        }
    } catch (error) {
        console.error("Error fetching run:", error)
        return null
    }
}

export function buildValidConfig(config: any) {
    const instruments = config.universe.instruments.map((i: any) => ({
        symbol: i.symbol,
        asset_class: i.asset_class
    }));

    const backtestObj: any = {
        start_date: config.backtest.start_date,
        end_date: config.backtest.end_date,
        initial_cash: parseFloat(config.backtest.initial_cash),
    };

    if (config.backtest.contributions?.enabled) {
        backtestObj.contributions = {
            enabled: true,
            amount: parseFloat(config.backtest.contributions.amount > 0 ? config.backtest.contributions.amount : 100),
            frequency: config.backtest.contributions.frequency
        };
    } else {
        backtestObj.contributions = { enabled: false };
    }

    const cleanParams: any = {};
    for (const [key, value] of Object.entries(config.strategy.params || {})) {
        if (value !== "" && value !== undefined && value !== null && !Number.isNaN(value)) {
            cleanParams[key] = value;
        }
    }

    return {
        version: 1,
        strategy: config.strategy.type,
        strategy_params: cleanParams,
        base_currency: config.universe.base_currency,
        commission: {
            model: "BPS",
            bps: parseFloat(config.execution.commission.bps),
            min_fee_native: parseFloat(config.execution.commission.min_fee || 0)
        },
        slippage: {
            model: "BPS",
            bps: parseFloat(config.execution.slippage.bps)
        },
        fill_price_policy: config.execution.fill_price || "CLOSE",
        universe: {
            instruments,
            calendars: config.universe.calendars
        },
        backtest: backtestObj,
        data_policy: {
            missing_bar: "FORWARD_FILL"
        }
    };
}

export async function createRun(config: any): Promise<string> {
    const validConfig = buildValidConfig(config);

    const payload = {
        name: config.name || "Custom Strategy Run",
        config_snapshot: validConfig,
        data_snapshot_id: "default_snapshot_2026",
        seed: 42
    };

    const res = await fetch(`${API_BASE_URL}/backtests`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    if (!res.ok) {
        const err = await res.text();
        throw new Error(`Failed to create run: ${err}`);
    }

    const data = await res.json();
    return data.run_id;
}

export async function createRunFromSnapshot(validConfig: any): Promise<string> {
    const payload = {
        name: "Retried Strategy Run",
        config_snapshot: validConfig,
        data_snapshot_id: "default_snapshot_2026",
        seed: 42
    };

    const res = await fetch(`${API_BASE_URL}/backtests`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    if (!res.ok) {
        const err = await res.text();
        throw new Error(`Failed to create retried run: ${err}`);
    }

    const data = await res.json();
    return data.run_id;
}

export async function getRunPositions(runId: string, date?: string): Promise<RunPositionOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/runs/${runId}/positions`)
        if (date) {
            url.searchParams.append("date", date)
        }
        const res = await fetch(url.toString(), { cache: "no-store" })
        if (!res.ok) {
            console.error(`Failed to fetch positions: ${res.status} ${res.statusText}`)
            return []
        }
        return await res.json()
    } catch (e) {
        console.error("Error fetching positions:", e)
        return []
    }
}

export async function getRunFills(runId: string, start?: string, end?: string): Promise<RunFillOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/runs/${runId}/fills`)
        if (start) {
            url.searchParams.append("start", start)
        }
        if (end) {
            url.searchParams.append("end", end)
        }
        const res = await fetch(url.toString(), { cache: "no-store" })
        if (!res.ok) {
            console.error(`Failed to fetch fills: ${res.status} ${res.statusText}`)
            return []
        }
        return await res.json()
    } catch (e) {
        console.error("Error fetching fills:", e)
        return []
    }
}

