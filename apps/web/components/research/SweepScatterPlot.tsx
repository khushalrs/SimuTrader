"use client"

import { useState, useMemo } from "react"
import useSWR from "swr"
import {
    ScatterChart,
    Scatter,
    XAxis,
    YAxis,
    ZAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer
} from "recharts"
import { getResearchJobResults, ResearchSweepResultOut } from "@/lib/api"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { ChartFrame, CHART_THEME } from "@/components/run/ChartFrame"

interface SweepScatterPlotProps {
    jobId: string
    onSelectRun?: (runId: string) => void
}

export function SweepScatterPlot({ jobId, onSelectRun }: SweepScatterPlotProps) {
    const { data: results } = useSWR<ResearchSweepResultOut[]>(
        jobId ? `/research/jobs/${jobId}/results` : null,
        () => getResearchJobResults(jobId),
        { refreshInterval: 3000 }
    )

    // Extract parameter keys dynamically
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

    const [xKey, setXKey] = useState<string>("")
    const [yKey, setYKey] = useState<string>("sharpe")

    // Set initial X key once paramKeys loaded
    const effectiveXKey = xKey || paramKeys[0] || ""

    const scatterData = useMemo(() => {
        if (!results || results.length === 0 || !effectiveXKey) return []

        return results
            .filter(r => r.metrics && r.params?.[effectiveXKey] !== undefined)
            .map(r => {
                const xVal = Number(r.params?.[effectiveXKey])
                const yVal = Number((r.metrics as any)?.[yKey] ?? 0)

                return {
                    x: isNaN(xVal) ? 0 : xVal,
                    y: isNaN(yVal) ? 0 : yVal,
                    paramLabel: `${effectiveXKey} = ${r.params?.[effectiveXKey]}`,
                    run_id: r.run_id,
                    params: r.params,
                    metrics: r.metrics
                }
            })
    }, [results, effectiveXKey, yKey])

    if (!results || results.length === 0 || paramKeys.length === 0) {
        return null
    }

    return (
        <ChartFrame
            title="Parameter Sensitivity & Trade-off Scatter Plot"
            description="Visualize performance metrics against parameter variations."
            action={
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5">
                        <Label className="text-xs text-muted-foreground">X (Param):</Label>
                        <Select value={effectiveXKey} onValueChange={setXKey}>
                            <SelectTrigger className="h-7 text-xs font-mono w-36">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {paramKeys.map(k => (
                                    <SelectItem key={k} value={k} className="text-xs font-mono">{k}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="flex items-center gap-1.5">
                        <Label className="text-xs text-muted-foreground">Y (Metric):</Label>
                        <Select value={yKey} onValueChange={setYKey}>
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
            }
        >
            <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
                        <CartesianGrid {...CHART_THEME.grid} />
                        <XAxis
                            type="number"
                            dataKey="x"
                            name={effectiveXKey}
                            {...CHART_THEME.axis}
                            label={{ value: effectiveXKey, position: "insideBottom", offset: -5, fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                        />
                        <YAxis
                            type="number"
                            dataKey="y"
                            name={yKey}
                            {...CHART_THEME.axis}
                            tickFormatter={(v) => yKey === "cagr" || yKey === "volatility" || yKey === "max_drawdown" || yKey === "net_return" ? `${(v * 100).toFixed(1)}%` : v.toFixed(2)}
                            width={55}
                        />
                        <ZAxis range={[60, 60]} />
                        <Tooltip
                            contentStyle={CHART_THEME.tooltip.contentStyle}
                            itemStyle={CHART_THEME.tooltip.itemStyle}
                            formatter={(val: any, name: any) => [
                                name === effectiveXKey ? val : yKey === "sharpe" ? Number(val).toFixed(2) : `${(Number(val) * 100).toFixed(2)}%`,
                                name
                            ]}
                        />
                        <Scatter
                            name="Sweep Runs"
                            data={scatterData}
                            fill="hsl(var(--primary))"
                            className="cursor-pointer hover:opacity-80"
                            onClick={(entry: any) => {
                                if (entry?.run_id && onSelectRun) {
                                    onSelectRun(entry.run_id)
                                }
                            }}
                        />
                    </ScatterChart>
                </ResponsiveContainer>
            </div>
        </ChartFrame>
    )
}
