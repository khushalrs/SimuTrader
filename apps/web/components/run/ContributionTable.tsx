"use client"

import { useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableFooter } from "@/components/ui/table"
import { Percent } from "lucide-react"

interface ContributionTableProps {
    fills?: any[]
}

interface SymbolContrib {
    symbol: string
    avgWeight: number
    totalReturn: number
    pnl: number
    contributionPct: number
}

function matchRoundTrips(fills: any[]) {
    const trades: { symbol: string; qty: number; buyPrice: number; price: number; pnl: number }[] = []
    const inventory: Record<string, { date: string; price: number; qty: number }[]> = {}

    const sortedFills = [...fills].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    sortedFills.forEach(fill => {
        const sym = fill.symbol
        const side = (fill.side || "").toUpperCase()
        const qty = Math.abs(fill.qty)
        const price = fill.price

        if (!inventory[sym]) inventory[sym] = []

        if (side === "BUY") {
            inventory[sym].push({ date: fill.date, price, qty })
        } else if (side === "SELL") {
            let remainingQty = qty
            while (remainingQty > 0 && inventory[sym].length > 0) {
                const first = inventory[sym][0]
                const matchQty = Math.min(remainingQty, first.qty)

                const buyVal = matchQty * first.price
                const sellVal = matchQty * price
                const pnl = sellVal - buyVal

                trades.push({
                    symbol: sym,
                    qty: matchQty,
                    buyPrice: first.price,
                    price,
                    pnl
                })

                first.qty -= matchQty
                remainingQty -= matchQty

                if (first.qty <= 0) {
                    inventory[sym].shift()
                }
            }
        }
    })

    return trades
}

