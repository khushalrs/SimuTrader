import { z } from "zod"

const DEFAULT_API_BASE_URL = "http://localhost:8000"

const isServer = typeof window === "undefined"
const isProd = process.env.NODE_ENV === "production"

let rawApiBaseUrl = isServer
    ? (process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL)
    : process.env.NEXT_PUBLIC_API_BASE_URL

if (isProd) {
    if (!rawApiBaseUrl) {
        throw new Error("Missing API_BASE_URL or NEXT_PUBLIC_API_BASE_URL in production environment.")
    }
    const isLocal = rawApiBaseUrl.includes("localhost") || 
                    rawApiBaseUrl.includes("127.0.0.1") || 
                    rawApiBaseUrl.includes("host.docker.internal");
    if (!rawApiBaseUrl.startsWith("https://") && !isLocal) {
        throw new Error(`Production API base URL must use HTTPS. Received: ${rawApiBaseUrl}`)
    }
} else {
    rawApiBaseUrl = rawApiBaseUrl || DEFAULT_API_BASE_URL
}

const API_BASE_URL = rawApiBaseUrl as string

// ---------------------------------------------------------------------------
// Dev-only logger — silenced in production to prevent backend internals from
// leaking into browser consoles or log aggregators.
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function devLog(...args: any[]): void {
    if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.error(...args)
    }
}

// ---------------------------------------------------------------------------
// extractErrorMessage — returns a safe, generic message for the UI in prod.
// The raw backend detail is only logged in development.
// ---------------------------------------------------------------------------
async function extractErrorMessage(res: Response, fallbackPrefix: string): Promise<string> {
    try {
        const errJson = await res.json();
        const rawMsg = errJson.error_message_public || errJson.detail || JSON.stringify(errJson);
        devLog(`[API] ${fallbackPrefix}:`, rawMsg)
        if (isProd) {
            return `${fallbackPrefix}: An unexpected error occurred. Please try again.`;
        }
        return `${fallbackPrefix}: ${rawMsg}`;
    } catch {
        return `${fallbackPrefix}: Server returned status ${res.status}`;
    }
}

// ---------------------------------------------------------------------------
// Zod schemas — validate the shapes of critical API responses at runtime.
// Use .safeParse() so a malformed backend response degrades gracefully
// instead of crashing the UI with an unhandled exception.
// ---------------------------------------------------------------------------

const BacktestOutSchema = z.object({
    run_id: z.string(),
    name: z.string().nullish(),
    status: z.string(),
    error_code: z.string().nullish(),
    error_message_public: z.string().nullish(),
    error_retryable: z.boolean().nullish(),
    error_id: z.string().nullish(),
    created_at: z.string(),
    started_at: z.string().nullish(),
    finished_at: z.string().nullish(),
    data_snapshot_id: z.string(),
    seed: z.number(),
    config_snapshot: z.any().optional(),
})

const RunMetricOutSchema = z.object({
    cagr: z.number().nullish(),
    volatility: z.number().nullish(),
    sharpe: z.number().nullish(),
    sortino: z.number().nullish(),
    max_drawdown: z.number().nullish(),
    turnover: z.number().nullish(),
    gross_return: z.number().nullish(),
    net_return: z.number().nullish(),
    fee_drag: z.number().nullish(),
    tax_drag: z.number().nullish(),
    borrow_drag: z.number().nullish(),
    margin_interest_drag: z.number().nullish(),
    explanation: z.string().nullish(),
})

const RunDailyEquityOutSchema = z.object({
    date: z.string(),
    equity_base: z.number(),
    gross_exposure_base: z.number(),
    net_exposure_base: z.number(),
    drawdown: z.number(),
    fees_cum_base: z.number(),
    taxes_cum_base: z.number(),
    borrow_fees_cum_base: z.number(),
    margin_interest_cum_base: z.number(),
})

// The /backtests list returns BacktestOut-shaped objects. We keep the schema
// permissive (passthrough) for extra fields the server may add.
const RunListItemSchema = z.object({
    run_id: z.string(),
}).passthrough()

