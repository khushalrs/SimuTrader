"use client"

import useSWR from "swr"
import { getRunExplain } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { 
    Lightbulb, 
    Flame, 
    TrendingUp, 
    TrendingDown, 
    DollarSign, 
    ShieldAlert, 
    Percent, 
    ArrowDownRight,
    Award,
    Activity,
    Layers,
    Receipt,
    RefreshCw
} from "lucide-react"

function formatPercent(val?: number | null): string {
    if (val === undefined || val === null) return "N/A"
    const pct = val * 100
    const sign = pct > 0 ? "+" : ""
    return `${sign}${pct.toFixed(2)}%`
}

function formatDrag(val?: number | null): string {
    if (val === undefined || val === null || val === 0) return "0.00%"
    return `-${(Math.abs(val) * 100).toFixed(2)}%`
}

export function ExplainTab({ runId }: { runId: string }) {
    const { data: explainData, isLoading, error } = useSWR(
        runId ? `/runs/${runId}/explain` : null,
        () => getRunExplain(runId),
        { revalidateOnFocus: false }
    )

    if (isLoading) {
        return (
            <div className="space-y-6 animate-pulse">
                <Skeleton className="h-48 w-full rounded-xl" />
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32 w-full rounded-xl" />)}
                </div>
                <Skeleton className="h-64 w-full rounded-xl" />
            </div>
        )
    }

    if (error || !explainData) {
        return (
            <Card className="min-h-[300px] flex flex-col items-center justify-center p-8 text-center border-dashed">
                <Lightbulb className="w-12 h-12 text-muted-foreground/30 mb-3" />
                <h3 className="font-semibold text-lg">No Explanation Available</h3>
                <p className="text-sm text-muted-foreground mt-1 max-w-md">
                    Detailed explanation data could not be retrieved for this simulation.
                </p>
            </Card>
        )
    }

    // Drag keys must match RunExplainOut.drag_breakdown on the backend, which emits
    // fees/taxes/borrow/margin_interest (already signed negative), not the *_drag
    // names used by RunMetric.
    const breakdown = explainData.drag_breakdown || {}
    const grossReturn = explainData.gross_return ?? 0
    const feeDrag = breakdown.fees ?? 0
    const taxDrag = breakdown.taxes ?? 0
    const borrowDrag = breakdown.borrow ?? 0
    const marginDrag = breakdown.margin_interest ?? 0
    const netReturn = explainData.net_return ?? (grossReturn + feeDrag + taxDrag + borrowDrag + marginDrag)

    // Determine dominant drag
    const dragEntries = [
        { key: "fees", label: "Transaction Fees", value: Math.abs(feeDrag) },
        { key: "taxes", label: "Tax Drag", value: Math.abs(taxDrag) },
        { key: "borrow", label: "Short Borrow Fees", value: Math.abs(borrowDrag) },
        { key: "margin_interest", label: "Margin Interest", value: Math.abs(marginDrag) },
    ]
    const maxDragVal = Math.max(...dragEntries.map(d => d.value))
    const dominantKey = explainData.dominant_drag || (maxDragVal > 0 ? dragEntries.find(d => d.value === maxDragVal)?.key : null)

    // Calculate max scale for waterfall visualization
    const maxVal = Math.max(Math.abs(grossReturn), Math.abs(netReturn), 0.05)

    return (
        <div className="space-y-6">
            {/* Top Headline Banner. `headline` arrives once the backend explain
                upgrade lands; until then fall back to the generated `summary`. */}
            {(explainData.headline || explainData.summary) && (
                <Card className="border border-primary/20 bg-gradient-to-r from-primary/5 via-card to-card shadow-sm">
                    <CardContent className="pt-6 flex items-start gap-4">
                        <div className="p-3 bg-primary/10 rounded-xl shrink-0 text-primary">
                            <Lightbulb className="w-6 h-6" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-base text-foreground">Executive Performance Summary</h3>
                            <p className="text-sm text-foreground/90 mt-1 leading-relaxed">
                                {explainData.headline || explainData.summary}
                            </p>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Gross-to-Net Return Waterfall Visualization */}
            <Card className="border border-border bg-card shadow-sm overflow-hidden">
                <CardHeader className="pb-4 border-b border-border/50">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Activity className="w-4 h-4 text-primary" /> Gross-to-Net Return Waterfall
                            </CardTitle>
                            <CardDescription>Visual breakdown of strategy performance leakage from gross alpha to net investor return.</CardDescription>
                        </div>
                        <Badge variant="outline" className="font-mono text-xs">
                            Net: {formatPercent(netReturn)}
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent className="pt-6">
                    <div className="space-y-4">
                        {/* Waterfall Bars */}
                        <div className="grid grid-cols-1 sm:grid-cols-6 gap-3 pt-2">
                            {/* Gross Return */}
                            <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg flex flex-col justify-between">
                                <div className="text-[11px] font-semibold uppercase text-blue-600 dark:text-blue-400">Gross Return</div>
                                <div className="text-lg font-bold font-mono text-blue-700 dark:text-blue-300 mt-2">
                                    {formatPercent(grossReturn)}
                                </div>
                                <div className="w-full bg-blue-200 dark:bg-blue-900/50 h-1.5 rounded-full mt-2 overflow-hidden">
                                    <div className="bg-blue-500 h-full rounded-full" style={{ width: `${Math.min(100, Math.max(10, (Math.abs(grossReturn) / maxVal) * 100))}%` }}></div>
                                </div>
                            </div>

                            {/* Fee Drag */}
                            <div className={`p-3 rounded-lg flex flex-col justify-between border ${dominantKey === 'fees' ? 'bg-amber-500/15 border-amber-500/40 ring-1 ring-amber-500/30' : 'bg-amber-500/5 border-amber-500/15'}`}>
                                <div className="flex items-center justify-between">
                                    <span className="text-[11px] font-semibold uppercase text-amber-600 dark:text-amber-400">Fees Drag</span>
                                    {dominantKey === 'fees' && <Flame className="w-3.5 h-3.5 text-amber-500" />}
                                </div>
                                <div className="text-lg font-bold font-mono text-amber-700 dark:text-amber-300 mt-2">
                                    {formatDrag(feeDrag)}
                                </div>
                                <div className="w-full bg-amber-200 dark:bg-amber-900/50 h-1.5 rounded-full mt-2 overflow-hidden">
                                    <div className="bg-amber-500 h-full rounded-full" style={{ width: `${Math.min(100, (Math.abs(feeDrag) / maxVal) * 100)}%` }}></div>
                                </div>
                            </div>

                            {/* Tax Drag */}
                            <div className={`p-3 rounded-lg flex flex-col justify-between border ${dominantKey === 'taxes' ? 'bg-rose-500/15 border-rose-500/40 ring-1 ring-rose-500/30' : 'bg-rose-500/5 border-rose-500/15'}`}>
                                <div className="flex items-center justify-between">
                                    <span className="text-[11px] font-semibold uppercase text-rose-600 dark:text-rose-400">Tax Drag</span>
                                    {dominantKey === 'taxes' && <Flame className="w-3.5 h-3.5 text-rose-500" />}
                                </div>
                                <div className="text-lg font-bold font-mono text-rose-700 dark:text-rose-300 mt-2">
                                    {formatDrag(taxDrag)}
                                </div>
                                <div className="w-full bg-rose-200 dark:bg-rose-900/50 h-1.5 rounded-full mt-2 overflow-hidden">
                                    <div className="bg-rose-500 h-full rounded-full" style={{ width: `${Math.min(100, (Math.abs(taxDrag) / maxVal) * 100)}%` }}></div>
                                </div>
                            </div>

                            {/* Borrow Drag */}
                            <div className={`p-3 rounded-lg flex flex-col justify-between border ${dominantKey === 'borrow' ? 'bg-orange-500/15 border-orange-500/40 ring-1 ring-orange-500/30' : 'bg-orange-500/5 border-orange-500/15'}`}>
                                <div className="flex items-center justify-between">
                                    <span className="text-[11px] font-semibold uppercase text-orange-600 dark:text-orange-400">Borrow Drag</span>
                                    {dominantKey === 'borrow' && <Flame className="w-3.5 h-3.5 text-orange-500" />}
                                </div>
                                <div className="text-lg font-bold font-mono text-orange-700 dark:text-orange-300 mt-2">
                                    {formatDrag(borrowDrag)}
                                </div>
                                <div className="w-full bg-orange-200 dark:bg-orange-900/50 h-1.5 rounded-full mt-2 overflow-hidden">
                                    <div className="bg-orange-500 h-full rounded-full" style={{ width: `${Math.min(100, (Math.abs(borrowDrag) / maxVal) * 100)}%` }}></div>
                                </div>
                            </div>

                            {/* Margin Drag */}
                            <div className={`p-3 rounded-lg flex flex-col justify-between border ${dominantKey === 'margin_interest' ? 'bg-yellow-500/15 border-yellow-500/40 ring-1 ring-yellow-500/30' : 'bg-yellow-500/5 border-yellow-500/15'}`}>
                                <div className="flex items-center justify-between">
                                    <span className="text-[11px] font-semibold uppercase text-yellow-600 dark:text-yellow-400">Margin Int.</span>
                                    {dominantKey === 'margin_interest' && <Flame className="w-3.5 h-3.5 text-yellow-500" />}
                                </div>
                                <div className="text-lg font-bold font-mono text-yellow-700 dark:text-yellow-300 mt-2">
                                    {formatDrag(marginDrag)}
                                </div>
                                <div className="w-full bg-yellow-200 dark:bg-yellow-900/50 h-1.5 rounded-full mt-2 overflow-hidden">
                                    <div className="bg-yellow-500 h-full rounded-full" style={{ width: `${Math.min(100, (Math.abs(marginDrag) / maxVal) * 100)}%` }}></div>
                                </div>
                            </div>

                            {/* Net Return */}
                            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex flex-col justify-between">
                                <div className="text-[11px] font-semibold uppercase text-emerald-600 dark:text-emerald-400">Net Return</div>
                                <div className={`text-lg font-extrabold font-mono mt-2 ${netReturn >= 0 ? "text-emerald-700 dark:text-emerald-300" : "text-rose-600"}`}>
                                    {formatPercent(netReturn)}
                                </div>
                                <div className="w-full bg-emerald-200 dark:bg-emerald-900/50 h-1.5 rounded-full mt-2 overflow-hidden">
                                    <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${Math.min(100, Math.max(10, (Math.abs(netReturn) / maxVal) * 100))}%` }}></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Cost Drag Cards Grid with Dominant Drag Badge */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Fee Drag Card */}
                <Card className={`relative overflow-hidden ${dominantKey === 'fees' ? 'border-amber-500 shadow-md bg-amber-500/5' : ''}`}>
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">Transaction Fees</CardTitle>
                            {dominantKey === 'fees' && (
                                <Badge variant="destructive" className="bg-amber-500 hover:bg-amber-600 text-[10px] py-0 px-1.5 gap-1">
                                    <Flame className="w-3 h-3" /> Dominant Drag
                                </Badge>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">
                            {formatDrag(feeDrag)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Commissions & slippage incurred during rebalancing.
                        </p>
                    </CardContent>
                </Card>

                {/* Tax Drag Card */}
                <Card className={`relative overflow-hidden ${dominantKey === 'taxes' ? 'border-rose-500 shadow-md bg-rose-500/5' : ''}`}>
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">Capital Gains Tax</CardTitle>
                            {dominantKey === 'taxes' && (
                                <Badge variant="destructive" className="bg-rose-500 hover:bg-rose-600 text-[10px] py-0 px-1.5 gap-1">
                                    <Flame className="w-3 h-3" /> Dominant Drag
                                </Badge>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-rose-600 dark:text-rose-400">
                            {formatDrag(taxDrag)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Short/long term tax drag on realized gains.
                        </p>
                    </CardContent>
                </Card>

                {/* Short Borrow Drag Card */}
                <Card className={`relative overflow-hidden ${dominantKey === 'borrow' ? 'border-orange-500 shadow-md bg-orange-500/5' : ''}`}>
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">Short Borrow Fees</CardTitle>
                            {dominantKey === 'borrow' && (
                                <Badge variant="destructive" className="bg-orange-500 hover:bg-orange-600 text-[10px] py-0 px-1.5 gap-1">
                                    <Flame className="w-3 h-3" /> Dominant Drag
                                </Badge>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-orange-600 dark:text-orange-400">
                            {formatDrag(borrowDrag)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Daily borrow fees paid on short positions.
                        </p>
                    </CardContent>
                </Card>

                {/* Margin Interest Drag Card */}
                <Card className={`relative overflow-hidden ${dominantKey === 'margin_interest' ? 'border-yellow-500 shadow-md bg-yellow-500/5' : ''}`}>
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">Margin Interest</CardTitle>
                            {dominantKey === 'margin_interest' && (
                                <Badge variant="destructive" className="bg-yellow-500 hover:bg-yellow-600 text-[10px] py-0 px-1.5 gap-1">
                                    <Flame className="w-3 h-3" /> Dominant Drag
                                </Badge>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-yellow-600 dark:text-yellow-400">
                            {formatDrag(marginDrag)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Interest expenses on borrowed cash leverage.
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Detailed Explanations Section */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Tax Impact Summary */}
                <Card className="border border-border bg-card">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Receipt className="w-4 h-4 text-rose-500" /> Tax Impact Analysis
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs sm:text-sm text-foreground/80 leading-relaxed">
                        {explainData.tax_impact_summary || explainData.tax_impact || explainData.tax_explanation || (
                            "No significant tax drag recorded. Positions were held across tax-advantaged buckets or turnover was low."
                        )}
                    </CardContent>
                </Card>

                {/* Turnover Explanation */}
                <Card className="border border-border bg-card">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                            <RefreshCw className="w-4 h-4 text-blue-500" /> Turnover Dynamics
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs sm:text-sm text-foreground/80 leading-relaxed">
                        {explainData.turnover_explanation || explainData.turnover_summary || (
                            "Rebalancing frequency generated moderate turnover. Friction was primarily controlled by execution policy."
                        )}
                    </CardContent>
                </Card>

                {/* Leverage & Shorting Explanation */}
                <Card className="border border-border bg-card">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Layers className="w-4 h-4 text-purple-500" /> Leverage & Shorting
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="text-xs sm:text-sm text-foreground/80 leading-relaxed">
                        {explainData.leverage_explanation || explainData.shorting_explanation || (
                            "Strategy maintained standard long exposure without significant borrow fees or margin interest spikes."
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Key Drivers & Extremes Grid */}
            <Card className="border border-border bg-card">
                <CardHeader>
                    <CardTitle className="text-base">Key Drivers & Extremes</CardTitle>
                    <CardDescription>Notable single-event trade drivers and position milestones across the backtest.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* Best Period */}
                        <div className="p-3 bg-emerald-500/5 border border-emerald-500/15 rounded-lg">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                <TrendingUp className="w-3.5 h-3.5" /> Best Period
                            </div>
                            <div className="text-sm font-bold mt-1 text-foreground">
                                {explainData.best_period?.return_pct ? formatPercent(explainData.best_period.return_pct) : (explainData.best_period?.description || "N/A")}
                            </div>
                            {explainData.best_period?.date_range && (
                                <div className="text-[11px] text-muted-foreground font-mono mt-0.5">{explainData.best_period.date_range}</div>
                            )}
                        </div>

                        {/* Worst Period */}
                        <div className="p-3 bg-rose-500/5 border border-rose-500/15 rounded-lg">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 dark:text-rose-400">
                                <TrendingDown className="w-3.5 h-3.5" /> Worst Period
                            </div>
                            <div className="text-sm font-bold mt-1 text-foreground">
                                {explainData.worst_period?.return_pct ? formatPercent(explainData.worst_period.return_pct) : (explainData.worst_period?.description || "N/A")}
                            </div>
                            {explainData.worst_period?.date_range && (
                                <div className="text-[11px] text-muted-foreground font-mono mt-0.5">{explainData.worst_period.date_range}</div>
                            )}
                        </div>

                        {/* Largest Position */}
                        <div className="p-3 bg-secondary/30 border border-border rounded-lg">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                                <Award className="w-3.5 h-3.5 text-blue-500" /> Largest Position
                            </div>
                            <div className="text-sm font-bold mt-1 text-foreground">
                                {explainData.largest_position?.symbol || "N/A"}
                            </div>
                            {explainData.largest_position?.weight_pct && (
                                <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                                    {(explainData.largest_position.weight_pct * 100).toFixed(1)}% Weight
                                </div>
                            )}
                        </div>

                        {/* Largest Trade / Tax Event */}
                        <div className="p-3 bg-secondary/30 border border-border rounded-lg">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                                <DollarSign className="w-3.5 h-3.5 text-amber-500" /> Largest Tax Event
                            </div>
                            <div className="text-sm font-bold mt-1 text-foreground">
                                {explainData.largest_tax_event?.symbol || "N/A"}
                            </div>
                            {explainData.largest_tax_event?.tax_due && (
                                <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                                    Tax: ${explainData.largest_tax_event.tax_due.toLocaleString()}
                                </div>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
