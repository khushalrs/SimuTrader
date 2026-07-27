"use client"

import useSWR from "swr"
import { getRunFills } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ShieldAlert, TrendingUp, TrendingDown, Activity, Award } from "lucide-react"
import { useMemo } from "react"
import { ContributionTable } from "./ContributionTable"

interface Trade {
    symbol: string
    buyDate: string
    sellDate: string
    qty: number
    buyPrice: number
    sellPrice: number
    pnl: number
    pnlPct: number
    durationDays: number
}

function matchRoundTrips(fills: any[]): Trade[] {
    const trades: Trade[] = []
    const inventory: Record<string, { date: string; price: number; qty: number }[]> = {}

    // Sort chronologically
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
                const pnlPct = first.price > 0 ? pnl / buyVal : 0
                
                const buyDate = new Date(first.date)
                const sellDate = new Date(fill.date)
                const durationDays = Math.max(0, Math.ceil((sellDate.getTime() - buyDate.getTime()) / (1000 * 60 * 60 * 24)))

                trades.push({
                    symbol: sym,
                    buyDate: first.date,
                    sellDate: fill.date,
                    qty: matchQty,
                    buyPrice: first.price,
                    sellPrice: price,
                    pnl,
                    pnlPct,
                    durationDays
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

export function TradeAnalyticsTab({ runId, baseCurrency = "USD" }: { runId: string, baseCurrency?: string }) {
    // Fetch all fills to run analytics. Fetching up to 1000 fills to have full depth.
    const { data: fills, isLoading, error } = useSWR(
        runId ? `/runs/${runId}/fills?limit=1000` : null,
        () => getRunFills(runId, undefined, undefined, 1000, 0),
        { revalidateOnFocus: false }
    )

    const stats = useMemo(() => {
        if (!fills || fills.length === 0) return null

        const trades = matchRoundTrips(fills)
        if (trades.length === 0) return null

        const totalTrades = trades.length
        const winners = trades.filter(t => t.pnl > 0)
        const losers = trades.filter(t => t.pnl <= 0)
        
        const winCount = winners.length
        const lossCount = losers.length
        const winRate = winCount / totalTrades

        const avgDuration = trades.reduce((sum, t) => sum + t.durationDays, 0) / totalTrades

        const totalWinPnl = winners.reduce((sum, t) => sum + t.pnl, 0)
        const totalLossPnl = losers.reduce((sum, t) => sum + t.pnl, 0)

        const avgWinPnl = winCount > 0 ? totalWinPnl / winCount : 0
        const avgLossPnl = lossCount > 0 ? totalLossPnl / lossCount : 0

        const profitFactor = Math.abs(totalLossPnl) > 0 ? totalWinPnl / Math.abs(totalLossPnl) : totalWinPnl

        const sortedWinners = [...winners].sort((a, b) => b.pnl - a.pnl).slice(0, 5)
        const sortedLosers = [...losers].sort((a, b) => a.pnl - b.pnl).slice(0, 5)

        return {
            totalTrades,
            winCount,
            lossCount,
            winRate,
            avgDuration,
            avgWinPnl,
            avgLossPnl,
            profitFactor,
            sortedWinners,
            sortedLosers
        }
    }, [fills])

    if (isLoading) {
        return (
            <div className="space-y-6 animate-pulse">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
                </div>
                <Skeleton className="h-64 w-full rounded-xl" />
            </div>
        )
    }

    if (error || !stats) {
        return (
            <Card className="min-h-[300px] flex flex-col items-center justify-center p-8 text-center border-dashed">
                <Activity className="w-12 h-12 text-muted-foreground/30 mb-3" />
                <h3 className="font-semibold text-lg">No Fills / Trades Recorded</h3>
                <p className="text-sm text-muted-foreground mt-1 max-w-md">
                    No round-trip trade executions were detected. Either the strategy hasn't rebalanced yet or holds asset positions statically.
                </p>
            </Card>
        )
    }

    const {
        totalTrades,
        winCount,
        lossCount,
        winRate,
        avgDuration,
        avgWinPnl,
        avgLossPnl,
        profitFactor,
        sortedWinners,
        sortedLosers
    } = stats

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* KPI Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Total Completed Trades</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-primary">
                            {totalTrades}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Matched round-trip BUY/SELL sequences.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Win Rate</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                            {(winRate * 100).toFixed(1)}%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">{winCount} wins vs {lossCount} losses.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Average Hold Duration</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-foreground">
                            {avgDuration.toFixed(1)} Days
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Average lifetime of matched positions.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Profit Factor</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-foreground">
                            {profitFactor.toFixed(2)}x
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Gross wins divided by gross losses.</p>
                    </CardContent>
                </Card>
            </div>

            {/* Symbol Performance Contribution Table Card (F5) */}
            <ContributionTable fills={fills} />

            {/* Performance Averages */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Card>
                    <CardContent className="pt-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs uppercase text-muted-foreground font-semibold">Average Winning Trade</p>
                            <h4 className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                                +${avgWinPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </h4>
                        </div>
                        <TrendingUp className="w-5 h-5 text-emerald-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs uppercase text-muted-foreground font-semibold">Average Losing Trade</p>
                            <h4 className="text-xl font-bold font-mono text-rose-500 mt-1">
                                -${Math.abs(avgLossPnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </h4>
                        </div>
                        <TrendingDown className="w-5 h-5 text-rose-500" />
                    </CardContent>
                </Card>
            </div>

            {/* Largest Winners and Losers tables */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Top Winners */}
                <Card className="border border-border">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <Award className="w-4 h-4 text-emerald-500" /> Top 5 Winner Trades
                        </CardTitle>
                        <CardDescription>Largest profitable round trips completed in this simulation.</CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Symbol</TableHead>
                                    <TableHead className="text-right">Qty</TableHead>
                                    <TableHead className="text-right">P&L</TableHead>
                                    <TableHead className="text-right">Return</TableHead>
                                    <TableHead className="text-right">Hold Time</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {sortedWinners.map((trade, idx) => (
                                    <TableRow key={idx}>
                                        <TableCell className="font-semibold uppercase">{trade.symbol}</TableCell>
                                        <TableCell className="text-right font-mono">{trade.qty.toLocaleString()}</TableCell>
                                        <TableCell className="text-right font-mono text-emerald-600">
                                            +${trade.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                        </TableCell>
                                        <TableCell className="text-right font-mono text-emerald-600">
                                            +{(trade.pnlPct * 100).toFixed(1)}%
                                        </TableCell>
                                        <TableCell className="text-right font-mono">{trade.durationDays}d</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Top Losers */}
                <Card className="border border-border">
                    <CardHeader>
                        <CardTitle className="text-sm flex items-center gap-2">
                            <ShieldAlert className="w-4 h-4 text-rose-500" /> Top 5 Loser Trades
                        </CardTitle>
                        <CardDescription>Largest losing round trips completed in this simulation.</CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Symbol</TableHead>
                                    <TableHead className="text-right">Qty</TableHead>
                                    <TableHead className="text-right">P&L</TableHead>
                                    <TableHead className="text-right">Return</TableHead>
                                    <TableHead className="text-right">Hold Time</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {sortedLosers.map((trade, idx) => (
                                    <TableRow key={idx}>
                                        <TableCell className="font-semibold uppercase">{trade.symbol}</TableCell>
                                        <TableCell className="text-right font-mono">{trade.qty.toLocaleString()}</TableCell>
                                        <TableCell className="text-right font-mono text-rose-500">
                                            -${Math.abs(trade.pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                        </TableCell>
                                        <TableCell className="text-right font-mono text-rose-500">
                                            {(trade.pnlPct * 100).toFixed(1)}%
                                        </TableCell>
                                        <TableCell className="text-right font-mono">{trade.durationDays}d</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
