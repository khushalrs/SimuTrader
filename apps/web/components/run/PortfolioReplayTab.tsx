"use client"

import { useState, useEffect, useMemo } from "react"
import useSWR from "swr"
import { getRunPositions, getRunFills, RunFillOut, RunPositionOut } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { formatCurrency } from "@/lib/utils"
import { Play, Pause, SkipBack, SkipForward, RotateCcw, Calendar, Layers, Activity, DollarSign } from "lucide-react"

interface PortfolioReplayTabProps {
    runId: string
    equity?: Array<{ date: string; value: number }>
    baseCurrency?: string
    status?: string
}

export function PortfolioReplayTab({ runId, equity = [], baseCurrency = "USD", status }: PortfolioReplayTabProps) {
    const isSucceeded = status === "SUCCEEDED"

    // Fetch all positions & fills for replay
    const { data: positionsData } = useSWR(
        isSucceeded ? `/runs/${runId}/positions` : null,
        () => getRunPositions(runId),
        { revalidateOnFocus: false }
    )

    const { data: fillsData } = useSWR(
        isSucceeded ? `/runs/${runId}/fills?limit=1000` : null,
        () => getRunFills(runId, undefined, undefined, 1000, 0),
        { revalidateOnFocus: false }
    )

    const dates = useMemo(() => {
        if (!equity || equity.length === 0) return []
        return equity.map(e => e.date)
    }, [equity])

    const [currentIndex, setCurrentIndex] = useState(0)
    const [isPlaying, setIsPlaying] = useState(false)

    // Reset index if dates change
    useEffect(() => {
        if (dates.length > 0 && currentIndex >= dates.length) {
            setCurrentIndex(0)
        }
    }, [dates, currentIndex])

    // Playback interval animation
    useEffect(() => {
        let timer: NodeJS.Timeout
        if (isPlaying && dates.length > 0) {
            timer = setInterval(() => {
                setCurrentIndex(prev => {
                    if (prev >= dates.length - 1) {
                        setIsPlaying(false)
                        return prev
                    }
                    return prev + 1
                })
            }, 800)
        }
        return () => clearInterval(timer)
    }, [isPlaying, dates])

    const selectedDate = dates[currentIndex] || ""
    const selectedEquityPoint = equity[currentIndex] || null

    // Daily positions
    const dailyPositions = useMemo(() => {
        if (!positionsData || !selectedDate) return []
        return positionsData.filter(p => p.date === selectedDate)
    }, [positionsData, selectedDate])

    // Daily fills
    const dailyFills = useMemo(() => {
        if (!fillsData || !selectedDate) return []
        return fillsData.filter(f => f.date === selectedDate || f.date.startsWith(selectedDate))
    }, [fillsData, selectedDate])

    // Daily equity return
    const dailyReturn = useMemo(() => {
        if (currentIndex <= 0 || !equity || equity.length < 2) return 0
        const prev = equity[currentIndex - 1].value
        const curr = equity[currentIndex].value
        return prev > 0 ? (curr - prev) / prev : 0
    }, [equity, currentIndex])

    if (!dates || dates.length === 0) {
        return (
            <Card className="p-8 text-center text-muted-foreground border-dashed">
                <Calendar className="w-10 h-10 mx-auto mb-2 opacity-40" />
                No simulation trading dates available for portfolio replay.
            </Card>
        )
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* Scrubber Controls Card */}
            <Card className="border border-border shadow-sm bg-card/60 backdrop-blur">
                <CardHeader className="pb-3 border-b border-border/40 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <CardTitle className="text-base font-bold flex items-center gap-2">
                            <Play className="w-4 h-4 text-primary" /> Date-by-Date Portfolio Playback & Scrubber
                        </CardTitle>
                        <CardDescription className="text-xs">
                            Step or animate through daily portfolio states, positions, and execution events.
                        </CardDescription>
                    </div>

                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => setCurrentIndex(0)}
                        >
                            <RotateCcw className="w-3.5 h-3.5" />
                        </Button>

                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 w-8 p-0"
                            disabled={currentIndex <= 0}
                            onClick={() => setCurrentIndex(prev => Math.max(0, prev - 1))}
                        >
                            <SkipBack className="w-3.5 h-3.5" />
                        </Button>

                        <Button
                            variant={isPlaying ? "destructive" : "default"}
                            size="sm"
                            className="h-8 px-3 text-xs font-semibold gap-1.5"
                            onClick={() => setIsPlaying(prev => !prev)}
                        >
                            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                            {isPlaying ? "Pause" : "Play"}
                        </Button>

                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 w-8 p-0"
                            disabled={currentIndex >= dates.length - 1}
                            onClick={() => setCurrentIndex(prev => Math.min(dates.length - 1, prev + 1))}
                        >
                            <SkipForward className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </CardHeader>

                <CardContent className="pt-4 space-y-4">
                    {/* Date Slider */}
                    <div className="space-y-2">
                        <div className="flex justify-between items-center text-xs font-mono">
                            <span className="text-muted-foreground font-semibold">Day {currentIndex + 1} of {dates.length}</span>
                            <span className="font-bold text-primary text-sm">{selectedDate}</span>
                            <span className="text-muted-foreground font-semibold">{dates[dates.length - 1]}</span>
                        </div>

                        <input
                            type="range"
                            min={0}
                            max={dates.length - 1}
                            value={currentIndex}
                            onChange={e => setCurrentIndex(Number(e.target.value))}
                            className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                        />
                    </div>

                    {/* Selected Date Summary KPIs */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs pt-2">
                        <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Selected Date</span>
                            <span className="font-mono font-bold text-sm text-foreground">{selectedDate}</span>
                        </div>

                        <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Portfolio Equity</span>
                            <span className="font-mono font-bold text-sm text-foreground">
                                {selectedEquityPoint ? formatCurrency(selectedEquityPoint.value, baseCurrency) : "—"}
                            </span>
                        </div>

                        <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Daily Return</span>
                            <span className={`font-mono font-bold text-sm ${dailyReturn >= 0 ? "text-emerald-600" : "text-rose-500"}`}>
                                {dailyReturn >= 0 ? "+" : ""}{(dailyReturn * 100).toFixed(2)}%
                            </span>
                        </div>

                        <div className="p-2.5 rounded-lg bg-muted/30 border border-border/50">
                            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Day's Executions</span>
                            <span className="font-mono font-bold text-sm text-foreground">
                                {dailyFills.length} Fills
                            </span>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Daily Positions & Fills Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Positions Snapshot */}
                <Card className="border border-border shadow-sm">
                    <CardHeader className="pb-3 border-b border-border/40">
                        <CardTitle className="text-sm font-semibold flex items-center gap-2">
                            <Layers className="w-4 h-4 text-primary" /> Active Positions ({selectedDate})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-muted/40 text-xs">
                                    <TableHead>Symbol</TableHead>
                                    <TableHead className="text-right">Qty</TableHead>
                                    <TableHead className="text-right">Market Value</TableHead>
                                    <TableHead className="text-right">Weight</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody className="text-xs">
                                {dailyPositions.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={4} className="text-center py-6 text-muted-foreground">
                                            No active positions held on {selectedDate}.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    dailyPositions.map((pos, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell className="font-bold uppercase font-mono">{pos.symbol}</TableCell>
                                            <TableCell className="text-right font-mono">{pos.qty.toLocaleString()}</TableCell>
                                            <TableCell className="text-right font-mono font-medium">
                                                {formatCurrency(pos.market_value_base, baseCurrency)}
                                            </TableCell>
                                            <TableCell className="text-right font-mono font-bold text-primary">
                                                {pos.weight !== undefined && pos.weight !== null ? `${(pos.weight * 100).toFixed(1)}%` : "—"}
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Daily Executions Snapshot */}
                <Card className="border border-border shadow-sm">
                    <CardHeader className="pb-3 border-b border-border/40">
                        <CardTitle className="text-sm font-semibold flex items-center gap-2">
                            <Activity className="w-4 h-4 text-primary" /> Execution Fills ({selectedDate})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-muted/40 text-xs">
                                    <TableHead>Symbol</TableHead>
                                    <TableHead className="text-right">Side</TableHead>
                                    <TableHead className="text-right">Qty</TableHead>
                                    <TableHead className="text-right">Price</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody className="text-xs">
                                {dailyFills.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={4} className="text-center py-6 text-muted-foreground">
                                            No trade executions on {selectedDate}.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    dailyFills.map((fill, idx) => (
                                        <TableRow key={idx}>
                                            <TableCell className="font-bold uppercase font-mono">{fill.symbol}</TableCell>
                                            <TableCell className="text-right font-mono">
                                                <Badge
                                                    variant={(fill.side || "").toUpperCase() === "BUY" ? "default" : "destructive"}
                                                    className="text-[9px] px-1.5 py-0"
                                                >
                                                    {fill.side}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-right font-mono">{fill.qty.toLocaleString()}</TableCell>
                                            <TableCell className="text-right font-mono font-semibold">
                                                {formatCurrency(fill.price, baseCurrency)}
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
