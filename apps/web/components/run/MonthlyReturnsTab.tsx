"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { RunEquityPoint } from "@/lib/api"
import { ChartFrame } from "./ChartFrame"
import { Calendar, Info } from "lucide-react"

interface MonthlyReturnsTabProps {
    equity?: RunEquityPoint[]
    benchmarkEquity?: { date: string; value: number }[]
}

type ViewMode = "portfolio" | "benchmark" | "active"

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

export function MonthlyReturnsTab({ equity, benchmarkEquity }: MonthlyReturnsTabProps) {
    const [mode, setMode] = useState<ViewMode>("portfolio")
    const [hoveredCell, setHoveredCell] = useState<{
        year: number
        month: number
        portVal: number | null
        benchVal: number | null
        activeVal: number | null
    } | null>(null)

    // Compute monthly returns matrix
    const { matrix, years, maxAbsReturn, monthAverages } = useMemo(() => {
        if (!equity || equity.length < 2) {
            return { matrix: {}, years: [], maxAbsReturn: 0.05, monthAverages: {} }
        }

        // Helper: Calculate daily returns map by YYYY-MM
        const computeMonthlyReturns = (series: { date: string; value: number }[]) => {
            const byMonth: Record<string, { start: number; end: number }> = {}
            series.forEach(pt => {
                const yearMonth = pt.date.substring(0, 7) // "YYYY-MM"
                if (!byMonth[yearMonth]) {
                    byMonth[yearMonth] = { start: pt.value, end: pt.value }
                } else {
                    byMonth[yearMonth].end = pt.value
                }
            })

            const returns: Record<number, Record<number, number>> = {}
            Object.entries(byMonth).forEach(([ym, val]) => {
                const [yStr, mStr] = ym.split("-")
                const y = parseInt(yStr, 10)
                const m = parseInt(mStr, 10) - 1 // 0-indexed month
                const ret = val.start > 0 ? (val.end - val.start) / val.start : 0
                if (!returns[y]) returns[y] = {}
                returns[y][m] = ret
            })
            return returns
        }

        const portMonthly = computeMonthlyReturns(equity)
        const benchMonthly = benchmarkEquity && benchmarkEquity.length > 1 
            ? computeMonthlyReturns(benchmarkEquity) 
            : {}

        const allYearsSet = new Set<number>([
            ...Object.keys(portMonthly).map(Number),
            ...Object.keys(benchMonthly).map(Number)
        ])
        const sortedYears = Array.from(allYearsSet).sort((a, b) => b - a)

        let maxVal = 0.05
        const matrixData: Record<number, Record<number, { port: number | null; bench: number | null; active: number | null }>> = {}

        sortedYears.forEach(y => {
            matrixData[y] = {}
            for (let m = 0; m < 12; m++) {
                const portVal = portMonthly[y]?.[m] ?? null
                const benchVal = benchMonthly[y]?.[m] ?? null
                const activeVal = portVal !== null && benchVal !== null ? portVal - benchVal : portVal

                matrixData[y][m] = { port: portVal, bench: benchVal, active: activeVal }

                const checkVal = mode === "active" ? activeVal : mode === "benchmark" ? benchVal : portVal
                if (checkVal !== null) {
                    maxVal = Math.max(maxVal, Math.abs(checkVal))
                }
            }
        })

        // Compute average month row
        const monthAvgMap: Record<number, { portSum: number; portCount: number; benchSum: number; benchCount: number }> = {}
        for (let m = 0; m < 12; m++) {
            monthAvgMap[m] = { portSum: 0, portCount: 0, benchSum: 0, benchCount: 0 }
            sortedYears.forEach(y => {
                const cell = matrixData[y][m]
                if (cell.port !== null) {
                    monthAvgMap[m].portSum += cell.port
                    monthAvgMap[m].portCount++
                }
                if (cell.bench !== null) {
                    monthAvgMap[m].benchSum += cell.bench
                    monthAvgMap[m].benchCount++
                }
            })
        }

        const monthAvgs: Record<number, { port: number | null; bench: number | null; active: number | null }> = {}
        for (let m = 0; m < 12; m++) {
            const pAvg = monthAvgMap[m].portCount > 0 ? monthAvgMap[m].portSum / monthAvgMap[m].portCount : null
            const bAvg = monthAvgMap[m].benchCount > 0 ? monthAvgMap[m].benchSum / monthAvgMap[m].benchCount : null
            const aAvg = pAvg !== null && bAvg !== null ? pAvg - bAvg : pAvg
            monthAvgs[m] = { port: pAvg, bench: bAvg, active: aAvg }
        }

        return { matrix: matrixData, years: sortedYears, maxAbsReturn: maxVal, monthAverages: monthAvgs }
    }, [equity, benchmarkEquity, mode])

    if (!equity || equity.length === 0) {
        return (
            <Card className="p-8 text-center text-muted-foreground">
                No equity data available for monthly returns analysis.
            </Card>
        )
    }

    // Color generator based on return value and max absolute return
    const getCellColor = (val: number | null) => {
        if (val === null || val === undefined) return "transparent"
        if (Math.abs(val) < 0.0001) return "rgba(120, 120, 120, 0.15)"

        const intensity = Math.min(Math.abs(val) / (maxAbsReturn || 0.05), 1)
        const alpha = 0.15 + intensity * 0.65

        if (val > 0) {
            // Green scale
            return `rgba(34, 197, 94, ${alpha.toFixed(2)})`
        } else {
            // Red scale
            return `rgba(239, 68, 68, ${alpha.toFixed(2)})`
        }
    }

    const formatPct = (val: number | null, forceSign = false) => {
        if (val === null || val === undefined) return "—"
        const pct = (val * 100).toFixed(2)
        if (forceSign && val > 0) return `+${pct}%`
        return `${pct}%`
    }

    // Calculate annual compounded total for a year
    const getYearTotal = (year: number) => {
        let portComp = 1
        let benchComp = 1
        let hasPort = false
        let hasBench = false

        for (let m = 0; m < 12; m++) {
            const cell = matrix[year]?.[m]
            if (cell?.port !== null && cell?.port !== undefined) {
                portComp *= (1 + cell.port)
                hasPort = true
            }
            if (cell?.bench !== null && cell?.bench !== undefined) {
                benchComp *= (1 + cell.bench)
                hasBench = true
            }
        }

        const pTotal = hasPort ? portComp - 1 : null
        const bTotal = hasBench ? benchComp - 1 : null
        const aTotal = pTotal !== null && bTotal !== null ? pTotal - bTotal : pTotal

        return { port: pTotal, bench: bTotal, active: aTotal }
    }

    const hasBenchmark = benchmarkEquity && benchmarkEquity.length > 0

    return (
        <ChartFrame
            title="Monthly Returns Heatmap"
            description="Monthly return breakdown and seasonal performance analysis."
            action={
                <div className="flex items-center gap-1.5 bg-muted/50 p-1 rounded-lg border border-border/50">
                    <Button
                        variant={mode === "portfolio" ? "default" : "ghost"}
                        size="sm"
                        className="h-7 text-xs px-2.5"
                        onClick={() => setMode("portfolio")}
                    >
                        Portfolio
                    </Button>
                    <Button
                        variant={mode === "benchmark" ? "default" : "ghost"}
                        size="sm"
                        className="h-7 text-xs px-2.5"
                        disabled={!hasBenchmark}
                        onClick={() => setMode("benchmark")}
                    >
                        Benchmark
                    </Button>
                    <Button
                        variant={mode === "active" ? "default" : "ghost"}
                        size="sm"
                        className="h-7 text-xs px-2.5"
                        disabled={!hasBenchmark}
                        onClick={() => setMode("active")}
                    >
                        Active (Excess)
                    </Button>
                </div>
            }
        >
            <div className="space-y-4">
                {/* Heatmap Table */}
                <div className="overflow-x-auto rounded-lg border border-border/50">
                    <table className="w-full text-xs border-collapse">
                        <thead>
                            <tr className="border-b border-border bg-muted/40">
                                <th className="p-2 text-left font-semibold text-muted-foreground w-16">Year</th>
                                {MONTH_NAMES.map(m => (
                                    <th key={m} className="p-2 text-center font-semibold text-muted-foreground">
                                        {m}
                                    </th>
                                ))}
                                <th className="p-2 text-center font-semibold text-foreground bg-muted/60 border-l border-border/50 w-20">
                                    Annual
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {years.map(y => {
                                const annualTot = getYearTotal(y)
                                const activeAnnualVal = mode === "active" ? annualTot.active : mode === "benchmark" ? annualTot.bench : annualTot.port

                                return (
                                    <tr key={y} className="border-b border-border/30 hover:bg-muted/20 transition-colors">
                                        <td className="p-2 font-semibold text-foreground bg-muted/20">{y}</td>
                                        {MONTH_NAMES.map((_, m) => {
                                            const cell = matrix[y]?.[m]
                                            const val = mode === "active" ? cell?.active : mode === "benchmark" ? cell?.bench : cell?.port

                                            return (
                                                <td
                                                    key={m}
                                                    className="p-1 text-center transition-transform hover:scale-105"
                                                    onMouseEnter={() => setHoveredCell({
                                                        year: y,
                                                        month: m,
                                                        portVal: cell?.port ?? null,
                                                        benchVal: cell?.bench ?? null,
                                                        activeVal: cell?.active ?? null
                                                    })}
                                                    onMouseLeave={() => setHoveredCell(null)}
                                                >
                                                    <div
                                                        className="h-8 rounded flex items-center justify-center font-medium font-mono text-[11px] cursor-default border border-black/5 dark:border-white/5"
                                                        style={{ backgroundColor: getCellColor(val ?? null) }}
                                                    >
                                                        {formatPct(val ?? null)}
                                                    </div>
                                                </td>
                                            )
                                        })}
                                        <td className="p-1 text-center bg-muted/30 border-l border-border/50 font-bold font-mono">
                                            <div
                                                className="h-8 rounded flex items-center justify-center border border-black/5 dark:border-white/5"
                                                style={{ backgroundColor: getCellColor(activeAnnualVal) }}
                                            >
                                                {formatPct(activeAnnualVal, true)}
                                            </div>
                                        </td>
                                    </tr>
                                )
                            })}

                            {/* Average Month Row */}
                            <tr className="bg-muted/50 font-semibold border-t-2 border-border">
                                <td className="p-2 text-foreground">Avg Month</td>
                                {MONTH_NAMES.map((_, m) => {
                                    const avgCell = monthAverages[m]
                                    const avgVal = mode === "active" ? avgCell?.active : mode === "benchmark" ? avgCell?.bench : avgCell?.port
                                    return (
                                        <td key={m} className="p-1 text-center">
                                            <div
                                                className="h-7 rounded flex items-center justify-center font-mono text-[11px]"
                                                style={{ backgroundColor: getCellColor(avgVal ?? null) }}
                                            >
                                                {formatPct(avgVal ?? null)}
                                            </div>
                                        </td>
                                    )
                                })}
                                <td className="p-1 text-center bg-muted/70 border-l border-border/50 font-mono text-[11px]">
                                    —
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                {/* Cell Hover Detail / Legend Footer */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 p-3 bg-muted/20 rounded-md border border-border/40 text-xs">
                    {hoveredCell ? (
                        <div className="flex items-center gap-4 font-mono">
                            <span className="font-semibold text-foreground">
                                {MONTH_NAMES[hoveredCell.month]} {hoveredCell.year}:
                            </span>
                            <span>Portfolio: <strong className="text-foreground">{formatPct(hoveredCell.portVal, true)}</strong></span>
                            {hasBenchmark && (
                                <>
                                    <span>Benchmark: <strong className="text-foreground">{formatPct(hoveredCell.benchVal, true)}</strong></span>
                                    <span>Active Delta: <strong className="text-foreground">{formatPct(hoveredCell.activeVal, true)}</strong></span>
                                </>
                            )}
                        </div>
                    ) : (
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                            <Info className="w-3.5 h-3.5" />
                            <span>Hover over any month cell to view detailed return breakdown.</span>
                        </div>
                    )}

                    {/* Scale legend */}
                    <div className="flex items-center gap-1.5 shrink-0 text-[11px] text-muted-foreground">
                        <span>Negative</span>
                        <div className="w-4 h-3 rounded" style={{ backgroundColor: "rgba(239, 68, 68, 0.75)" }} />
                        <div className="w-4 h-3 rounded" style={{ backgroundColor: "rgba(239, 68, 68, 0.3)" }} />
                        <div className="w-4 h-3 rounded" style={{ backgroundColor: "rgba(120, 120, 120, 0.2)" }} />
                        <div className="w-4 h-3 rounded" style={{ backgroundColor: "rgba(34, 197, 94, 0.3)" }} />
                        <div className="w-4 h-3 rounded" style={{ backgroundColor: "rgba(34, 197, 94, 0.75)" }} />
                        <span>Positive</span>
                    </div>
                </div>
            </div>
        </ChartFrame>
    )
}
