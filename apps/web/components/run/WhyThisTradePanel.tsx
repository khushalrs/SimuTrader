"use client"

import { useMemo } from "react"
import { TradeTraceChain, RunFillOut, buildTradeTraceFromFill } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatCurrency } from "@/lib/utils"
import {
    HelpCircle,
    ArrowRight,
    TrendingUp,
    ShieldCheck,
    ShieldAlert,
    DollarSign,
    Receipt,
    Layers,
    Activity,
    CheckCircle2
} from "lucide-react"

interface WhyThisTradePanelProps {
    fill?: RunFillOut | null
    trace?: TradeTraceChain | null
    baseCurrency?: string
    onClose?: () => void
}

export function WhyThisTradePanel({ fill, trace: propTrace, baseCurrency = "USD", onClose }: WhyThisTradePanelProps) {
    const trace = useMemo(() => {
        if (propTrace) return propTrace
        if (fill) return buildTradeTraceFromFill(fill)
        return null
    }, [fill, propTrace])

    if (!trace) {
        return (
            <div className="p-6 text-center text-muted-foreground text-xs font-mono border border-dashed rounded-lg">
                Select a trade fill from the table to inspect "Why this trade?" execution chain.
            </div>
        )
    }

    const isBuy = trace.side === "BUY"

    return (
        <Card className="border border-primary/30 shadow-md bg-card animate-in fade-in duration-300">
            <CardHeader className="pb-3 border-b border-border/40">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className={`p-1.5 rounded ${isBuy ? "bg-emerald-500/10 text-emerald-600" : "bg-rose-500/10 text-rose-500"}`}>
                            <HelpCircle className="w-4 h-4" />
                        </div>
                        <div>
                            <CardTitle className="text-sm font-bold flex items-center gap-2">
                                Why This Trade?
                                <Badge variant={isBuy ? "default" : "destructive"} className="text-[10px]">
                                    {trace.side} {trace.symbol}
                                </Badge>
                            </CardTitle>
                            <CardDescription className="text-xs font-mono">
                                Execution Chain · {trace.date} · Fill #{trace.fillId.substring(0, 8)}
                            </CardDescription>
                        </div>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="pt-4 space-y-5 text-xs">
                {/* Section 1: Signal & Rank Rationale */}
                <div className="p-3 rounded-lg bg-muted/30 border border-border/50 space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="font-semibold text-foreground uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                            <Activity className="w-3.5 h-3.5 text-primary" /> 1. Signal Value & Rank
                        </span>
                        <Badge variant="outline" className="font-mono text-[10px]">
                            Rank #{trace.signal.rank} of {trace.signal.totalUniverse}
                        </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 font-mono pt-1">
                        <div>
                            <span className="text-[10px] text-muted-foreground block">Signal Intensity</span>
                            <span className="font-bold text-foreground">{trace.signal.value > 0 ? "+" : ""}{trace.signal.value.toFixed(2)}</span>
                        </div>
                        <div>
                            <span className="text-[10px] text-muted-foreground block">Selection Rule</span>
                            <span className="text-foreground text-[11px] truncate block">{trace.signal.ruleDescription}</span>
                        </div>
                    </div>
                </div>

                {/* Section 2: Weight Allocation Delta */}
                <div className="p-3 rounded-lg bg-muted/30 border border-border/50 space-y-2">
                    <span className="font-semibold text-foreground uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5 text-primary" /> 2. Portfolio Weight Allocation
                    </span>
                    <div className="flex items-center justify-between font-mono pt-1">
                        <div className="text-center">
                            <span className="text-[10px] text-muted-foreground block">Pre-Trade</span>
                            <span className="font-medium">{(trace.weights.preWeight * 100).toFixed(1)}%</span>
                        </div>
                        <ArrowRight className="w-4 h-4 text-muted-foreground" />
                        <div className="text-center">
                            <span className="text-[10px] text-muted-foreground block">Target Weight</span>
                            <span className="font-medium">{(trace.weights.targetWeight * 100).toFixed(1)}%</span>
                        </div>
                        <ArrowRight className="w-4 h-4 text-muted-foreground" />
                        <div className="text-center">
                            <span className="text-[10px] text-muted-foreground block">Net Rebalance (\(\Delta w\))</span>
                            <span className={`font-bold ${trace.weights.deltaWeight >= 0 ? "text-emerald-600" : "text-rose-500"}`}>
                                {trace.weights.deltaWeight >= 0 ? "+" : ""}{(trace.weights.deltaWeight * 100).toFixed(1)}%
                            </span>
                        </div>
                    </div>
                </div>

                {/* Section 3: Risk Engine & Constraint Clamps */}
                <div className="p-3 rounded-lg bg-muted/30 border border-border/50 space-y-2">
                    <span className="font-semibold text-foreground uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-primary" /> 3. Risk Engine Clamps & Constraints
                    </span>
                    <div className="space-y-1.5 pt-1">
                        {trace.constraints.map((c, idx) => (
                            <div key={idx} className="flex items-center justify-between text-[11px]">
                                <span className="font-medium">{c.name}</span>
                                <div className="flex items-center gap-1.5">
                                    <Badge
                                        variant={c.status === "PASSED" ? "default" : c.status === "CLAMPED" ? "secondary" : "destructive"}
                                        className="text-[9px] px-1.5 py-0"
                                    >
                                        {c.status}
                                    </Badge>
                                    <span className="text-[10px] text-muted-foreground">{c.description}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Section 4: Fill Economics */}
                <div className="p-3 rounded-lg bg-muted/30 border border-border/50 space-y-2">
                    <span className="font-semibold text-foreground uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                        <DollarSign className="w-3.5 h-3.5 text-primary" /> 4. Fill Economics & Friction
                    </span>
                    <div className="grid grid-cols-3 gap-2 font-mono text-[11px] pt-1">
                        <div>
                            <span className="text-[10px] text-muted-foreground block">Exec Price</span>
                            <span className="font-bold">{formatCurrency(trace.price, baseCurrency)}</span>
                        </div>
                        <div>
                            <span className="text-[10px] text-muted-foreground block">Slippage Drag</span>
                            <span className="font-medium text-amber-600">{trace.economics.slippageBps.toFixed(1)} bps</span>
                        </div>
                        <div>
                            <span className="text-[10px] text-muted-foreground block">Commission</span>
                            <span className="font-medium">{formatCurrency(trace.commission, baseCurrency)}</span>
                        </div>
                    </div>
                </div>

                {/* Section 5: Tax Lots Consumed (for SELL Fills) */}
                {!isBuy && trace.taxLots && trace.taxLots.length > 0 && (
                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50 space-y-2">
                        <span className="font-semibold text-foreground uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                            <Receipt className="w-3.5 h-3.5 text-primary" /> 5. Accounting Tax Lots Consumed (FIFO)
                        </span>
                        <div className="overflow-x-auto pt-1">
                            <Table>
                                <TableHeader>
                                    <TableRow className="bg-muted/50 text-[10px]">
                                        <TableHead className="py-1">Lot Date</TableHead>
                                        <TableHead className="py-1 text-right">Qty</TableHead>
                                        <TableHead className="py-1 text-right">Cost Basis</TableHead>
                                        <TableHead className="py-1 text-right">Realized PnL</TableHead>
                                        <TableHead className="py-1 text-center">Holding</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody className="text-[10px] font-mono">
                                    {trace.taxLots.map((lot, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell className="py-1">{lot.purchaseDate}</TableCell>
                                            <TableCell className="py-1 text-right">{lot.qty}</TableCell>
                                            <TableCell className="py-1 text-right">${lot.costBasis}</TableCell>
                                            <TableCell className={`py-1 text-right font-bold ${lot.realizedPnl >= 0 ? "text-emerald-600" : "text-rose-500"}`}>
                                                {lot.realizedPnl >= 0 ? "+" : ""}${lot.realizedPnl}
                                            </TableCell>
                                            <TableCell className="py-1 text-center">
                                                <Badge variant="outline" className="text-[9px] px-1 py-0">{lot.holdingType}</Badge>
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
