const DEFAULT_API_BASE_URL = "http://localhost:8000"

const isServer = typeof window === "undefined"
// @ts-ignore
const API_BASE_URL = isServer
    // @ts-ignore
    ? process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL
    // @ts-ignore
    : process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL

function runApiFetch(input: string, init?: RequestInit): Promise<Response> {
    return fetch(input, {
        credentials: "include",
        ...init,
    })
}

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
    error_code?: string | null
    error_message_public?: string | null
    error_retryable?: boolean | null
    error_id?: string | null
}

interface BacktestOut {
    run_id: string
    name?: string | null
    status: string
    error_code?: string | null
    error_message_public?: string | null
    error_retryable?: boolean | null
    error_id?: string | null
    created_at: string
    started_at?: string | null
    finished_at?: string | null
    data_snapshot_id: string
    seed: number
    config_snapshot?: any
}

export interface RunStatusOut {
    run_id: string
    status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
    progress: number
    started_at?: string
    completed_at?: string
    error_code?: string
    error_message_runtime?: string
    error_message_public?: string
    error_retryable?: boolean
    error_id?: string
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

export interface RunTaxEventOut {
    date: string
    symbol: string
    quantity: number
    realized_pnl_base: number
    holding_period_days: number
    bucket: string
    tax_rate: number
    tax_due_base: number
    meta?: Record<string, any>
}

export interface RunTaxesOut {
    run_id: string
    event_count: number
    total_realized_pnl_base: number
    total_tax_due_base: number
    by_bucket_tax_due_base: Record<string, number>
    events: RunTaxEventOut[]
}

export interface RunCompareMetricRowOut {
    run_id: string
    cagr?: number | null
    volatility?: number | null
    sharpe?: number | null
    max_drawdown?: number | null
    gross_return?: number | null
    net_return?: number | null
    fee_drag?: number | null
    tax_drag?: number | null
    borrow_drag?: number | null
    margin_interest_drag?: number | null
}

export interface RunCompareSeriesPointOut {
    date: string
    value: number
}

export interface RunCompareSeriesOut {
    run_id: string
    points: RunCompareSeriesPointOut[]
}

export interface RunCompareOut {
    base_run_id: string
    run_ids: string[]
    metric_rows: RunCompareMetricRowOut[]
    equity_series: RunCompareSeriesOut[]
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

function buildIdempotencyKey(prefix: string, payload: unknown): string {
    const raw = `${prefix}:${JSON.stringify(payload)}`
    let hash = 2166136261
    for (let i = 0; i < raw.length; i += 1) {
        hash ^= raw.charCodeAt(i)
        hash +=
            (hash << 1) +
            (hash << 4) +
            (hash << 7) +
            (hash << 8) +
            (hash << 24)
    }
    const bucket = Math.floor(Date.now() / 30000)
    return `${prefix}-${bucket}-${Math.abs(hash >>> 0)}`
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
        const runRes = await runApiFetch(`${API_BASE_URL}/runs/${runId}`, { cache: "no-store" })

        if (!runRes.ok) {
            console.error(`Failed to fetch run ${runId}: ${runRes.status} ${runRes.statusText}`)
            return null
        }

        const run: BacktestOut = await runRes.json()

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

        return {
            id: run.run_id,
            title,
            date,
            tags,
            metrics: mapMetrics(null),
            equity: undefined,
            costs: undefined,
            config_snapshot: run.config_snapshot,
            requested_start_date,
            requested_end_date,
            baseCurrency: configSnapshot.base_currency || "USD",
            status: run.status,
            error_code: run.error_code,
            error_message_public: run.error_message_public,
            error_retryable: run.error_retryable,
            error_id: run.error_id,
            effective_start_date: undefined, // Let client fetch equity to determine this if needed
            effective_end_date: undefined,
        }
    } catch (error) {
        console.error("Error fetching run:", error)
        return null
    }
}

export async function getRunStatus(runId: string): Promise<RunStatusOut | null> {
    try {
        const res = await fetch(`${API_BASE_URL}/runs/${runId}/status`, { cache: "no-store" })
        if (!res.ok) return null
        return await res.json()
    } catch (e) {
        console.error("Error fetching run status:", e)
        return null
    }
}

export async function getRunMetrics(runId: string) {
    const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/metrics`, { cache: "no-store" });
    if (!res.ok) return null;
    const data: RunMetricOut = await res.json();
    return {
        metrics: mapMetrics(data),
        costs: {
            fee_drag: data.fee_drag,
            tax_drag: data.tax_drag,
            borrow_drag: data.borrow_drag,
            margin_interest_drag: data.margin_interest_drag,
        }
    };
}

export async function getRunEquity(runId: string) {
    const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/equity`, { cache: "no-store" });
    if (!res.ok) return null;
    const data: RunDailyEquityOut[] = await res.json();
    return mapEquity(data);
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
        cash_currency: config.backtest.cash_currency || "USD",
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
        execution: {
            commission: {
                model: "BPS",
                bps: parseFloat(config.execution.commission.bps),
                min_fee: parseFloat(config.execution.commission.min_fee || 0),
            },
            slippage: {
                model: "BPS",
                bps: parseFloat(config.execution.slippage.bps),
            },
            fill_price: config.execution.fill_price || "CLOSE",
        },
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
        financing: config.financing,
        risk: config.risk,
        tax: config.tax,
        data_policy: {
            missing_bar: "FORWARD_FILL",
            missing_fx: "FORWARD_FILL",
        }
    };
}

