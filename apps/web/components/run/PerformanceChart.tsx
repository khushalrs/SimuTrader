"use client"

import { useState, useMemo } from "react"
import {
    Area,
    AreaChart,
    Line,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
    CartesianGrid,
    BarChart,
    Bar,
    Cell
} from "recharts"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { formatCurrency } from "@/lib/utils"
import { ChartFrame, CHART_THEME } from "./ChartFrame"
import { TrendingUp, Layers } from "lucide-react"

interface PerformanceChartProps {
    data?: { date: string; value: number }[]
    benchmarkData?: { date: string; value: number }[]
    baseCurrency?: string
    onHover?: (point: { date: string; value: number } | null) => void
}

export function PerformanceChart({ data, benchmarkData, baseCurrency, onHover }: PerformanceChartProps) {
    const [showBenchmark, setShowBenchmark] = useState(true)

    const hasBenchmark = benchmarkData && benchmarkData.length > 0

    // Merge portfolio equity and normalized benchmark data
    const { combinedData, hasValidExcess } = useMemo(() => {
        if (!data || data.length === 0) return { combinedData: [], hasValidExcess: false }

        const initialPortVal = data[0].value
        const benchMap: Record<string, number> = {}

        if (hasBenchmark && benchmarkData.length > 0) {
            const initialBenchVal = benchmarkData[0].value
            benchmarkData.forEach(pt => {
                // Rebase benchmark to start at same value as portfolio initial capital
                if (initialBenchVal > 0) {
                    const rebased = (pt.value / initialBenchVal) * initialPortVal
                    benchMap[pt.date] = rebased
                }
            })
        }

        const initialBenchRebased = hasBenchmark ? benchMap[data[0].date] || initialPortVal : initialPortVal

        const combined = data.map((pt, idx) => {
            const benchVal = hasBenchmark ? (benchMap[pt.date] ?? null) : null
            
            let portCumReturn = initialPortVal > 0 ? (pt.value - initialPortVal) / initialPortVal : 0
            let benchCumReturn = 0
            let excessReturn = 0

            if (benchVal !== null && initialBenchRebased > 0) {
                benchCumReturn = (benchVal - initialBenchRebased) / initialBenchRebased
                excessReturn = portCumReturn - benchCumReturn
            }

            return {
                date: pt.date,
                value: pt.value,
                benchmarkValue: benchVal,
                portCumReturn,
                benchCumReturn,
                excessReturn
            }
        })

        const validExcess = hasBenchmark && combined.some(c => c.benchmarkValue !== null)

        return { combinedData: combined, hasValidExcess: validExcess }
    }, [data, benchmarkData, hasBenchmark])

    return (
        <ChartFrame
            title="Equity Curve"
            description="Net asset value over time (rebased to initial capital)."
            action={
                hasValidExcess ? (
                    <Button
                        variant={showBenchmark ? "default" : "outline"}
                        size="sm"
                        className="h-7 text-xs gap-1.5"
                        onClick={() => setShowBenchmark(prev => !prev)}
                    >
                        <Layers className="w-3.5 h-3.5" />
                        {showBenchmark ? "Hide Benchmark" : "Show Benchmark"}
                    </Button>
                ) : undefined
            }
        >
            {!data || data.length === 0 ? (
                <Skeleton className="h-[350px] w-full" />
            ) : (
                <div className="space-y-4">
                    {/* Primary Equity Chart */}
                    <div className="h-[320px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart
                                data={combinedData}
                                onMouseMove={(state: any) => {
                                    if (state.isTooltipActive && state.activePayload && state.activePayload.length > 0) {
                                        onHover?.(state.activePayload[0].payload)
                                    }
                                }}
                                onMouseLeave={() => onHover?.(null)}
                            >
                                <defs>
                                    <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <XAxis
                                    dataKey="date"
                                    {...CHART_THEME.axis}
                                />
                                <YAxis
                                    {...CHART_THEME.axis}
                                    tickFormatter={(value) => {
                                        if (Math.abs(value) >= 1000000) {
                                            return formatCurrency(value / 1000000, baseCurrency, true) + 'M';
                                        }
                                        return formatCurrency(value, baseCurrency, true);
                                    }}
                                    domain={['auto', 'auto']}
                                    width={80}
                                />
                                <CartesianGrid {...CHART_THEME.grid} />
                                <Tooltip
                                    contentStyle={CHART_THEME.tooltip.contentStyle}
                                    itemStyle={CHART_THEME.tooltip.itemStyle}
                                    formatter={(val: any, name: any) => [
                                        formatCurrency(Number(val) || 0, baseCurrency),
                                        name === "value" ? "Portfolio Equity" : "Benchmark (Rebased)"
                                    ]}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="value"
                                    name="Portfolio Equity"
                                    stroke="hsl(var(--primary))"
                                    fillOpacity={1}
                                    fill="url(#colorEquity)"
                                    strokeWidth={2}
                                />
                                {hasValidExcess && showBenchmark && (
                                    <Line
                                        type="monotone"
                                        dataKey="benchmarkValue"
                                        name="Benchmark (Rebased)"
                                        stroke="hsl(var(--muted-foreground))"
                                        strokeDasharray="4 4"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                )}
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Excess Return Sub-strip */}
                    {hasValidExcess && showBenchmark && (
                        <div className="pt-2 border-t border-border/40 space-y-1">
                            <div className="flex items-center justify-between text-xs text-muted-foreground font-medium px-1">
                                <span className="flex items-center gap-1">
                                    <TrendingUp className="w-3.5 h-3.5 text-primary" />
                                    Excess Return Strip (Portfolio vs Benchmark Delta)
                                </span>
                                <span className="font-mono text-[11px]">
                                    Latest Excess: {((combinedData[combinedData.length - 1]?.excessReturn || 0) * 100).toFixed(2)}%
                                </span>
                            </div>
                            <div className="h-[75px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={combinedData} margin={{ top: 5, right: 0, left: 80, bottom: 0 }}>
                                        <XAxis dataKey="date" hide />
                                        <YAxis
                                            {...CHART_THEME.axis}
                                            tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
                                            domain={['auto', 'auto']}
                                            width={80}
                                        />
                                        <Tooltip
                                            contentStyle={CHART_THEME.tooltip.contentStyle}
                                            itemStyle={CHART_THEME.tooltip.itemStyle}
                                            formatter={(v: any) => [`${((Number(v) || 0) * 100).toFixed(2)}%`, "Excess Return"]}
                                        />
                                        <Bar dataKey="excessReturn" name="Excess Return">
                                            {combinedData.map((entry, index) => (
                                                <Cell
                                                    key={`cell-${index}`}
                                                    fill={entry.excessReturn >= 0 ? "rgba(34, 197, 94, 0.7)" : "rgba(239, 68, 68, 0.7)"}
                                                />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </ChartFrame>
    )
}
