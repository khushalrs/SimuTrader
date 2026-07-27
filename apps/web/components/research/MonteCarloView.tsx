"use client"

import { useMemo, useState } from "react"
import {
    AreaChart,
    Area,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChartFrame, CHART_THEME } from "@/components/run/ChartFrame"
import { Dices, RefreshCw, ShieldAlert, TrendingUp, Percent, Activity } from "lucide-react"

interface MonteCarloViewProps {
    equityPoints?: Array<{ date: string; equity: number }>
    initialCapital?: number
}

export function MonteCarloView({ equityPoints, initialCapital = 100000 }: MonteCarloViewProps) {
    const [simSeed, setSimSeed] = useState(1)

    // Calculate daily returns from equity series
    const dailyReturns = useMemo(() => {
        if (!equityPoints || equityPoints.length < 2) {
            // Demo synthetic returns
            const returns = []
            for (let i = 0; i < 252; i++) {
                returns.push((Math.random() - 0.485) * 0.015)
            }
            return returns
        }

        const returns: number[] = []
        for (let i = 1; i < equityPoints.length; i++) {
            const prev = equityPoints[i - 1].equity
            const curr = equityPoints[i].equity
            if (prev > 0) {
                returns.push((curr - prev) / prev)
            }
        }
        return returns.length > 0 ? returns : [0.001]
    }, [equityPoints])

    // Perform Monte Carlo Bootstrap Resampling (500 runs)
    const mcResults = useMemo(() => {
        const numSims = 500
        const numDays = Math.max(100, dailyReturns.length)
        const N = dailyReturns.length

        const paths: number[][] = []
        const terminalReturns: number[] = []
        const maxDrawdowns: number[] = []

        // Deterministic pseudo-random with simSeed
        let seed = simSeed
        const pseudoRand = () => {
            seed = (seed * 9301 + 49297) % 233280
            return seed / 233280
        }

        for (let sim = 0; sim < numSims; sim++) {
            const path = [initialCapital]
            let peak = initialCapital
            let maxDD = 0

            for (let day = 0; day < numDays; day++) {
                const randIdx = Math.floor(pseudoRand() * N)
                const ret = dailyReturns[randIdx]
                const nextVal = Math.max(100, path[path.length - 1] * (1.0 + ret))
                path.push(nextVal)

                if (nextVal > peak) peak = nextVal
                const dd = (nextVal - peak) / peak
                if (dd < maxDD) maxDD = dd
            }

            paths.push(path)
            terminalReturns.push((path[path.length - 1] - initialCapital) / initialCapital)
            maxDrawdowns.push(maxDD)
        }

        // Calculate Percentile Bands for each day
        const fanPoints = []
        for (let day = 0; day < numDays; day += 2) {
            const dayVals = paths.map(p => p[day]).sort((a, b) => a - b)
            const p5 = dayVals[Math.floor(numSims * 0.05)]
            const p25 = dayVals[Math.floor(numSims * 0.25)]
            const p50 = dayVals[Math.floor(numSims * 0.50)]
            const p75 = dayVals[Math.floor(numSims * 0.75)]
            const p95 = dayVals[Math.floor(numSims * 0.95)]

            fanPoints.push({
                day: `Day ${day}`,
                p5: Math.round(p5),
                p25: Math.round(p25),
                p50: Math.round(p50),
                p75: Math.round(p75),
                p95: Math.round(p95),
                // Area range helpers
                bandOuter: [Math.round(p5), Math.round(p95)],
                bandInner: [Math.round(p25), Math.round(p75)]
            })
        }

        // Histogram of Terminal Returns
        const positiveCount = terminalReturns.filter(r => r > 0).length
        const probPositive = positiveCount / numSims

        // 95% Confidence Max Drawdown (5th percentile of max drawdowns)
        const sortedDD = [...maxDrawdowns].sort((a, b) => a - b)
        const dd95 = sortedDD[Math.floor(numSims * 0.05)]

        // Binned return histogram data
        const returnBins: { range: string; count: number }[] = []
        const binCount = 10
        const minRet = Math.min(...terminalReturns)
        const maxRet = Math.max(...terminalReturns)
        const step = (maxRet - minRet) / binCount || 0.1

        for (let i = 0; i < binCount; i++) {
            const low = minRet + i * step
            const high = low + step
            const cnt = terminalReturns.filter(r => r >= low && (i === binCount - 1 ? r <= high : r < high)).length
            returnBins.push({
                range: `${(low * 100).toFixed(0)}%`,
                count: cnt
            })
        }

        return {
            fanPoints,
            probPositive,
            dd95,
            medianReturn: terminalReturns.sort((a, b) => a - b)[Math.floor(numSims * 0.5)],
            returnBins
        }
    }, [dailyReturns, initialCapital, simSeed])

    return (
        <div className="space-y-6">
            {/* Header KPI Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Probability of Positive Return</CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-baseline justify-between">
                        <div className="text-3xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                            {(mcResults.probPositive * 100).toFixed(1)}%
                        </div>
                        <Badge variant="outline" className="font-mono text-xs">500 Resamples</Badge>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">5th Percentile Max DD (VaR 95%)</CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-baseline justify-between">
                        <div className="text-3xl font-bold font-mono text-rose-500">
                            {(mcResults.dd95 * 100).toFixed(1)}%
                        </div>
                        <Badge variant="destructive" className="text-[10px]">Tail Risk</Badge>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Median Expected Terminal Return</CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-baseline justify-between">
                        <div className="text-3xl font-bold font-mono text-primary">
                            +{(mcResults.medianReturn * 100).toFixed(1)}%
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs gap-1"
                            onClick={() => setSimSeed(prev => prev + 1)}
                        >
                            <RefreshCw className="w-3.5 h-3.5" /> Re-sim
                        </Button>
                    </CardContent>
                </Card>
            </div>

            {/* Fan Chart View */}
            <ChartFrame
                title="Monte Carlo Resampled Equity Percentile Fan Chart"
                description="500 bootstrapped path iterations showing 5th, 25th, 50th (median), 75th, and 95th percentile confidence bands."
            >
                <div className="h-[320px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={mcResults.fanPoints} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                            <CartesianGrid {...CHART_THEME.grid} />
                            <XAxis dataKey="day" {...CHART_THEME.axis} minTickGap={30} />
                            <YAxis
                                {...CHART_THEME.axis}
                                tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                                width={55}
                            />
                            <Tooltip
                                contentStyle={CHART_THEME.tooltip.contentStyle}
                                itemStyle={CHART_THEME.tooltip.itemStyle}
                                formatter={(val: any, name: any) => [`$${Number(val).toLocaleString()}`, name]}
                            />
                            {/* 95th Percentile Band */}
                            <Area type="monotone" dataKey="p95" name="95th Percentile" stroke="hsl(var(--emerald-500, 160 84% 39%))" fill="rgba(16, 185, 129, 0.15)" strokeWidth={1.5} />
                            {/* 75th Percentile Band */}
                            <Area type="monotone" dataKey="p75" name="75th Percentile" stroke="hsl(var(--primary))" fill="rgba(59, 130, 246, 0.2)" strokeWidth={1.5} />
                            {/* Median 50th Percentile Line */}
                            <Area type="monotone" dataKey="p50" name="50th Percentile (Median)" stroke="hsl(var(--foreground))" fill="none" strokeWidth={2.5} />
                            {/* 25th Percentile Band */}
                            <Area type="monotone" dataKey="p25" name="25th Percentile" stroke="hsl(var(--amber-500, 38 92% 50%))" fill="rgba(245, 158, 11, 0.15)" strokeWidth={1.5} />
                            {/* 5th Percentile Band */}
                            <Area type="monotone" dataKey="p5" name="5th Percentile (Tail)" stroke="hsl(var(--rose-500, 343 81% 55%))" fill="rgba(244, 63, 94, 0.15)" strokeWidth={1.5} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </ChartFrame>

            {/* Terminal Return Distribution Histogram */}
            <ChartFrame
                title="Terminal Return Frequency Distribution Histogram"
                description="Frequency distribution of net returns across 500 resampled simulations."
            >
                <div className="h-[220px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={mcResults.returnBins} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                            <CartesianGrid {...CHART_THEME.grid} />
                            <XAxis dataKey="range" {...CHART_THEME.axis} />
                            <YAxis {...CHART_THEME.axis} width={40} />
                            <Tooltip
                                contentStyle={CHART_THEME.tooltip.contentStyle}
                                itemStyle={CHART_THEME.tooltip.itemStyle}
                                formatter={(val: any) => [`${val} Paths`, "Frequency"]}
                            />
                            <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </ChartFrame>
        </div>
    )
}