export async function createRun(config: any, client_idempotency_key?: string): Promise<string> {
    const validConfig = buildValidConfig(config);

    const payload = {
        name: config.name || "Custom Strategy Run",
        config_snapshot: validConfig,
        data_snapshot_id: "default_snapshot_2026",
        seed: 42
    };
    const idempotencyKey = client_idempotency_key || buildIdempotencyKey("create-run", payload)

    const res = await runApiFetch(`${API_BASE_URL}/backtests`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotencyKey,
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

export async function createRunFromSnapshot(validConfig: any, client_idempotency_key?: string): Promise<string> {
    const payload = {
        name: "Retried Strategy Run",
        config_snapshot: validConfig,
        data_snapshot_id: "default_snapshot_2026",
        seed: 42
    };
    const idempotencyKey = client_idempotency_key || buildIdempotencyKey("retry-run", payload)

    const res = await runApiFetch(`${API_BASE_URL}/backtests`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotencyKey,
            'X-Reuse-Succeeded-Run': 'true',
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

export async function getOrCreatePlaygroundPresetRun(presetId: string): Promise<string> {
    const res = await runApiFetch(`${API_BASE_URL}/playground/presets/${presetId}/run`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
    })
    if (!res.ok) {
        const err = await res.text()
        throw new Error(`Failed to get preset run: ${err}`)
    }
    const data = await res.json()
    return data.run_id
}

export async function getRunPositions(runId: string, date?: string, limit?: number): Promise<RunPositionOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/runs/${runId}/positions`)
        if (date) {
            url.searchParams.append("date", date)
        }
        if (limit) {
            url.searchParams.append("limit", limit.toString())
        }
        const res = await runApiFetch(url.toString(), { cache: "no-store" })
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

export async function getRunTaxes(runId: string): Promise<RunTaxesOut | null> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/backtests/${runId}/taxes`, { cache: "no-store" })
        if (!res.ok) {
            console.error(`Failed to fetch taxes: ${res.status} ${res.statusText}`)
            return null
        }
        return await res.json()
    } catch (e) {
        console.error("Error fetching taxes:", e)
        return null
    }
}

export async function compareRuns(baseRunId: string, runIds: string[]): Promise<RunCompareOut | null> {
    try {
        const url = new URL(`${API_BASE_URL}/backtests/${baseRunId}/compare`)
        if (runIds.length > 0) {
            url.searchParams.append("run_ids", runIds.join(","))
        }
        const res = await runApiFetch(url.toString(), { cache: "no-store" })
        if (!res.ok) {
            console.error(`Failed to compare runs: ${res.status} ${res.statusText}`)
            return null
        }
        return await res.json()
    } catch (e) {
        console.error("Error comparing runs:", e)
        return null
    }
}

export async function getRunFills(runId: string, start?: string, end?: string, limit?: number, offset?: number): Promise<RunFillOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/runs/${runId}/fills`)
        if (start) {
            url.searchParams.append("start", start)
        }
        if (end) {
            url.searchParams.append("end", end)
        }
        const res = await runApiFetch(url.toString(), { cache: "no-store" })
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

export async function getRunTopHoldings(runId: string, limit: number = 5): Promise<RunPositionOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/runs/${runId}/top-holdings`)
        url.searchParams.append("limit", limit.toString())
        const res = await fetch(url.toString(), { cache: "no-store" })
        if (!res.ok) {
            console.error(`Failed to fetch top holdings: ${res.status} ${res.statusText}`)
            return []
        }
        return await res.json()
    } catch (e) {
        console.error("Error fetching top holdings:", e)
        return []
    }
}

export interface AssetOut {
    symbol: string
    name: string
    asset_class: string
}

export async function searchAssets(query: string): Promise<AssetOut[]> {
    if (!query) return []
    try {
        const url = new URL(`${API_BASE_URL}/assets`)
        url.searchParams.append("q", query)
        const res = await runApiFetch(url.toString())
        if (!res.ok) {
            console.error(`Failed to fetch assets: ${res.status}`)
            return []
        }
        return await res.json()
    } catch (e) {
        console.error("Error searching assets", e)
        return []
    }
}
