"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { AlertCircle, Share, Download, Check, Sparkles, Loader2, ArrowRight } from "lucide-react"

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { getRunPositions, getRunFills, createRunScenario, getRunStatus, RunEquityPoint } from "@/lib/api"

function downloadBlob(content: string, filename: string, contentType: string) {
    const blob = new Blob([content], { type: contentType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
}

function exportConfigJSON(runId: string, config: any) {
    const json = JSON.stringify(config, null, 2)
    downloadBlob(json, `run_${runId}_config.json`, "application/json")
}

function exportEquityCSV(runId: string, equity: RunEquityPoint[]) {
    if (!equity || equity.length === 0) return;
    const headers = ["date", "equity_base", "gross_exposure_base", "net_exposure_base", "drawdown", "fees_cum_base", "taxes_cum_base", "borrow_fees_cum_base", "margin_interest_cum_base"];
    const rows = equity.map(e => [
        e.date,
        e.value,
        e.gross_exposure_base || 0,
        e.net_exposure_base || 0,
        e.drawdown || 0,
        e.fees_cum_base || 0,
        e.taxes_cum_base || 0,
        e.borrow_fees_cum_base || 0,
        e.margin_interest_cum_base || 0
    ].join(","));
    downloadBlob([headers.join(","), ...rows].join("\n"), `run_${runId}_equity.csv`, "text/csv");
}

interface RunHeaderProps {
    runId: string
    title: string
    tags: string[]
    date: string
    requestedStart?: string
    requestedEnd?: string
    effectiveStart?: string
    effectiveEnd?: string
    configSnapshot?: any
    equity?: RunEquityPoint[]
}

export function RunHeader({ runId, title, tags, date, requestedStart, requestedEnd, effectiveStart, effectiveEnd, configSnapshot, equity }: RunHeaderProps) {
    const router = useRouter()
    const [isCopied, setIsCopied] = useState(false)
    const [isExporting, setIsExporting] = useState(false)

    // Form inputs for Scenario override
    const [scenarioOpen, setScenarioOpen] = useState(false)
    const [taxRegime, setTaxRegime] = useState(configSnapshot?.tax?.regime || configSnapshot?.tax_regime || "USA")
    const [commissionBps, setCommissionBps] = useState(String(configSnapshot?.execution?.commission?.bps ?? configSnapshot?.commission?.bps ?? 5))
    const [slippageBps, setSlippageBps] = useState(String(configSnapshot?.execution?.slippage?.bps ?? configSnapshot?.slippage?.bps ?? 10))
    const [initialCash, setInitialCash] = useState(String(configSnapshot?.backtest?.initial_cash ?? 100000))
    const [startDate, setStartDate] = useState(configSnapshot?.backtest?.start_date || requestedStart || "")
    const [endDate, setEndDate] = useState(configSnapshot?.backtest?.end_date || requestedEnd || "")
    const [rebalanceFreq, setRebalanceFreq] = useState(configSnapshot?.backtest?.contributions?.frequency || configSnapshot?.rebalance_frequency || "DAILY")

    // Polling states
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [pollingStatus, setPollingStatus] = useState("")

    const isShifted = requestedStart && effectiveStart && (requestedStart !== effectiveStart || requestedEnd !== effectiveEnd);

    // Lineage from Scenario
    const scenario = configSnapshot?._scenario
    const parentRunId = scenario?.base_run_id
    const parentRunName = scenario?.base_run_name || "Parent Run"
    const parentOverrides = scenario?.overrides || {}

    const handleShare = () => {
        navigator.clipboard.writeText(window.location.href)
        setIsCopied(true)
        setTimeout(() => setIsCopied(false), 2000)
    }

    const handleExportPositions = async () => {
        setIsExporting(true)
        try {
            const positions = await getRunPositions(runId)
            const headers = ["date", "symbol", "qty", "avg_cost_native", "market_value_base", "unrealized_pnl_base", "weight"]
            const rows = positions.map(p => [p.date, p.symbol, p.qty, p.avg_cost_native, p.market_value_base, p.unrealized_pnl_base, p.weight].join(","))
            downloadBlob([headers.join(","), ...rows].join("\n"), `run_${runId}_positions.csv`, "text/csv")
        } catch (e) { console.error(e) }
        setIsExporting(false)
    }

    const handleExportFills = async () => {
        setIsExporting(true)
        try {
            const fills = await getRunFills(runId)
            const headers = ["date", "symbol", "side", "qty", "price", "notional", "commission", "slippage"]
            const rows = fills.map(f => [f.date, f.symbol, f.side, f.qty, f.price, f.notional, f.commission, f.slippage].join(","))
            downloadBlob([headers.join(","), ...rows].join("\n"), `run_${runId}_fills.csv`, "text/csv")
        } catch (e) { console.error(e) }
        setIsExporting(false)
    }

    const handleCreateScenario = async () => {
        setIsSubmitting(true)
        setPollingStatus("Creating simulation scenario...")

        const payload = {
            tax_regime: taxRegime,
            commission_bps: parseFloat(commissionBps) || 0,
            slippage_bps: parseFloat(slippageBps) || 0,
            initial_cash: parseFloat(initialCash) || 0,
            start_date: startDate,
            end_date: endDate,
            rebalance_frequency: rebalanceFreq,
            strategy_params: configSnapshot?.strategy_params || configSnapshot?.strategy?.params || {}
        }

        try {
            const result = await createRunScenario(runId, payload)
            const newRunId = result.run_id

            if (!newRunId) {
                throw new Error("No run ID returned from scenario engine.")
            }

            // Start status polling
            setPollingStatus("Scenario initiated. Polling backtester status...")
            const interval = setInterval(async () => {
                try {
                    const statusRes = await getRunStatus(newRunId)
                    if (statusRes) {
                        setPollingStatus(`Simulation is ${statusRes.status.toLowerCase()}...`)
                        if (statusRes.status === "SUCCEEDED") {
                            clearInterval(interval)
                            setIsSubmitting(false)
                            setScenarioOpen(false)
                            router.push(`/compare?base=${runId}&runs=${newRunId}`)
                        } else if (statusRes.status === "FAILED") {
                            clearInterval(interval)
                            setIsSubmitting(false)
                            setPollingStatus(`Simulation failed: ${statusRes.error_message_public || "Internal error"}`)
                        }
                    }
                } catch (e: any) {
                    clearInterval(interval)
                    setIsSubmitting(false)
                    setPollingStatus(`Failed to poll status: ${e.message}`)
                }
            }, 1000)
        } catch (e: any) {
            setIsSubmitting(false)
            setPollingStatus(`Error: ${e.message}`)
        }
    }

    return (
        <div className="space-y-4">
            {isShifted && (
                <div className="flex items-center gap-3 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-3 text-sm text-yellow-600 dark:text-yellow-500">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <p>
                        <strong>Date Range Adjusted: </strong>
                        Requested <code>{requestedStart}</code> to <code>{requestedEnd}</code>;
                        executed on <code>{effectiveStart}</code> to <code>{effectiveEnd}</code>.
                    </p>
                </div>
            )}

            {/* Lineage lineage banner */}
            {parentRunId && (
                <div className="flex flex-wrap items-center gap-2 p-3 bg-muted/40 border border-border rounded-lg text-xs font-medium text-foreground/80">
                    <span className="flex items-center gap-1">🌿 <strong>Scenario Lineage:</strong> Derived from</span>
                    <a href={`/runs/${parentRunId}`} className="text-primary hover:underline font-mono font-bold">
                        {parentRunName}
                    </a>
                    {Object.keys(parentOverrides).length > 0 && (
                        <>
                            <span>with modifications:</span>
                            <div className="flex gap-1 flex-wrap">
                                {Object.entries(parentOverrides).map(([key, val]) => (
                                    <Badge key={key} variant="outline" className="text-[10px] font-mono py-0.5 px-1.5 bg-background">
                                        {key}: {String(val)}
                                    </Badge>
                                ))}
                            </div>
                        </>
                    )}
                </div>
            )}

            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
                        <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">{runId}</Badge>
                        {isShifted && <Badge variant="secondary" className="bg-yellow-500/10 text-yellow-600 hover:bg-yellow-500/20 border-yellow-500/20">Dates Shifted</Badge>}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>{date}</span>
                        <span>•</span>
                        <div className="flex gap-1">
                            {tags.map(tag => (
                                <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                    {/* Create Scenario Dialog */}
                    <Dialog open={scenarioOpen} onOpenChange={(open) => { if (!isSubmitting) setScenarioOpen(open) }}>
                        <DialogTrigger asChild>
                            <Button variant="default" size="sm" className="bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/95 hover:to-indigo-600/95 gap-1.5 shadow-sm">
                                <Sparkles className="w-4 h-4" />
                                Create Scenario
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
                            <DialogHeader>
                                <DialogTitle className="flex items-center gap-1.5">
                                    <Sparkles className="w-5 h-5 text-primary" /> Create Simulation Scenario
                                </DialogTitle>
                                <DialogDescription>
                                    Create a daughter backtest scenario by modifying configuration parameters. After execution completes, you'll auto-compare results.
                                </DialogDescription>
                            </DialogHeader>

                            {isSubmitting ? (
                                <div className="py-12 flex flex-col items-center justify-center gap-4 text-center">
                                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                                    <p className="font-medium text-sm text-muted-foreground">{pollingStatus}</p>
                                </div>
                            ) : (
                                <div className="space-y-4 py-2 text-sm">
                                    {/* Tax Regime Selector */}
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold uppercase text-muted-foreground">Tax Regime</label>
                                        <select 
                                            value={taxRegime} 
                                            onChange={(e) => setTaxRegime(e.target.value)}
                                            className="w-full border rounded-md p-2 bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                        >
                                            <option value="USA">USA (Standard tax buckets)</option>
                                            <option value="INDIA">INDIA (Standard LTCG/STCG)</option>
                                            <option value="GERMANY">GERMANY (Abgeltungsteuer Flat)</option>
                                            <option value="NONE">NONE (Tax-advantaged account)</option>
                                        </select>
                                    </div>

                                    {/* Commission / Slippage Grid */}
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-semibold uppercase text-muted-foreground">Commission (BPS)</label>
                                            <input 
                                                type="number"
                                                value={commissionBps}
                                                onChange={(e) => setCommissionBps(e.target.value)}
                                                className="w-full border rounded-md p-2 bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                            />
                                        </div>
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-semibold uppercase text-muted-foreground">Slippage (BPS)</label>
                                            <input 
                                                type="number"
                                                value={slippageBps}
                                                onChange={(e) => setSlippageBps(e.target.value)}
                                                className="w-full border rounded-md p-2 bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                            />
                                        </div>
                                    </div>

                                    {/* Initial Cash */}
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold uppercase text-muted-foreground">Initial Cash (Base Currency)</label>
                                        <input 
                                            type="number"
                                            value={initialCash}
                                            onChange={(e) => setInitialCash(e.target.value)}
                                            className="w-full border rounded-md p-2 bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                        />
                                    </div>

                                    {/* Dates Grid */}
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-semibold uppercase text-muted-foreground">Start Date</label>
                                            <input 
                                                type="date"
                                                value={startDate}
                                                onChange={(e) => setStartDate(e.target.value)}
                                                className="w-full border rounded-md p-2 bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                            />
                                        </div>
                                        <div className="space-y-1.5">
                                            <label className="text-xs font-semibold uppercase text-muted-foreground">End Date</label>
                                            <input 
                                                type="date"
                                                value={endDate}
                                                onChange={(e) => setEndDate(e.target.value)}
                                                className="w-full border rounded-md p-2 bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                            />
                                        </div>
                                    </div>

                                    {/* Rebalance Frequency */}
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold uppercase text-muted-foreground">Rebalance Frequency</label>
                                        <select 
                                            value={rebalanceFreq} 
                                            onChange={(e) => setRebalanceFreq(e.target.value)}
                                            className="w-full border rounded-md p-2 bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                                        >
                                            <option value="DAILY">Daily</option>
                                            <option value="WEEKLY">Weekly</option>
                                            <option value="MONTHLY">Monthly</option>
                                            <option value="QUARTERLY">Quarterly</option>
                                        </select>
                                    </div>

                                    {pollingStatus && (
                                        <p className="text-xs text-rose-500 font-medium">{pollingStatus}</p>
                                    )}

                                    <div className="pt-4 flex items-center justify-end gap-2">
                                        <Button variant="outline" onClick={() => setScenarioOpen(false)}>
                                            Cancel
                                        </Button>
                                        <Button onClick={handleCreateScenario} className="gap-1.5">
                                            Run Scenario <ArrowRight className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </DialogContent>
                    </Dialog>

                    <Button variant="outline" size="sm" onClick={handleShare}>
                        {isCopied ? <Check className="mr-2 h-4 w-4 text-green-500" /> : <Share className="mr-2 h-4 w-4" />}
                        {isCopied ? "Copied!" : "Share"}
                    </Button>
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" size="sm">
                                <Download className="mr-2 h-4 w-4" />
                                Export
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Export Run Data</DialogTitle>
                                <DialogDescription>
                                    Download data from this run in various formats.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                                <Button variant="outline" onClick={() => exportConfigJSON(runId, configSnapshot || {})}>
                                    Download Config (JSON)
                                </Button>
                                <Button variant="outline" onClick={() => exportEquityCSV(runId, equity || [])} disabled={!equity || equity.length === 0}>
                                    Download Equity Timeseries (CSV)
                                </Button>
                                <Button variant="outline" onClick={handleExportPositions} disabled={isExporting}>
                                    {isExporting ? "Exporting..." : "Download Final Positions (CSV)"}
                                </Button>
                                <Button variant="outline" onClick={handleExportFills} disabled={isExporting}>
                                    {isExporting ? "Exporting..." : "Download All Trades (CSV)"}
                                </Button>
                            </div>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>
            <Separator />
        </div>
    )
}
