"use client"

import { useState, useMemo } from "react"
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine
} from "recharts"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { RunEquityPoint } from "@/lib/api"
import { ChartFrame, CHART_THEME } from "./ChartFrame"

interface RollingMetricsTabProps {
    equity?: RunEquityPoint[]
    benchmarkEquity?: { date: string; value: number }[]
}

type WindowSize = 21 | 63 | 126 | 252
type MetricType = "sharpe" | "volatility" | "beta"

export function RollingMetricsTab({ equity, benchmarkEquity }: RollingMetricsTabProps) {
    const [windowSize, setWindowSize] = useState<WindowSize>(63)
    const [metric, setMetric] = useState<MetricType>("sharpe")

    const hasBenchmark = benchmarkEquity && benchmarkEquity.length > 0

    const chartData = useMemo(() => {
        if (!equity || equity.length <= windowSize) return []

        // Daily returns calculation
        const portReturns: { date: string; ret: number }[] = []
        for (let i = 1; i < equity.length; i++) {
            const prev = equity[i - 1].value
            const curr = equity[i].value
            if (prev > 0) {
                portReturns.push({
                    date: equity[i].date,
                    ret: (curr - prev) / prev
                })
            }
        }

        // Benchmark daily returns calculation
        const benchReturnsMap: Record<string, number> = {}
        if (hasBenchmark) {
            for (let i = 1; i < benchmarkEquity.length; i++) {
                const prev = benchmarkEquity[i - 1].value
                const curr = benchmarkEquity[i].value
                if (prev > 0) {
                    benchReturnsMap[benchmarkEquity[i].date] = (curr - prev) / prev
                }
            }
        }

        const points: { date: string; value: number }[] = []

        for (let i = windowSize - 1; i < portReturns.length; i++) {
            const slice = portReturns.slice(i - windowSize + 1, i + 1)
            const date = portReturns[i].date

            const returns = slice.map(s => s.ret)
            const mean = returns.reduce((a, b) => a + b, 0) / returns.length
            const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (returns.length - 1 || 1)
            const stdDev = Math.sqrt(variance)

            if (metric === "volatility") {
                const annVol = stdDev * Math.sqrt(252)
                points.push({ date, value: annVol })
            } else if (metric === "sharpe") {
                const annSharpe = stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0
                points.push({ date, value: annSharpe })
            } else if (metric === "beta" && hasBenchmark) {
                const benchSlice = slice.map(s => benchReturnsMap[s.date] ?? 0)
                const benchMean = benchSlice.reduce((a, b) => a + b, 0) / benchSlice.length
                const benchVar = benchSlice.reduce((a, b) => a + Math.pow(b - benchMean, 2), 0) / (benchSlice.length - 1 || 1)

                let cov = 0
                for (let k = 0; k < slice.length; k++) {
                    cov += (slice[k].ret - mean) * (benchSlice[k] - benchMean)
                }
                cov = cov / (slice.length - 1 || 1)

                const betaVal = benchVar > 0 ? cov / benchVar : 1.0
                points.push({ date, value: betaVal })
            }
        }

        return points
    }, [equity, benchmarkEquity, windowSize, metric, hasBenchmark])

    if (!equity || equity.length <= 21) {
        return (
            <Card className="p-8 text-center text-muted-foreground">
                Insufficient equity history to calculate rolling metrics (minimum 21 trading days required).
            </Card>
        )
    }

    const metricTitle = metric === "sharpe" 
        ? "Rolling Sharpe Ratio" 
        : metric === "volatility" 
            ? "Rolling Annualized Volatility" 
            : "Rolling Beta (vs Benchmark)"

    const metricDesc = metric === "sharpe"
        ? `Annualized Sharpe ratio computed over a ${windowSize}-day rolling window.`
        : metric === "volatility"
            ? `Annualized daily return standard deviation over a ${windowSize}-day rolling window.`
            : `Systematic risk exposure relative to benchmark over a ${windowSize}-day rolling window.`

    const referenceY = metric === "sharpe" ? 0 : metric === "volatility" ? 0 : 1.0

    return (
        <ChartFrame
            title={metricTitle}
            description={metricDesc}
            action={
                <div className="flex flex-wrap items-center gap-2">
                    {/* Window Size Selector */}
                    <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-lg border border-border/50">
                        {([21, 63, 126, 252] as WindowSize[]).map(w => (
                            <Button
                                key={w}
                                variant={windowSize === w ? "default" : "ghost"}
                                size="sm"
                                className="h-7 text-xs px-2"
                                onClick={() => setWindowSize(w)}
                            >
                                {w === 21 ? "1M" : w === 63 ? "3M" : w === 126 ? "6M" : "1Y"} ({w}d)
                            </Button>
                        ))}
                    </div>

                    {/* Metric Selector */}
                    <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-lg border border-border/50">
                        <Button
                            variant={metric === "sharpe" ? "default" : "ghost"}
                            size="sm"
                            className="h-7 text-xs px-2.5"
                            onClick={() => setMetric("sharpe")}
                        >
                            Sharpe
                        </Button>
                        <Button
                            variant={metric === "volatility" ? "default" : "ghost"}
                            size="sm"
                            className="h-7 text-xs px-2.5"
                            onClick={() => setMetric("volatility")}
                        >
                            Volatility
                        </Button>
                        <Button
                            variant={metric === "beta" ? "default" : "ghost"}
                            size="sm"
                            className="h-7 text-xs px-2.5"
                            disabled={!hasBenchmark}
                            onClick={() => setMetric("beta")}
                        >
                            Beta
                        </Button>
                    </div>
                </div>
            }
        >
            <div className="h-[380px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                        <CartesianGrid {...CHART_THEME.grid} />
                        <XAxis dataKey="date" {...CHART_THEME.axis} />
                        <YAxis
                            {...CHART_THEME.axis}
                            domain={['auto', 'auto']}
                            tickFormatter={(v) => metric === "volatility" ? `${(v * 100).toFixed(1)}%` : v.toFixed(2)}
                            width={55}
                        />
                        <Tooltip
                            contentStyle={CHART_THEME.tooltip.contentStyle}
                            itemStyle={CHART_THEME.tooltip.itemStyle}
                            formatter={(value: any) => [
                                metric === "volatility" ? `${((Number(value) || 0) * 100).toFixed(2)}%` : Number(value).toFixed(3),
                                metric === "sharpe" ? "Sharpe" : metric === "volatility" ? "Volatility" : "Beta"
                            ]}
                        />
                        <ReferenceLine
                            y={referenceY}
                            stroke="hsl(var(--muted-foreground))"
                            strokeDasharray="3 3"
                            strokeOpacity={0.6}
                            label={{
                                value: metric === "sharpe" ? "y = 0" : metric === "beta" ? "β = 1.0" : "y = 0",
                                fill: "hsl(var(--muted-foreground))",
                                fontSize: 10,
                                position: "insideTopRight"
                            }}
                        />
                        <Line
                            type="monotone"
                            dataKey="value"
                            stroke="hsl(var(--primary))"
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4 }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </ChartFrame>
    )
}
