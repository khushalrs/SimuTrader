"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { createRun, buildValidConfig, preflightBacktest, type BacktestPreflightOut } from "@/lib/api"
import { 
    AlertCircle, 
    CheckCircle2, 
    AlertTriangle, 
    Globe, 
    Activity, 
    ShieldAlert, 
    ChevronDown,
    Calendar,
    Coins,
    Sliders
} from "lucide-react"
import { Badge } from "@/components/ui/badge"

const EXCLUDED_CAPABILITY_KEYS = new Set([
    "allocation_modes", // duplicate with supported_allocation_modes
    "param_types", // object
    "defaults", // object
    "supported_asset_classes" // rendered separately
])

const CAPABILITY_LABEL_MAP: Record<string, string> = {
    required_params: "Required Parameters",
    optional_params: "Optional Parameters",
    supported_allocation_modes: "Supported Allocations",
    supports_mixed_currency: "Cross-Currency FX",
    supports_shorting: "Short Selling Enabled",
    supports_margin: "Margin Borrowing Enabled"
}

export function ReviewStep({ config, prevStep }: any) {
    const router = useRouter()
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [idempotencyKey, setIdempotencyKey] = useState<string>("")

    const [preflightRes, setPreflightRes] = useState<BacktestPreflightOut | null>(null)
    const [isPreflighting, setIsPreflighting] = useState(true)

    const validConfig = buildValidConfig(config)

    useEffect(() => {
        setIdempotencyKey(crypto.randomUUID())
    }, [config])

    useEffect(() => {
        let active = true
        setIsPreflighting(true)
        preflightBacktest(config).then(res => {
            if (active) {
                setPreflightRes(res)
                setIsPreflighting(false)
            }
        }).catch((err) => {
            if (active) {
                setPreflightRes({
                    ok: false,
                    status: "red",
                    errors: [err.message || "Preflight request failed."],
                    warnings: [],
                    checks: [],
                    risk_flags: []
                })
                setIsPreflighting(false)
            }
        })
        return () => { active = false }
    }, [config])

    const handleRun = async () => {
        try {
            setIsSubmitting(true)
            setError(null)
            const runId = await createRun(config, idempotencyKey)
            router.push(`/runs/${runId}`)
        } catch (err: any) {
            console.error("Run error:", err)
            setError(err.message || "Failed to start run.")
        } finally {
            setIdempotencyKey(crypto.randomUUID())
            setIsSubmitting(false)
        }
    }

    // Helper to render date callout comparison
    const requestedStart = validConfig.backtest?.start_date
    const requestedEnd = validConfig.backtest?.end_date
    const effectiveStart = preflightRes?.meta?.effective_start_date || (preflightRes as any)?.meta?.effective_start || (preflightRes as any)?.effective_start || requestedStart
    const effectiveEnd = preflightRes?.meta?.effective_end_date || (preflightRes as any)?.meta?.effective_end || (preflightRes as any)?.effective_end || requestedEnd
    const isDateShifted = requestedStart && effectiveStart && (requestedStart !== effectiveStart || requestedEnd !== effectiveEnd)

    // Data coverage (Top-level in preflight response)
    const dataCoverage = (preflightRes as any)?.data_coverage || (preflightRes as any)?.coverage || preflightRes?.meta?.data_coverage || []

    // Required FX conversion pairs (Top-level in preflight response)
    const fxPairs = (preflightRes as any)?.required_fx_pairs || (preflightRes as any)?.fx_pairs || preflightRes?.meta?.required_fx_pairs || []

    // Strategy capabilities
    const capabilities = (preflightRes as any)?.strategy_capability || {}

    // Formatting capability values to avoid raw objects or raw developer keys
    const getFormattedValue = (key: string, val: any) => {
        if (typeof val === "boolean") {
            return val ? "Supported" : "Not Supported"
        }
        if (Array.isArray(val)) {
            if (val.length === 0) return "None"
            return val.map((v: string) => {
                // Map parameter names to clean labels
                if (v === "weights") return "Target Weights"
                if (v === "equal") return "Equal Weight"
                if (v === "amounts") return "Custom Amounts"
                return v.replace(/_/g, " ")
            }).join(", ")
        }
        return String(val)
    }

    return (
        <div className="p-6 flex flex-col h-full space-y-6 text-sm">
            <div>
                <h2 className="text-xl font-bold tracking-tight">Review & Readiness Panel</h2>
                <p className="text-xs text-muted-foreground mt-1">
                    Pre-execution checklist. Review validation rules, data coverage margins, and configuration checks before running.
                </p>
            </div>

            {/* Top-Level Verdict Callout */}
            {isPreflighting ? (
                <div className="flex items-center space-x-3 p-4 border rounded-xl bg-muted/40 text-muted-foreground animate-pulse">
                    <Loader2 className="w-5 h-5 animate-spin text-primary shrink-0" />
                    <span className="font-medium text-sm">Performing engine preflight checklist & validating data snapshots...</span>
                </div>
            ) : preflightRes ? (
                <div className="space-y-4">
                    {/* Verdict Banner */}
                    {preflightRes.status === "green" && (
                        <div className="flex items-start space-x-3.5 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                            <CheckCircle2 className="w-5 h-5 mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-500" />
                            <div>
                                <span className="font-bold text-sm block">System Ready</span>
                                <span className="text-xs opacity-90 block mt-0.5">Strategy configuration passed all static checking tests and is ready for historical backtest run.</span>
                            </div>
                        </div>
                    )}
                    {preflightRes.status === "yellow" && (
                        <div className="flex items-start space-x-3.5 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-500">
                            <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0 text-amber-600 dark:text-amber-500" />
                            <div>
                                <span className="font-bold text-sm block">System Ready with Warnings</span>
                                <span className="text-xs opacity-90 block mt-0.5">Static checking completed with warnings. You can proceed with execution, but metrics may degrade.</span>
                                <ul className="list-disc pl-4 mt-2 space-y-1 text-xs opacity-90">
                                    {preflightRes.warnings.map((w: string, i: number) => (
                                        <li key={i}>{w}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    )}
                    {preflightRes.status === "red" && (
                        <div className="flex items-start space-x-3.5 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-700 dark:text-red-400">
                            <AlertCircle className="w-5 h-5 mt-0.5 shrink-0 text-red-600 dark:text-red-500" />
                            <div>
                                <span className="font-bold text-sm block">Cannot Run Simulation</span>
                                <span className="text-xs opacity-90 block mt-0.5">Validation engine reported critical errors in your configuration. Fix errors to continue.</span>
                                <ul className="list-disc pl-4 mt-2 space-y-1 text-xs opacity-90 font-mono">
                                    {preflightRes.errors.map((e: string, i: number) => (
                                        <li key={i}>{e}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    )}

                    {/* Preflight Stats & Info Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/* Timeline callout */}
                        <Card className="p-3.5 bg-card border shadow-sm">
                            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground mb-2">
                                <Calendar className="w-4 h-4 text-blue-500" /> Timeline Callout
                            </div>
                            <div className="space-y-1 text-xs font-mono">
                                <div><strong className="text-muted-foreground font-sans">Requested:</strong> {requestedStart} to {requestedEnd}</div>
                                <div className={isDateShifted ? "text-yellow-600 font-medium font-semibold" : "text-muted-foreground"}>
                                    <strong className="text-muted-foreground font-sans">Effective:</strong> {effectiveStart} to {effectiveEnd}
                                </div>
                                {isDateShifted && (
                                    <span className="text-[10px] bg-yellow-500/15 text-yellow-600 px-1 py-0.5 rounded font-medium mt-1 inline-block font-sans">Dates Shifted</span>
                                )}
                            </div>
                        </Card>

                        {/* Estimated Activity */}
                        <Card className="p-3.5 bg-card border shadow-sm">
                            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground mb-2">
                                <Activity className="w-4 h-4 text-indigo-500" /> Activity Metrics
                            </div>
                            <div className="space-y-1.5 text-xs font-medium">
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Trading Days:</span>
                                    <span>{preflightRes.estimated_trading_days ?? "N/A"}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Rebalances:</span>
                                    <span>{preflightRes.estimated_rebalance_count ?? "N/A"}</span>
                                </div>
                            </div>
                        </Card>

                        {/* Currency FX conversions */}
                        <Card className="p-3.5 bg-card border shadow-sm">
                            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground mb-2">
                                <Coins className="w-4 h-4 text-emerald-500" /> Required FX Pairs
                            </div>
                            {fxPairs.length === 0 ? (
                                <div className="text-xs text-muted-foreground pt-1">No cross-currency FX conversions required.</div>
                            ) : (
                                <div className="flex flex-wrap gap-1.5 pt-1">
                                    {fxPairs.map((pair: string) => (
                                        <Badge key={pair} variant="outline" className="font-mono text-[10px] bg-background">
                                            {pair}
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </Card>
                    </div>

                    {/* Dotted parameters capabilities / limitations (User facing copy, duplicate rows removed, no [object Object]) */}
                    {Object.keys(capabilities).length > 0 && (
                        <Card className="border bg-card shadow-sm p-4">
                            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5 border-b pb-2">
                                <Sliders className="w-3.5 h-3.5 text-purple-500" /> Strategy Capabilities & Constraints
                            </h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3.5 text-xs font-sans">
                                {Object.entries(capabilities)
                                    .filter(([key]) => !EXCLUDED_CAPABILITY_KEYS.has(key))
                                    .map(([key, val]) => (
                                        <div key={key} className="flex justify-between items-center py-1 border-b border-border/40">
                                            <span className="text-muted-foreground font-medium">{CAPABILITY_LABEL_MAP[key] || key.replace(/_/g, " ")}</span>
                                            <span className="font-bold text-foreground font-mono bg-muted/40 px-2 py-0.5 rounded text-[11px]">
                                                {getFormattedValue(key, val)}
                                            </span>
                                        </div>
                                    ))}
                            </div>
                        </Card>
                    )}

                    {/* Risk Flags Section */}
                    {preflightRes.risk_flags && preflightRes.risk_flags.length > 0 && (
                        <Card className="border border-border/85 bg-rose-50/5 dark:bg-rose-950/5 p-4 rounded-xl">
                            <h4 className="text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                                <ShieldAlert className="w-4 h-4 text-rose-500" /> Potential Risk Indicators
                            </h4>
                            <div className="space-y-2">
                                {preflightRes.risk_flags.map((flag, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-xs">
                                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase shrink-0 ${flag.severity === "error" ? "bg-red-500/10 text-red-600 border border-red-500/20" : "bg-yellow-500/10 text-yellow-600 border border-yellow-500/20"}`}>
                                            {flag.severity}
                                        </span>
                                        <div>
                                            <span className="font-bold text-foreground font-mono text-[11px] block">{flag.code}</span>
                                            <span className="text-muted-foreground text-xs mt-0.5 block">{flag.message}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    )}

                    {/* Data Coverage Table */}
                    <Card className="border bg-card shadow-sm overflow-hidden">
                        <div className="px-4 py-3 bg-muted/40 border-b border-border/60">
                            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                                <Globe className="w-3.5 h-3.5 text-blue-500" /> Historical Data Coverage Snapshot
                            </h4>
                        </div>
                        <div className="overflow-x-auto">
                            {dataCoverage.length === 0 ? (
                                <div className="p-6 text-center text-xs text-muted-foreground">
                                    No custom symbol coverage data emitted by validation engine.
                                </div>
                            ) : (
                                <table className="w-full text-xs text-left">
                                    <thead className="bg-muted/50 border-b border-border/50 text-[10px] font-semibold text-muted-foreground uppercase">
                                        <tr>
                                            <th className="px-4 py-2.5">Symbol</th>
                                            <th className="px-4 py-2.5">Source Coverage Start</th>
                                            <th className="px-4 py-2.5">Source Coverage End</th>
                                            <th className="px-4 py-2.5 text-right">Coverage %</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border/40 font-mono">
                                        {dataCoverage.map((item: any, idx: number) => (
                                            <tr key={idx} className="hover:bg-muted/20">
                                                <td className="px-4 py-2 font-bold text-foreground">{item.symbol}</td>
                                                <td className="px-4 py-2 text-muted-foreground">
                                                    {item.first_date || item.start_date || item.coverage_start || "-"}
                                                </td>
                                                <td className="px-4 py-2 text-muted-foreground">
                                                    {item.last_date || item.end_date || item.coverage_end || "-"}
                                                </td>
                                                <td className="px-4 py-2 text-right">
                                                    <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-bold ${
                                                        (item.coverage_pct ?? 1.0) >= 0.95 ? "bg-emerald-500/10 text-emerald-600" :
                                                        (item.coverage_pct ?? 1.0) >= 0.80 ? "bg-amber-500/10 text-amber-600" :
                                                        "bg-rose-500/10 text-rose-600"
                                                    }`}>
                                                        {((item.coverage_pct ?? 1.0) * 100).toFixed(1)}%
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </Card>
                </div>
            ) : null}

            {/* Raw JSON details collapsible */}
            <details className="group border rounded-lg bg-muted/10 overflow-hidden">
                <summary className="flex items-center justify-between p-3 font-semibold text-xs text-muted-foreground cursor-pointer select-none hover:bg-muted/20">
                    <span>View Configuration & Raw Preflight JSON</span>
                    <ChevronDown className="w-4 h-4 transition-transform group-open:rotate-180" />
                </summary>
                <div className="p-3 border-t bg-muted/30 font-mono text-[11px] overflow-auto max-h-[300px] divide-y space-y-4">
                    <div className="pt-2">
                        <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1.5">Strategy Config Snapshot</div>
                        <pre>{JSON.stringify(validConfig, null, 2)}</pre>
                    </div>
                    {preflightRes && (
                        <div className="pt-4">
                            <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1.5">Raw Preflight Output</div>
                            <pre>{JSON.stringify(preflightRes, null, 2)}</pre>
                        </div>
                    )}
                </div>
            </details>

            {error && (
                <div className="p-3.5 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-md">
                    {error}
                </div>
            )}

            {/* Stepper Footer Controls */}
            <div className="mt-8 flex items-center justify-between pt-4 border-t border-border">
                <Button variant="outline" onClick={prevStep} disabled={isSubmitting}>Back</Button>
                <div className="flex items-center space-x-4">
                    {isSubmitting && <span className="text-xs text-muted-foreground animate-pulse">Running historical simulation...</span>}
                    <Button 
                        onClick={handleRun} 
                        disabled={isSubmitting || isPreflighting || preflightRes?.status === "red"}
                        className="bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/95 hover:to-indigo-600/95"
                    >
                        {isSubmitting ? "Running..." : "Run Strategy"}
                    </Button>
                </div>
            </div>
        </div>
    )
}

function Card({ className, children }: { className?: string; children: React.ReactNode }) {
    return (
        <div className={`rounded-xl border border-border bg-card text-card-foreground shadow-sm ${className}`}>
            {children}
        </div>
    )
}

function Loader2({ className }: { className?: string }) {
    return (
        <svg className={`animate-spin ${className}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
    )
}
