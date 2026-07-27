"use client"

import { useState, useMemo } from "react"
import useSWR from "swr"
import { getRunFills, RunFillOut, buildTradeTraceFromFill } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatCurrency } from "@/lib/utils"
import {
    Activity,
    CheckCircle2,
    ArrowRight,
    ShieldCheck,
    DollarSign,
    Receipt,
    Layers,
    Sliders,
    Zap
} from "lucide-react"

interface SignalPipelineTimelineProps {
    runId: string
    baseCurrency?: string
}

export function SignalPipelineTimeline({ runId, baseCurrency = "USD" }: SignalPipelineTimelineProps) {
    const { data: fills } = useSWR<RunFillOut[]>(
        runId ? `/runs/${runId}/fills?limit=1000` : null,
        () => getRunFills(runId, undefined, undefined, 1000, 0),
        { revalidateOnFocus: false }
    )

    const [selectedFillIndex, setSelectedFillIndex] = useState<number>(0)

    const trace = useMemo(() => {
        if (!fills || fills.length === 0) return null
        const fill = fills[Math.min(selectedFillIndex, fills.length - 1)]
        return buildTradeTraceFromFill(fill)
    }, [fills, selectedFillIndex])

    if (!fills || fills.length === 0 || !trace) {
        return (
            <Card className="p-8 text-center text-muted-foreground border-dashed">
                <Zap className="w-10 h-10 mx-auto mb-2 opacity-40" />
                No execution fills recorded for pipeline timeline visualization.
            </Card>
        )
    }

    const isBuy = trace.side === "BUY"

    return (
        <Card className="border border-border shadow-sm">
            <CardHeader className="pb-3 border-b border-border/40 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <CardTitle className="text-base font-bold flex items-center gap-2">
                        <Zap className="w-4 h-4 text-primary" /> Signal \(\rightarrow\) Order \(\rightarrow\) Fill Pipeline Timeline
                    </CardTitle>
                    <CardDescription className="text-xs">
                        Horizontal decision & execution lifecycle connecting signal, intent, constraints, fill, and tax lot.
                    </CardDescription>
                </div>

                <div className="flex items-center gap-2">
                    <Label className="text-xs text-muted-foreground">Select Trade Fill:</Label>
                    <Select
                        value={String(selectedFillIndex)}
                        onValueChange={v => setSelectedFillIndex(Number(v))}
                    >
                        <SelectTrigger className="h-8 text-xs font-mono w-56">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {fills.map((f, idx) => (
                                <SelectItem key={idx} value={String(idx)} className="text-xs font-mono">
                                    {f.date.substring(0, 10)} · {f.side} {f.symbol} ({f.qty} @ ${f.price})
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </CardHeader>

            <CardContent className="pt-6 space-y-6">
                {/* Trade Summary Banner */}
                <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-muted/40 border border-border/60">
                    <div className="flex items-center gap-2">
                        <Badge variant={isBuy ? "default" : "destructive"} className="font-bold text-xs">
                            {trace.side} {trace.symbol}
                        </Badge>
                        <span className="font-mono text-xs font-bold">{trace.date}</span>
                        <span className="text-xs text-muted-foreground font-mono">ID: {trace.fillId.substring(0, 8)}</span>
                    </div>

                    <div className="flex items-center gap-4 font-mono text-xs">
                        <div><span className="text-muted-foreground text-[10px] block">Qty</span><b>{trace.qty}</b></div>
                        <div><span className="text-muted-foreground text-[10px] block">Price</span><b>{formatCurrency(trace.price, baseCurrency)}</b></div>
                        <div><span className="text-muted-foreground text-[10px] block">Notional</span><b>{formatCurrency(trace.notional, baseCurrency)}</b></div>
                    </div>
                </div>

                {/* Horizontal 7-Stage Pipeline Visual Flow */}
                <div className="overflow-x-auto pb-4">
                    <div className="flex items-stretch gap-2 min-w-[900px]">
                        {/* Stage 1: Signal */}
                        <div className="flex-1 p-3 bg-muted/20 border border-border/60 rounded-lg space-y-2 relative">
                            <div className="flex items-center justify-between">
                                <Badge variant="outline" className="text-[9px] uppercase font-bold">1. Signal</Badge>
                                <Activity className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <div>
                                <span className="text-[10px] text-muted-foreground block">Factor Value</span>
                                <span className="font-mono font-bold text-xs">{trace.signal.value > 0 ? "+" : ""}{trace.signal.value.toFixed(2)}</span>
                            </div>
                            <div className="text-[10px] text-muted-foreground font-mono">
                                Rank #{trace.signal.rank} of {trace.signal.totalUniverse}
                            </div>
                        </div>

                        <div className="flex items-center text-muted-foreground shrink-0"><ArrowRight className="w-4 h-4" /></div>

                        {/* Stage 2: Selection */}
                        <div className="flex-1 p-3 bg-muted/20 border border-border/60 rounded-lg space-y-2">
                            <div className="flex items-center justify-between">
                                <Badge variant="outline" className="text-[9px] uppercase font-bold">2. Selection</Badge>
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                            </div>
                            <div>
                                <span className="text-[10px] text-muted-foreground block">Rule Outcome</span>
                                <span className="font-semibold text-xs text-foreground">PASS</span>
                            </div>
                            <div className="text-[10px] text-muted-foreground line-clamp-2">
                                {trace.signal.ruleDescription}
                            </div>
                        </div>

                        <div className="flex items-center text-muted-foreground shrink-0"><ArrowRight className="w-4 h-4" /></div>

                        {/* Stage 3: Target Weight */}
                        <div className="flex-1 p-3 bg-muted/20 border border-border/60 rounded-lg space-y-2">
                            <div className="flex items-center justify-between">
                                <Badge variant="outline" className="text-[9px] uppercase font-bold">3. Allocation</Badge>
                                <Layers className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <div>
                                <span className="text-[10px] text-muted-foreground block">Target Weight</span>
                                <span className="font-mono font-bold text-xs">{(trace.weights.targetWeight * 100).toFixed(1)}%</span>
                            </div>
                            <div className="text-[10px] font-mono text-muted-foreground">
                                \(\Delta w = {(trace.weights.deltaWeight * 100).toFixed(1)}%\)
                            </div>
                        </div>

                        <div className="flex items-center text-muted-foreground shrink-0"><ArrowRight className="w-4 h-4" /></div>

                        {/* Stage 4: Order Intent */}
                        <div className="flex-1 p-3 bg-muted/20 border border-border/60 rounded-lg space-y-2">
                            <div className="flex items-center justify-between">
                                <Badge variant="outline" className="text-[9px] uppercase font-bold">4. Order Intent</Badge>
                                <Sliders className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <div>
                                <span className="text-[10px] text-muted-foreground block">Order Type</span>
                                <span className="font-semibold text-xs text-foreground">{trace.intent.orderType}</span>
                            </div>
                            <div className="text-[10px] font-mono text-muted-foreground">
                                Qty: {trace.intent.requestedQty}
                            </div>
                        </div>

                        <div className="flex items-center text-muted-foreground shrink-0"><ArrowRight className="w-4 h-4" /></div>

                        {/* Stage 5: Risk Constraints */}
                        <div className="flex-1 p-3 bg-muted/20 border border-border/60 rounded-lg space-y-2">
                            <div className="flex items-center justify-between">
                                <Badge variant="outline" className="text-[9px] uppercase font-bold">5. Risk Checks</Badge>
                                <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <div>
                                <span className="text-[10px] text-muted-foreground block">Engine Clamps</span>
                                <span className="font-semibold text-xs text-emerald-600 dark:text-emerald-400">PASSED</span>
                            </div>
                            <div className="text-[10px] text-muted-foreground">
                                {trace.constraints[0]?.description}
                            </div>
                        </div>

                        <div className="flex items-center text-muted-foreground shrink-0"><ArrowRight className="w-4 h-4" /></div>

                        {/* Stage 6: Market Fill */}
                        <div className="flex-1 p-3 bg-muted/20 border border-border/60 rounded-lg space-y-2">
                            <div className="flex items-center justify-between">
                                <Badge variant="outline" className="text-[9px] uppercase font-bold">6. Market Fill</Badge>
                                <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
                            </div>
                            <div>
                                <span className="text-[10px] text-muted-foreground block">Exec Price</span>
                                <span className="font-mono font-bold text-xs">${trace.price}</span>
                            </div>
                            <div className="text-[10px] font-mono text-amber-600">
                                Drag: {trace.economics.slippageBps.toFixed(1)} bps
                            </div>
                        </div>

                        <div className="flex items-center text-muted-foreground shrink-0"><ArrowRight className="w-4 h-4" /></div>

                        {/* Stage 7: Tax Accounting */}
                        <div className="flex-1 p-3 bg-muted/20 border border-border/60 rounded-lg space-y-2">
                            <div className="flex items-center justify-between">
                                <Badge variant="outline" className="text-[9px] uppercase font-bold">7. Tax Accounting</Badge>
                                <Receipt className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <div>
                                <span className="text-[10px] text-muted-foreground block">Accounting Lot</span>
                                <span className="font-semibold text-xs text-foreground">{!isBuy ? "FIFO Consumed" : "Lot Created"}</span>
                            </div>
                            <div className="text-[10px] text-muted-foreground font-mono">
                                {!isBuy ? `${trace.taxLots?.length || 0} Lots Taxed` : "Cost Basis Logged"}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Tax Lot Realization Table for SELL Executions */}
                {!isBuy && trace.taxLots && trace.taxLots.length > 0 && (
                    <div className="pt-4 border-t border-border/40 space-y-2">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            Stage 7 Detail: Tax Lots Consumed & Capital Gains Realized
                        </h4>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow className="bg-muted/40 text-xs">
                                        <TableHead>Lot Purchase Date</TableHead>
                                        <TableHead className="text-right">Qty Consumed</TableHead>
                                        <TableHead className="text-right">Cost Basis</TableHead>
                                        <TableHead className="text-right">Sale Proceeds</TableHead>
                                        <TableHead className="text-right">Realized PnL</TableHead>
                                        <TableHead className="text-center">Holding Bucket</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody className="text-xs font-mono">
                                    {trace.taxLots.map((lot, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell>{lot.purchaseDate}</TableCell>
                                            <TableCell className="text-right">{lot.qty}</TableCell>
                                            <TableCell className="text-right">${lot.costBasis}</TableCell>
                                            <TableCell className="text-right">${lot.proceeds}</TableCell>
                                            <TableCell className={`text-right font-bold ${lot.realizedPnl >= 0 ? "text-emerald-600" : "text-rose-500"}`}>
                                                {lot.realizedPnl >= 0 ? "+" : ""}${lot.realizedPnl}
                                            </TableCell>
                                            <TableCell className="text-center">
                                                <Badge variant="outline" className="text-[10px]">{lot.holdingType}</Badge>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