const RunListSchema = z.array(RunListItemSchema)

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
    explanation?: string | null
    equity?: RunEquityPoint[]
    costs?: {
        fee_drag?: number | null
        tax_drag?: number | null
        borrow_drag?: number | null
        margin_interest_drag?: number | null
        gross_return?: number | null
        net_return?: number | null
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
    explanation?: string | null
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

/** Numeric metric columns on a compare row -- the keys that are safe to index
 *  dynamically and that also appear in `delta_vs_base`. */
export type CompareMetricKey =
    | "cagr"
    | "volatility"
    | "sharpe"
    | "sortino"
    | "max_drawdown"
    | "turnover"
    | "gross_return"
    | "net_return"
    | "fee_drag"
    | "tax_drag"
    | "borrow_drag"
    | "margin_interest_drag"

export interface RunCompareMetricRowOut {
    run_id: string
    name?: string | null
    strategy_type?: string | null
    tax_regime?: string | null
    base_currency?: string | null
    start_date?: string | null
    end_date?: string | null
    delta_vs_base?: Partial<Record<CompareMetricKey, number | null>> | null
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
            devLog(`[API] Failed to fetch run ${runId}: ${runRes.status} ${runRes.statusText}`)
            return null
        }

        const parsed = BacktestOutSchema.safeParse(await runRes.json())
        if (!parsed.success) {
            devLog("[API] getRun: unexpected response shape", parsed.error.format())
            return null
        }
        const run: BacktestOut = parsed.data

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
        devLog("[API] Error fetching run:", error)
        return null
    }
}

export async function getRunStatus(runId: string): Promise<RunStatusOut | null> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/status`, { cache: "no-store" })
        if (!res.ok) return null
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching run status:", e)
        return null
    }
}

export async function getRunMetrics(runId: string) {
    const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/metrics`, { cache: "no-store" });
    if (!res.ok) return null;
    const parsed = RunMetricOutSchema.safeParse(await res.json());
    if (!parsed.success) {
        devLog("[API] getRunMetrics: unexpected response shape", parsed.error.format())
        return null
    }
    const data: RunMetricOut = parsed.data
    return {
        metrics: mapMetrics(data),
        explanation: data.explanation,
        costs: {
            fee_drag: data.fee_drag,
            tax_drag: data.tax_drag,
            borrow_drag: data.borrow_drag,
            margin_interest_drag: data.margin_interest_drag,
            gross_return: data.gross_return,
            net_return: data.net_return,
        }
    };
}

