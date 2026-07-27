"use client"

import { useMemo } from "react"
import useSWR from "swr"
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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { ChartFrame, CHART_THEME } from "@/components/run/ChartFrame"
import { GitCompare, ShieldAlert, CheckCircle2, TrendingDown, ArrowRight } from "lucide-react"

interface ISOOSComparisonProps {
    isMetrics?: {
        sharpe?: number
        cagr?: number
        volatility?: number
        max_drawdown?: number
        net_return?: number
    }
    oosMetrics?: {
        sharpe?: number
        cagr?: number
        volatility?: number
        max_drawdown?: number
        net_return?: number
    }
    equityPoints?: Array<{ date: string; isEquity?: number; oosEquity?: number }>
}

export function ISOOSComparison({
    isMetrics = { sharpe: 1.85, cagr: 0.245, volatility: 0.132, max_drawdown: -0.105, net_return: 0.245 },
    oosMetrics = { sharpe: 1.42, cagr: 0.178, volatility: 0.141, max_drawdown: -0.138, net_return: 0.178 },
    equityPoints
}: ISOOSComparisonProps) {
    // Degradation ratio calculation
    const isSharpe = isMetrics.sharpe || 1.0
    const oosSharpe = oosMetrics.sharpe || 0.8
    const degradationRatio = Math.max(0, 1.0 - oosSharpe / isSharpe)

    const isDegradationSevere = degradationRatio > 0.35
    const isDegradationModerate = degradationRatio >= 0.15 && degradationRatio <= 0.35

    // Synthetic demo equity points if not provided
    const chartData = useMemo(() => {
        if (equityPoints && equityPoints.length > 0) return equityPoints

        // Fallback demo points
        const points = []
        let isVal = 100000
        let oosVal = 100000
        const total = 100
        const isSplit = 60

        for (let i = 0; i < total; i++) {
            const date = `2024-${String(Math.floor(i / 30) + 1).padStart(2, '0')}-${String((i % 30) + 1).padStart(2, '0')}`
            if (i <= isSplit) {
                isVal += (Math.random() - 0.42) * 800
                points.push({ date, isEquity: Math.round(isVal), oosEquity: undefined })
                if (i === isSplit) oosVal = isVal
            } else {
                oosVal += (Math.random() - 0.46) * 850
                points.push({ date, isEquity: undefined, oosEquity: Math.round(oosVal) })
            }
        }
        return points
    }, [equityPoints])

    return (
        <div className="space-y-6">
            {/* Top Row: Degradation Ratio & Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className={`border ${isDegradationSevere ? "border-rose-500/40 bg-rose-500/5" : isDegradationModerate ? "border-amber-500/40 bg-amber-500/5" : "border-emerald-500/40 bg-emerald-500/5"}`}>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">In-Sample vs OOS Degradation</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-baseline justify-between">
                            <div className={`text-3xl font-bold font-mono ${isDegradationSevere ? "text-rose-500" : isDegradationModerate ? "text-amber-500" : "text-emerald-600"}`}>
                                {(degradationRatio * 100).toFixed(1)}%
                            </div>
                            <Badge variant={isDegradationSevere ? "destructive" : isDegradationModerate ? "secondary" : "default"}>
                                {isDegradationSevere ? "Severe Overfit" : isDegradationModerate ? "Moderate Decay" : "Minimal Decay"}
                            </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                            {isDegradationSevere
                                ? "Out-of-sample performance suffered significant degradation (>35%). High overfit risk."
                                : isDegradationModerate
                                ? "Moderate performance decay observed in out-of-sample period."
                                : "Out-of-sample performance maintained consistency with in-sample period."}
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">In-Sample Sharpe Ratio</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold font-mono text-foreground">
                            {isMetrics.sharpe?.toFixed(2) || "—"}
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">Training / optimization window performance.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Out-of-Sample Sharpe Ratio</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold font-mono text-primary">
                            {oosMetrics.sharpe?.toFixed(2) || "—"}
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">Validation / un-optimized window performance.</p>
                    </CardContent>
                </Card>
            </div>

            {/* Overlaid Equity Curve Chart */}
            <ChartFrame
                title="In-Sample vs Out-of-Sample Overlaid Equity Curve"
                description="Solid line indicates in-sample training window; dashed line represents out-of-sample validation period."
            >
                <div className="h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                            <CartesianGrid {...CHART_THEME.grid} />
                            <XAxis dataKey="date" {...CHART_THEME.axis} minTickGap={30} />
                            <YAxis
                                {...CHART_THEME.axis}
                                tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                                width={55}
                            />
                            <Tooltip
                                contentStyle={CHART_THEME.tooltip.contentStyle}
                                itemStyle={CHART_THEME.tooltip.itemStyle}
                                formatter={(val: any, name: any) => [`$${Number(val).toLocaleString()}`, name === "isEquity" ? "In-Sample" : "Out-of-Sample"]}
                            />
                            <Line
                                type="monotone"
                                dataKey="isEquity"
                                name="In-Sample"
                                stroke="hsl(var(--primary))"
                                strokeWidth={2}
                                dot={false}
                                connectNulls
                            />
                            <Line
                                type="monotone"
                                dataKey="oosEquity"
                                name="Out-of-Sample"
                                stroke="hsl(var(--destructive))"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                                connectNulls
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </ChartFrame>

            {/* Side-by-Side Metric Comparison Table */}
            <Card className="border border-border shadow-sm">
                <CardHeader className="pb-3 border-b border-border/40">
                    <CardTitle className="text-base font-bold flex items-center gap-2">
                        <GitCompare className="w-4 h-4 text-primary" /> Side-by-Side In-Sample vs OOS Metrics
                    </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow className="bg-muted/40 text-xs">
                                <TableHead className="font-semibold">Performance Metric</TableHead>
                                <TableHead className="text-right font-semibold">In-Sample (IS)</TableHead>
                                <TableHead className="text-right font-semibold">Out-of-Sample (OOS)</TableHead>
                                <TableHead className="text-right font-semibold">Decay / Change</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody className="text-xs">
                            <TableRow>
                                <TableCell className="font-medium">Sharpe Ratio</TableCell>
                                <TableCell className="text-right font-mono font-bold">{isMetrics.sharpe?.toFixed(2) ?? "—"}</TableCell>
                                <TableCell className="text-right font-mono font-bold text-primary">{oosMetrics.sharpe?.toFixed(2) ?? "—"}</TableCell>
                                <TableCell className={`text-right font-mono font-bold ${isDegradationSevere ? "text-rose-500" : "text-emerald-600"}`}>
                                    -{(degradationRatio * 100).toFixed(1)}%
                                </TableCell>
                            </TableRow>

                            <TableRow>
                                <TableCell className="font-medium">CAGR</TableCell>
                                <TableCell className="text-right font-mono">{( (isMetrics.cagr || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono font-semibold">{((oosMetrics.cagr || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono">
                                    {(((oosMetrics.cagr || 0) - (isMetrics.cagr || 0)) * 100).toFixed(1)}%
                                </TableCell>
                            </TableRow>

                            <TableRow>
                                <TableCell className="font-medium">Volatility</TableCell>
                                <TableCell className="text-right font-mono">{((isMetrics.volatility || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono">{((oosMetrics.volatility || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono">
                                    {(((oosMetrics.volatility || 0) - (isMetrics.volatility || 0)) * 100).toFixed(1)}%
                                </TableCell>
                            </TableRow>

                            <TableRow>
                                <TableCell className="font-medium">Max Drawdown</TableCell>
                                <TableCell className="text-right font-mono text-rose-500">{((isMetrics.max_drawdown || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono text-rose-500">{((oosMetrics.max_drawdown || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono text-rose-500">
                                    {(((oosMetrics.max_drawdown || 0) - (isMetrics.max_drawdown || 0)) * 100).toFixed(1)}%
                                </TableCell>
                            </TableRow>

                            <TableRow>
                                <TableCell className="font-medium">Net Return</TableCell>
                                <TableCell className="text-right font-mono">{((isMetrics.net_return || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono">{((oosMetrics.net_return || 0) * 100).toFixed(1)}%</TableCell>
                                <TableCell className="text-right font-mono">
                                    {(((oosMetrics.net_return || 0) - (isMetrics.net_return || 0)) * 100).toFixed(1)}%
                                </TableCell>
                            </TableRow>
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    )
}
