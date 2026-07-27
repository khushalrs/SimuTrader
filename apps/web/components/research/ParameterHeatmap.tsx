"use client"

import { useState, useMemo } from "react"
import useSWR from "swr"
import { useRouter } from "next/navigation"
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
import { getResearchJobResults, ResearchSweepResultOut } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ChartFrame, CHART_THEME } from "@/components/run/ChartFrame"
import { Grid, Layers, Activity } from "lucide-react"

interface ParameterHeatmapProps {
    jobId: string
    onSelectRun?: (runId: string) => void
}

export function ParameterHeatmap({ jobId, onSelectRun }: ParameterHeatmapProps) {
    const router = useRouter()
    const { data: results } = useSWR<ResearchSweepResultOut[]>(
        jobId ? `/research/jobs/${jobId}/results` : null,
        () => getResearchJobResults(jobId),
        { refreshInterval: 3000 }
    )

    // Extract unique parameter keys dynamically
    const paramKeys = useMemo(() => {
        if (!results || results.length === 0) return []
        const keysSet = new Set<string>()
        results.forEach(r => {
            if (r.params) {
                Object.keys(r.params).forEach(k => keysSet.add(k))
            }
        })
        return Array.from(keysSet)
    }, [results])

    const [rowParam, setRowParam] = useState<string>("")
    const [colParam, setColParam] = useState<string>("")
    const [selectedMetric, setSelectedMetric] = useState<string>("sharpe")

    // Set defaults when paramKeys load
    const effectiveRowParam = rowParam || paramKeys[0] || ""
    const effectiveColParam = colParam || (paramKeys.length > 1 ? paramKeys[1] : "")

    // Single-parameter 1D line chart data
    const lineChartData = useMemo(() => {
        if (!results || results.length === 0 || !effectiveRowParam) return []

        return results
            .filter(r => r.params?.[effectiveRowParam] !== undefined && r.metrics)
            .map(r => ({
                paramVal: String(r.params[effectiveRowParam]),
                metricVal: Number((r.metrics as any)?.[selectedMetric] ?? 0),
                run_id: r.run_id,
                params: r.params
            }))
            .sort((a, b) => String(a.paramVal).localeCompare(String(b.paramVal), undefined, { numeric: true }))
    }, [results, effectiveRowParam, selectedMetric])

    // 2D Matrix Grid data calculation
    const matrixData = useMemo(() => {
        if (!results || results.length === 0 || !effectiveRowParam || !effectiveColParam) return null

        const rowValues = Array.from(new Set(results.map(r => String(r.params?.[effectiveRowParam] ?? "")))).filter(Boolean)
        const colValues = Array.from(new Set(results.map(r => String(r.params?.[effectiveColParam] ?? "")))).filter(Boolean)

        rowValues.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
        colValues.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))

        // Create lookup grid
        const grid: Record<string, Record<string, { val: number; run_id?: string | null; raw: ResearchSweepResultOut }>> = {}

        let minVal = Infinity
        let maxVal = -Infinity

        rowValues.forEach(rv => {
            grid[rv] = {}
            colValues.forEach(cv => {
                const match = results.find(
                    r => String(r.params?.[effectiveRowParam]) === rv && String(r.params?.[effectiveColParam]) === cv
                )
                if (match && match.metrics) {
                    const metricVal = Number((match.metrics as any)?.[selectedMetric] ?? 0)
                    grid[rv][cv] = { val: metricVal, run_id: match.run_id, raw: match }
                    if (metricVal < minVal) minVal = metricVal
                    if (metricVal > maxVal) maxVal = metricVal
                }
            })
        })

        if (minVal === Infinity) minVal = 0
        if (maxVal === -Infinity) maxVal = 1

        return { rowValues, colValues, grid, minVal, maxVal }
    }, [results, effectiveRowParam, effectiveColParam, selectedMetric])

    if (!results || results.length === 0 || paramKeys.length === 0) {
        return null
    }

    const formatMetricVal = (v: number) => {
        if (selectedMetric === "cagr" || selectedMetric === "volatility" || selectedMetric === "max_drawdown" || selectedMetric === "net_return") {
            return `${(v * 100).toFixed(1)}%`
        }
        return v.toFixed(2)
    }

    // Helper for 2D cell HSL color scaling
    const getCellColor = (val: number, min: number, max: number) => {
        if (min === max) return "hsl(var(--muted))"
        const range = max - min || 1
        const norm = (val - min) / range // 0 to 1

        if (val >= 0) {
            // Emerald tint
            const alpha = Math.max(0.15, Math.min(0.85, 0.2 + norm * 0.65))
            return `rgba(16, 185, 129, ${alpha})`
        } else {
            // Rose tint
            const alpha = Math.max(0.15, Math.min(0.85, 0.2 + (1 - norm) * 0.65))
            return `rgba(244, 63, 94, ${alpha})`
        }
    }

    const is2D = paramKeys.length >= 2 && effectiveColParam && effectiveRowParam !== effectiveColParam

    return (
        <Card className="border border-border shadow-sm">
            <CardHeader className="pb-3 border-b border-border/40 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <CardTitle className="text-base font-bold flex items-center gap-2">
                        <Grid className="w-4 h-4 text-primary" /> Parameter Heatmap & Stability Matrix
                    </CardTitle>
                    <CardDescription className="text-xs">
                        Evaluate parameter plateaus versus fragile lone spikes across optimization space.
                    </CardDescription>
                </div>

                <div className="flex items-center gap-3">
                    {/* Row Param Select */}
                    <div className="flex items-center gap-1.5">
                        <Label className="text-xs text-muted-foreground">{is2D ? "Row (Y):" : "Param:"}</Label>
                        <Select value={effectiveRowParam} onValueChange={setRowParam}>
                            <SelectTrigger className="h-7 text-xs font-mono w-32">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {paramKeys.map(k => (
                                    <SelectItem key={k} value={k} className="text-xs font-mono">{k}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Column Param Select if 2D */}
                    {paramKeys.length >= 2 && (
                        <div className="flex items-center gap-1.5">
                            <Label className="text-xs text-muted-foreground">Col (X):</Label>
                            <Select value={effectiveColParam} onValueChange={setColParam}>
                                <SelectTrigger className="h-7 text-xs font-mono w-32">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {paramKeys.map(k => (
                                        <SelectItem key={k} value={k} className="text-xs font-mono">{k}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    )}

                    {/* Metric Select */}
                    <div className="flex items-center gap-1.5">
                        <Label className="text-xs text-muted-foreground">Metric:</Label>
                        <Select value={selectedMetric} onValueChange={setSelectedMetric}>
                            <SelectTrigger className="h-7 text-xs font-mono w-32">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="sharpe" className="text-xs">Sharpe Ratio</SelectItem>
                                <SelectItem value="cagr" className="text-xs">CAGR</SelectItem>
                                <SelectItem value="volatility" className="text-xs">Volatility</SelectItem>
                                <SelectItem value="max_drawdown" className="text-xs">Max Drawdown</SelectItem>
                                <SelectItem value="net_return" className="text-xs">Net Return</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="pt-6">
                {is2D && matrixData ? (
                    <div className="space-y-3">
                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse text-xs font-mono">
                                <thead>
                                    <tr>
                                        <th className="p-2 border border-border/60 bg-muted/50 text-left font-semibold text-muted-foreground">
                                            {effectiveRowParam} \ {effectiveColParam}
                                        </th>
                                        {matrixData.colValues.map(cv => (
                                            <th key={cv} className="p-2 border border-border/60 bg-muted/50 text-center font-bold">
                                                {cv}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {matrixData.rowValues.map(rv => (
                                        <tr key={rv}>
                                            <td className="p-2 border border-border/60 bg-muted/50 font-bold text-left">
                                                {rv}
                                            </td>
                                            {matrixData.colValues.map(cv => {
                                                const cell = matrixData.grid[rv]?.[cv]
                                                if (!cell) {
                                                    return (
                                                        <td key={cv} className="p-2 border border-border/60 bg-muted/20 text-center text-muted-foreground">
                                                            —
                                                        </td>
                                                    )
                                                }

                                                const colorBg = getCellColor(cell.val, matrixData.minVal, matrixData.maxVal)

                                                return (
                                                    <td
                                                        key={cv}
                                                        style={{ backgroundColor: colorBg }}
                                                        className="p-3 border border-border/60 text-center font-bold font-mono transition-transform hover:scale-105 hover:z-10 cursor-pointer shadow-sm"
                                                        title={`${effectiveRowParam}: ${rv} | ${effectiveColParam}: ${cv} → ${selectedMetric.toUpperCase()}: ${formatMetricVal(cell.val)}`}
                                                        onClick={() => {
                                                            if (cell.run_id) {
                                                                if (onSelectRun) onSelectRun(cell.run_id)
                                                                else router.push(`/runs/${cell.run_id}`)
                                                            }
                                                        }}
                                                    >
                                                        {formatMetricVal(cell.val)}
                                                    </td>
                                                )
                                            })}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                            <span>Click any cell to open that child run dashboard.</span>
                            <div className="flex items-center gap-2">
                                <span className="text-[11px]">Low ({formatMetricVal(matrixData.minVal)})</span>
                                <div className="h-3 w-20 rounded bg-gradient-to-r from-rose-500 via-yellow-500 to-emerald-500" />
                                <span className="text-[11px]">High ({formatMetricVal(matrixData.maxVal)})</span>
                            </div>
                        </div>
                    </div>
                ) : (
                    /* 1D Parameter Line Sensitivity Chart */
                    <div className="h-[280px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={lineChartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                                <CartesianGrid {...CHART_THEME.grid} />
                                <XAxis
                                    dataKey="paramVal"
                                    {...CHART_THEME.axis}
                                    label={{ value: effectiveRowParam, position: "insideBottom", offset: -5, fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                                />
                                <YAxis
                                    {...CHART_THEME.axis}
                                    tickFormatter={v => formatMetricVal(v)}
                                    width={55}
                                />
                                <Tooltip
                                    contentStyle={CHART_THEME.tooltip.contentStyle}
                                    itemStyle={CHART_THEME.tooltip.itemStyle}
                                    formatter={(val: any) => [formatMetricVal(Number(val)), selectedMetric.toUpperCase()]}
                                />
                                {selectedMetric === "sharpe" && <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="3 3" />}
                                <Line
                                    type="monotone"
                                    dataKey="metricVal"
                                    name={selectedMetric.toUpperCase()}
                                    stroke="hsl(var(--primary))"
                                    strokeWidth={2.5}
                                    dot={{ r: 4, fill: "hsl(var(--primary))" }}
                                    activeDot={{ r: 6 }}
                                    onClick={(entry: any) => {
                                        if (entry?.run_id && onSelectRun) {
                                            onSelectRun(entry.run_id)
                                        }
                                    }}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