export async function getRunEquity(runId: string) {
    const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/equity`, { cache: "no-store" });
    if (!res.ok) return null;
    const parsed = z.array(RunDailyEquityOutSchema).safeParse(await res.json());
    if (!parsed.success) {
        devLog("[API] getRunEquity: unexpected response shape", parsed.error.format())
        return null
    }
    return mapEquity(parsed.data);
}

export function buildValidConfig(config: any) {
    const instruments = config.universe.instruments.map((i: any) => {
        const item: any = {
            symbol: i.symbol,
            asset_class: i.asset_class
        };
        if (i.weight !== undefined && i.weight !== null && i.weight !== "") {
            item.weight = parseFloat(i.weight);
        }
        if (i.amount !== undefined && i.amount !== null && i.amount !== "") {
            item.amount = parseFloat(i.amount);
        }
        return item;
    });

    const backtestObj: any = {
        start_date: config.backtest.start_date,
        end_date: config.backtest.end_date,
        initial_cash: parseFloat(config.backtest.initial_cash),
        // cash_currency is not accepted by the backend schema
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
        if (value !== "" && value !== undefined && value !== null) {
            if (typeof value === "object" && !Array.isArray(value)) {
                const cleanSubObj: any = {};
                for (const [subKey, subVal] of Object.entries(value || {})) {
                    if (subVal !== "" && subVal !== undefined && subVal !== null) {
                        cleanSubObj[subKey] = typeof subVal === "string" ? parseFloat(subVal) : subVal;
                    }
                }
                cleanParams[key] = cleanSubObj;
            } else if (!Number.isNaN(value)) {
                cleanParams[key] = value;
            }
        }
    }

    return {
        version: 1,
        benchmark: config.benchmark?.trim() || null,
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
        financing: config.financing ? {
            ...config.financing,
            shorting: config.financing.shorting ? {
                enabled: config.financing.shorting.enabled,
                borrow_fee_daily_bps: config.financing.shorting.borrow_fee_daily_bps,
                // locate_required is not accepted by the backend schema
            } : undefined,
        } : undefined,
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
        const err = await extractErrorMessage(res, "Failed to create run");
        throw new Error(err);
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
        const err = await extractErrorMessage(res, "Failed to create retried run");
        throw new Error(err);
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
        const err = await extractErrorMessage(res, "Failed to get preset run");
        throw new Error(err)
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
            devLog(`[API] Failed to fetch positions: ${res.status} ${res.statusText}`)
            return []
        }
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching positions:", e)
        return []
    }
}

export async function getRunTaxes(runId: string): Promise<RunTaxesOut | null> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/backtests/${runId}/taxes`, { cache: "no-store" })
        if (!res.ok) {
            devLog(`[API] Failed to fetch taxes: ${res.status} ${res.statusText}`)
            return null
        }
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching taxes:", e)
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
            devLog(`[API] Failed to compare runs: ${res.status} ${res.statusText}`)
            return null
        }
        return await res.json()
    } catch (e) {
        devLog("[API] Error comparing runs:", e)
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
        if (limit !== undefined && limit !== null) {
            url.searchParams.append("limit", limit.toString())
        }
        if (offset !== undefined && offset !== null) {
            url.searchParams.append("offset", offset.toString())
        }
        const res = await runApiFetch(url.toString(), { cache: "no-store" })
        if (!res.ok) {
            devLog(`[API] Failed to fetch fills: ${res.status} ${res.statusText}`)
            return []
        }
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching fills:", e)
        return []
    }
}

export async function getRunTopHoldings(runId: string, limit: number = 5): Promise<RunPositionOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/runs/${runId}/top-holdings`)
        url.searchParams.append("limit", limit.toString())
        const res = await runApiFetch(url.toString(), { cache: "no-store" })
        if (!res.ok) {
            devLog(`[API] Failed to fetch top holdings: ${res.status} ${res.statusText}`)
            return []
        }
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching top holdings:", e)
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
            devLog(`[API] Failed to fetch assets: ${res.status}`)
            return []
        }
        return await res.json()
    } catch (e) {
        devLog("[API] Error searching assets", e)
        return []
    }
}

export async function getRuns(): Promise<RunData[]> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/backtests`, { cache: "no-store" })
        if (!res.ok) {
            devLog(`[API] Failed to fetch runs: ${res.status} ${res.statusText}`)
            return []
        }
        const raw = await res.json()
        if (!Array.isArray(raw)) return []
        return raw.map((item: any) => {
            const id = item.run_id || item.id
            const title = item.name?.trim() || item.title?.trim() || `Run ${id ? id.slice(0, 8) : "Untitled"}`
            const dateSource = item.finished_at || item.started_at || item.created_at
            const date = dateSource ? `Ran on ${formatDateLabel(dateSource)}` : item.date || ""
            return {
                id,
                title,
                name: item.name || title,
                run_id: id,
                date,
                tags: [
                    item.status,
                    item.data_snapshot_id ? `Snapshot: ${item.data_snapshot_id}` : "",
                    item.seed !== undefined ? `Seed: ${item.seed}` : "",
                ].filter(Boolean),
                metrics: mapMetrics(null),
                status: item.status,
                config_snapshot: item.config_snapshot,
                created_at: item.created_at,
            }
        })
    } catch (e) {
        devLog("[API] Error fetching runs:", e)
        return []
    }
}

export interface StrategyCreate {
    name: string;
    description?: string;
    config: any;
}

export interface StrategyOut {
    strategy_id: string;
    name: string;
    description?: string;
    config: any;
    created_at: string;
}

