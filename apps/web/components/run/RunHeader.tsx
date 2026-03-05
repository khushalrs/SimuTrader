"use client"

import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { AlertCircle, Share, Download, Check } from "lucide-react"

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { getRunPositions, getRunFills, RunEquityPoint } from "@/lib/api"

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
    const [isCopied, setIsCopied] = useState(false)
    const [isExporting, setIsExporting] = useState(false)

    const isShifted = requestedStart && effectiveStart && (requestedStart !== effectiveStart || requestedEnd !== effectiveEnd);

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
                <div className="flex items-center gap-2">
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
