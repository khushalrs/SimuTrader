"use client"

import {
    Area,
    AreaChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
    CartesianGrid
} from "recharts"
import { Skeleton } from "@/components/ui/skeleton"
import { formatCurrency } from "@/lib/utils"
import { ChartFrame, CHART_THEME } from "./ChartFrame"

interface PerformanceChartProps {
    data?: { date: string; value: number }[]
    baseCurrency?: string
    onHover?: (point: { date: string; value: number } | null) => void
}

export function PerformanceChart({ data, baseCurrency, onHover }: PerformanceChartProps) {
    return (
        <ChartFrame title="Equity Curve" description="Net asset value over time (rebased to 100).">
            {!data || data.length === 0 ? (
                <Skeleton className="h-[350px] w-full" />
            ) : (
                <div className="h-[350px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart
                            data={data}
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
                            />
                            <Area
                                type="monotone"
                                dataKey="value"
                                stroke="hsl(var(--primary))"
                                fillOpacity={1}
                                fill="url(#colorEquity)"
                                strokeWidth={2}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}
        </ChartFrame>
    )
}