export async function createStrategy(payload: StrategyCreate): Promise<StrategyOut> {
    const res = await runApiFetch(`${API_BASE_URL}/strategies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!res.ok) {
        throw new Error(await extractErrorMessage(res, "Failed to create strategy"));
    }
    return await res.json();
}

export async function getStrategies(): Promise<StrategyOut[]> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/strategies`, { cache: "no-store" });
        if (!res.ok) return [];
        return await res.json();
    } catch {
        return [];
    }
}

export async function getStrategy(id: string): Promise<StrategyOut | null> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/strategies/${id}`, { cache: "no-store" });
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

export interface BacktestPreflightCheck {
    name: string
    passed: boolean
    message?: string
    severity?: string
}

export interface BacktestPreflightOut {
    ok: boolean
    status: "green" | "yellow" | "red"
    errors: string[]
    warnings: string[]
    checks?: BacktestPreflightCheck[]
    meta?: Record<string, any>
    strategy_capability?: Record<string, any>
    estimated_trading_days?: number | null
    estimated_symbols?: number
    estimated_rebalance_count?: number | null
    risk_flags?: Array<{
        code: string
        severity: "error" | "warning" | string
        message: string
        details: Record<string, any>
    }>
}

export type PreflightResponse = BacktestPreflightOut

export async function preflightBacktest(config: any): Promise<PreflightResponse> {
    try {
        const validConfig = buildValidConfig(config)
        const payload = {
            config_snapshot: validConfig,
            data_snapshot_id: "default_snapshot_2026",
            seed: 42
        }
        const res = await runApiFetch(`${API_BASE_URL}/backtests/preflight`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        })
        if (!res.ok) {
            return {
                ok: false,
                status: "red",
                errors: [`Preflight request failed with status ${res.status}`],
                warnings: [],
                checks: []
            }
        }
        const data = await res.json()
        let status: "green" | "yellow" | "red" = "green"
        if (!data.ok || (data.errors && data.errors.length > 0)) {
            status = "red"
        } else if (data.warnings && data.warnings.length > 0) {
            status = "yellow"
        }
        return {
            ok: data.ok ?? status !== "red",
            status: data.status || status,
            errors: data.errors || [],
            warnings: data.warnings || [],
            checks: data.checks || [],
            meta: data.meta,
            strategy_capability: data.strategy_capability || {},
            estimated_trading_days: data.estimated_trading_days ?? null,
            estimated_symbols: data.estimated_symbols ?? 0,
            estimated_rebalance_count: data.estimated_rebalance_count ?? null,
            risk_flags: data.risk_flags || []
        }
    } catch (e: any) {
        return {
            ok: false,
            status: "red",
            errors: [e.message || "Failed to contact preflight validation engine"],
            warnings: [],
            checks: []
        }
    }
}

// ---------------------------------------------------------------------------
// Additional Endpoints
// ---------------------------------------------------------------------------

/** Mirrors backend RunExplainOut. Keys of `drag_breakdown` and the values of
 *  `dominant_drag` are fees | taxes | borrow | margin_interest -- NOT the *_drag
 *  names used by RunMetric. Fields below `summary` arrive with the backend explain
 *  upgrade and are optional until then. */
export type DragKey = "fees" | "taxes" | "borrow" | "margin_interest"

export interface RunExplainOut {
    gross_return: number | null
    net_return: number | null
    total_drag: number | null
    drag_breakdown: Partial<Record<DragKey, number>>
    dominant_drag: DragKey | null
    trade_count: number
    turnover: number | null
    tax_regime: string
    summary: string
    headline?: string | null
    best_period?: { date_range?: string; return_pct?: number; description?: string } | null
    worst_period?: { date_range?: string; return_pct?: number; description?: string } | null
    largest_position?: { symbol?: string; weight_pct?: number } | null
    largest_trade?: { symbol?: string; notional?: number } | null
    largest_tax_event?: { symbol?: string; tax_due?: number } | null
}

export interface RunExposureBreakdown {
    long_base: number
    short_base: number
    gross_base: number
    net_base: number
}

export interface RunExposurePointOut {
    date: string
    long_base: number
    short_base: number
    gross_base: number
    net_base: number
    leverage: number | null
    equity_native_by_currency: Record<string, number>
    exposure_base_by_currency: Record<string, RunExposureBreakdown>
    by_asset_class: Record<string, RunExposureBreakdown>
    by_country: Record<string, RunExposureBreakdown>
}

export interface RunCostsSummaryOut {
    commissions_native: Record<string, number>
    slippage_native: Record<string, number>
    fees_total_base: number
    taxes_total_base: number
    borrow_fees_base: number
    margin_interest_base: number
}

export async function getRunExplain(runId: string): Promise<RunExplainOut | null> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/explain`, { cache: "no-store" })
        if (!res.ok) return null
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching run explain:", e)
        return null
    }
}