export function ContributionTable({ fills }: ContributionTableProps) {
    const [sortKey, setSortKey] = useState<"contribution" | "symbol" | "weight" | "return">("contribution")
    const [sortAsc, setSortAsc] = useState(false)

    const symbolContributions = useMemo(() => {
        if (!fills || fills.length === 0) return []

        const trades = matchRoundTrips(fills)
        if (trades.length === 0) return []

        const symbolStatsMap: Record<string, { symbol: string; totalPnl: number; volume: number }> = {}
        let totalPnlSum = 0

        trades.forEach(t => {
            if (!symbolStatsMap[t.symbol]) {
                symbolStatsMap[t.symbol] = { symbol: t.symbol, totalPnl: 0, volume: 0 }
            }
            symbolStatsMap[t.symbol].totalPnl += t.pnl
            symbolStatsMap[t.symbol].volume += t.qty * t.buyPrice
            totalPnlSum += t.pnl
        })

        const totalVol = Object.values(symbolStatsMap).reduce((a, b) => a + b.volume, 0) || 1

        return Object.values(symbolStatsMap).map(s => {
            const avgWeight = s.volume / totalVol
            const contribPct = totalPnlSum !== 0 ? s.totalPnl / Math.max(1, Math.abs(totalPnlSum)) : 0
            const totalReturn = s.volume > 0 ? s.totalPnl / s.volume : 0
            return {
                symbol: s.symbol,
                avgWeight,
                totalReturn,
                pnl: s.totalPnl,
                contributionPct: contribPct
            } as SymbolContrib
        })
    }, [fills])

    const sortedContributions = useMemo(() => {
        return [...symbolContributions].sort((a, b) => {
            let mult = sortAsc ? 1 : -1
            if (sortKey === "symbol") return mult * a.symbol.localeCompare(b.symbol)
            if (sortKey === "weight") return mult * (a.avgWeight - b.avgWeight)
            if (sortKey === "return") return mult * (a.totalReturn - b.totalReturn)
            return mult * (a.contributionPct - b.contributionPct)
        })
    }, [symbolContributions, sortKey, sortAsc])

    const maxAbsContrib = useMemo(() => {
        return symbolContributions.reduce((max, s) => Math.max(max, Math.abs(s.contributionPct)), 0.01)
    }, [symbolContributions])

    const handleSort = (key: "contribution" | "symbol" | "weight" | "return") => {
        if (sortKey === key) {
            setSortAsc(!sortAsc)
        } else {
            setSortKey(key)
            setSortAsc(false)
        }
    }

    if (!fills || fills.length === 0 || symbolContributions.length === 0) {
        return null
    }

    return (
        <Card className="border border-border">
            <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Percent className="w-4 h-4 text-primary" /> Asset Performance Contribution Breakdown
                </CardTitle>
                <CardDescription>
                    Attribution of overall trading P&L decomposed by symbol, average portfolio weight, and net return contribution.
                </CardDescription>
            </CardHeader>
            <CardContent className="p-0 overflow-x-auto">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-muted/40 text-xs cursor-pointer select-none">
                            <TableHead className="w-28 font-semibold" onClick={() => handleSort("symbol")}>
                                Symbol {sortKey === "symbol" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="text-right font-semibold" onClick={() => handleSort("weight")}>
                                Avg Weight {sortKey === "weight" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="text-right font-semibold" onClick={() => handleSort("return")}>
                                Total Return {sortKey === "return" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="text-right font-semibold" onClick={() => handleSort("contribution")}>
                                PnL Contribution {sortKey === "contribution" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="w-40 text-left font-semibold pl-4">Contribution Visual</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody className="text-xs">
                        {sortedContributions.map((item, idx) => {
                            const barWidth = Math.min(100, (Math.abs(item.contributionPct) / maxAbsContrib) * 100)
                            const isPos = item.contributionPct >= 0

                            return (
                                <TableRow key={idx} className="hover:bg-muted/20">
                                    <TableCell className="font-bold uppercase font-mono">{item.symbol}</TableCell>
                                    <TableCell className="text-right font-mono font-medium">
                                        {(item.avgWeight * 100).toFixed(1)}%
                                    </TableCell>
                                    <TableCell className={`text-right font-mono font-medium ${item.totalReturn >= 0 ? "text-emerald-600" : "text-rose-500"}`}>
                                        {item.totalReturn >= 0 ? "+" : ""}{(item.totalReturn * 100).toFixed(2)}%
                                    </TableCell>
                                    <TableCell className={`text-right font-mono font-bold ${isPos ? "text-emerald-600" : "text-rose-500"}`}>
                                        {isPos ? "+" : ""}{(item.contributionPct * 100).toFixed(2)}%
                                    </TableCell>
                                    <TableCell className="pl-4">
                                        <div className="flex items-center gap-2">
                                            <div className="h-3 bg-muted rounded-full w-full overflow-hidden flex items-center">
                                                <div
                                                    className={`h-full rounded-full transition-all ${isPos ? "bg-emerald-500" : "bg-rose-500"}`}
                                                    style={{ width: `${Math.max(4, barWidth)}%` }}
                                                />
                                            </div>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            )
                        })}
                    </TableBody>
                    <TableFooter className="border-t-2 border-border bg-muted/50 font-semibold text-xs sticky bottom-0">
                        <TableRow>
                            <TableCell className="font-bold text-foreground">Total Asset PnL</TableCell>
                            <TableCell className="text-right font-mono">100.0%</TableCell>
                            <TableCell className="text-right font-mono">—</TableCell>
                            <TableCell className="text-right font-mono font-bold text-emerald-600">
                                +100.00%
                            </TableCell>
                            <TableCell className="pl-4 font-mono text-[11px] text-muted-foreground">
                                Total matched gains
                            </TableCell>
                        </TableRow>
                        <TableRow className="border-t border-border/30">
                            <TableCell className="font-medium text-muted-foreground">Cash & Residual</TableCell>
                            <TableCell className="text-right font-mono text-muted-foreground">—</TableCell>
                            <TableCell className="text-right font-mono text-muted-foreground">—</TableCell>
                            <TableCell className="text-right font-mono text-muted-foreground">0.00%</TableCell>
                            <TableCell className="pl-4 font-mono text-[11px] text-muted-foreground">
                                Unallocated capital balance
                            </TableCell>
                        </TableRow>
                    </TableFooter>
                </Table>
            </CardContent>
        </Card>
    )
}
