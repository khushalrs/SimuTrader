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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const DEFAULT_DATA = [
    { date: "Jan 01", value: 100 },
    { date: "Jan 08", value: 102 },
    { date: "Jan 15", value: 105 },
    { date: "Jan 22", value: 103 },
    { date: "Jan 29", value: 107 },
    { date: "Feb 05", value: 106 },
    { date: "Feb 12", value: 110 },
    { date: "Feb 19", value: 115 },
    { date: "Feb 26", value: 114 },
    { date: "Mar 05", value: 118 },
]

interface PerformanceChartProps {
    data?: { date: string; value: number }[]
}

export function PerformanceChart({ data }: PerformanceChartProps) {
    const chartData = data && data.length > 0 ? data : DEFAULT_DATA

    return (
        <Card className="col-span-3">
            <CardHeader>
                <CardTitle>Equity Curve</CardTitle>
                <CardDescription>
                    Net asset value over time (rebased to 100).
                </CardDescription>
            </CardHeader>
            <CardContent className="pl-2">
                <div className="h-[350px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                            <defs>
                                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <XAxis
                                dataKey="date"
                                stroke="#888888"
                                fontSize={12}
                                tickLine={false}
                                axisLine={false}
                            />
                            <YAxis
                                stroke="#888888"
                                fontSize={12}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={(value) => `$${value}`}
                                domain={['dataMin - 5', 'dataMax + 5']}
                            />
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                            <Tooltip
                                contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                itemStyle={{ color: 'hsl(var(--foreground))' }}
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
            </CardContent>
        </Card>
    )
}