export async function getRunExposure(runId: string): Promise<RunExposurePointOut[]> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/exposure`, { cache: "no-store" })
        if (!res.ok) return []
        const data = await res.json()
        return Array.isArray(data) ? data : []
    } catch (e) {
        devLog("[API] Error fetching run exposure:", e)
        return []
    }
}

export async function getRunCostsSummary(runId: string): Promise<RunCostsSummaryOut | null> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/runs/${runId}/costs_summary`, { cache: "no-store" })
        if (!res.ok) return null
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching run costs summary:", e)
        return null
    }
}

export async function getStrategySchemas(): Promise<any> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/strategies/schemas`, { cache: "no-store" })
        if (!res.ok) return []
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching strategy schemas:", e)
        return []
    }
}

export async function getCapabilities(): Promise<any> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/capabilities`, { cache: "no-store" })
        if (!res.ok) return null
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching capabilities:", e)
        return null
    }
}

export async function cloneRun(runId: string, overrides?: any): Promise<string> {
    const res = await runApiFetch(`${API_BASE_URL}/backtests/${runId}/clone`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(overrides || {})
    })
    if (!res.ok) {
        throw new Error(await extractErrorMessage(res, "Failed to clone run"))
    }
    const data = await res.json()
    return data.run_id || data.id
}

export async function createScenario(payload: any): Promise<any> {
    const res = await runApiFetch(`${API_BASE_URL}/scenarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    if (!res.ok) {
        throw new Error(await extractErrorMessage(res, "Failed to create scenario"))
    }
    return await res.json()
}

export async function getDataCoverage(symbols?: string[]): Promise<any> {
    try {
        const url = new URL(`${API_BASE_URL}/data/coverage`)
        if (symbols && symbols.length > 0) {
            url.searchParams.append("symbols", symbols.join(","))
        }
        const res = await runApiFetch(url.toString(), { cache: "no-store" })
        if (!res.ok) return []
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching data coverage:", e)
        return []
    }
}

export async function getDataQuality(symbols?: string[]): Promise<any> {
    try {
        const url = new URL(`${API_BASE_URL}/data/quality`)
        if (symbols && symbols.length > 0) {
            url.searchParams.append("symbols", symbols.join(","))
        }
        const res = await runApiFetch(url.toString(), { cache: "no-store" })
        if (!res.ok) return []
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching data quality:", e)
        return []
    }
}

export interface PlaygroundPreset {
    id: string
    name: string
    description: string
    strategy_type: string
    base_currency: string
    symbols: string[]
    asset_classes: string[]
    data_snapshot_id: string
    config_snapshot: any
}

export async function getPlaygroundPresets(): Promise<PlaygroundPreset[]> {
    try {
        const res = await runApiFetch(`${API_BASE_URL}/playground/presets`, { cache: "no-store" })
        if (!res.ok) return []
        return await res.json()
    } catch (e) {
        devLog("[API] Error fetching playground presets:", e)
        return []
    }
}

// ---------------------------------------------------------------------------
// Market API (folded from lib/market.ts)
// ---------------------------------------------------------------------------

export interface MarketBarOut {
    date: string
    symbol: string
    currency: string
    exchange: string
    open?: number | null
    high?: number | null
    low?: number | null
    close?: number | null
    volume?: number | null
}

export interface MarketCoverageOut {
    symbol: string
    first_date: string
    last_date: string
    rows: number
    missing_ratio?: number | null
}

export interface MarketSnapshotOut {
    symbol: string
    last_date: string
    last_close: number
    return_1w?: number | null
    return_1m?: number | null
    return_3m?: number | null
    return_1y?: number | null
    recent_vol_20d?: number | null
    median_vol_1y?: number | null
    meta?: any
}

const marketCache = new Map<string, { timestamp: number; data: any }>()
const marketPendingRequests = new Map<string, Promise<any>>()
const CACHE_TTL_MS = 60000

function getMarketCached<T>(key: string): T | null {
    const entry = marketCache.get(key)
    if (entry && Date.now() - entry.timestamp < CACHE_TTL_MS) {
        return entry.data as T
    }
    return null
}

function setMarketCached(key: string, data: any) {
    marketCache.set(key, { timestamp: Date.now(), data })
}

async function deduplicatedMarketFetch<T>(url: URL, cacheKey: string): Promise<T> {
    const cached = getMarketCached<T>(cacheKey)
    if (cached) return cached

    if (marketPendingRequests.has(cacheKey)) {
        return marketPendingRequests.get(cacheKey) as Promise<T>
    }

    const promise = (async () => {
        try {
            const res = await runApiFetch(url.toString())
            if (!res.ok) {
                devLog(`[Market API] Failed to fetch ${url.pathname}: ${res.status} ${res.statusText}`)
                throw new Error(`${res.status} ${res.statusText}`)
            }
            const data = await res.json()
            setMarketCached(cacheKey, data)
            return data
        } finally {
            marketPendingRequests.delete(cacheKey)
        }
    })()

    marketPendingRequests.set(cacheKey, promise)
    return promise
}

export async function getMarketBars(
    symbols: string[],
    startDate?: string,
    endDate?: string,
    fields: string = "close",
    calendar: string = "GLOBAL",
    missingBar: string = "RAW",
    interval: string = "1d",
    maxPoints?: number
): Promise<MarketBarOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/market/bars`)
        url.searchParams.append("symbols", symbols.join(","))
        if (startDate) url.searchParams.append("start_date", startDate)
        if (endDate) url.searchParams.append("end_date", endDate)
        if (fields) url.searchParams.append("fields", fields)
        if (calendar) url.searchParams.append("calendar", calendar)
        if (missingBar) url.searchParams.append("missing_bar", missingBar)
        if (interval) url.searchParams.append("interval", interval)
        if (maxPoints) url.searchParams.append("max_points", String(maxPoints))

        const cacheKey = `bars_${url.toString()}`
        return await deduplicatedMarketFetch<MarketBarOut[]>(url, cacheKey)
    } catch (error) {
        devLog("[Market API] Error fetching market bars:", error)
        return []
    }
}

export async function getMarketCoverage(
    symbols: string[],
    startDate?: string,
    endDate?: string,
    calendar: string = "GLOBAL"
): Promise<MarketCoverageOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/market/coverage`)
        url.searchParams.append("symbols", symbols.join(","))
        if (startDate) url.searchParams.append("start_date", startDate)
        if (endDate) url.searchParams.append("end_date", endDate)
        if (calendar) url.searchParams.append("calendar", calendar)

        const cacheKey = `coverage_${url.toString()}`
        return await deduplicatedMarketFetch<MarketCoverageOut[]>(url, cacheKey)
    } catch (error) {
        devLog("[Market API] Error fetching market coverage:", error)
        return []
    }
}

export async function getMarketSnapshot(
    symbols: string[],
    endDate?: string
): Promise<MarketSnapshotOut[]> {
    try {
        const url = new URL(`${API_BASE_URL}/market/snapshot`)
        url.searchParams.append("symbols", symbols.join(","))
        if (endDate) url.searchParams.append("end_date", endDate)

        const cacheKey = `snapshot_${url.toString()}`
        return await deduplicatedMarketFetch<MarketSnapshotOut[]>(url, cacheKey)
    } catch (error) {
        devLog("[Market API] Error fetching market snapshot:", error)
        return []
    }
}
