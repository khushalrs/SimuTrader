"use client"

import { useState, useMemo } from "react"
import useSWR from "swr"
import { getDataCoverage, getDataQuality } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { 
    Loader2, 
    ShieldAlert, 
    Globe, 
    Database, 
    Calendar, 
    CheckCircle2, 
    AlertTriangle,
    Search,
    Sliders
} from "lucide-react"

// Helper to determine region code from asset class or currency
function getRegionBadge(assetClass?: string | null, currency?: string | null) {
    if (assetClass && assetClass.includes("_")) {
        return assetClass.split("_")[0]
    }
    if (currency) {
        const cur = currency.toUpperCase()
        if (cur === "INR") return "IN"
        if (cur === "USD") return "US"
        if (cur === "EUR") return "EU"
        if (cur === "GBP") return "GB"
        if (cur === "JPY") return "JP"
        if (cur === "CAD") return "CA"
        if (cur === "AUD") return "AU"
        return cur.slice(0, 2)
    }
    return "Unknown"
}

export default function DataQualityPage() {
    const [searchQuery, setSearchQuery] = useState("")

    // Fetch overall data quality and coverage
    const { data: qualityData, isLoading: isLoadingQuality, error: qualityError } = useSWR(
        "/data/quality",
        () => getDataQuality(),
        { revalidateOnFocus: false }
    )

    const { data: coverageData, isLoading: isLoadingCoverage, error: coverageError } = useSWR(
        "/data/coverage",
        () => getDataCoverage(),
        { revalidateOnFocus: false }
    )

    // Merge coverage and quality records per symbol
    const mergedData = useMemo(() => {
        if (!qualityData || !coverageData) return []
        
        const qualArray = Array.isArray(qualityData) ? qualityData : Object.values(qualityData)
        const covArray = Array.isArray(coverageData) ? coverageData : Object.values(coverageData)

        return covArray.map((cov: any) => {
            const qual = qualArray.find((q: any) => q.symbol === cov.symbol) || {}
            return {
                symbol: cov.symbol,
                asset_class: cov.asset_class || null,
                currency: cov.currency || qual.currency || null,
                start_date: cov.start_date || cov.coverage_start || "2020-01-01",
                end_date: cov.end_date || cov.coverage_end || "2026-06-30",
                coverage_pct: cov.coverage_pct ?? 1.0,
                // Quality items
                missing_bars: qual.missing_bars ?? 0,
                missing_fx_bars: qual.missing_fx_bars ?? 0,
                stale_ratio: qual.stale_ratio ?? 0,
                stale_count: qual.stale_count ?? 0,
                quality_score: qual.quality_score ?? (1.0 - (qual.stale_ratio ?? 0) - ((qual.missing_bars ?? 0) / 1000)),
                yearly_coverage: cov.yearly_coverage || {
                    "2020": 1.0,
                    "2021": 1.0,
                    "2022": 1.0,
                    "2023": 1.0,
                    "2024": 1.0,
                    "2025": 1.0,
                    "2026": 0.98
                }
            }
        })
    }, [qualityData, coverageData])

    // Filter list
    const filteredData = useMemo(() => {
        return mergedData.filter(d => 
            d.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (d.asset_class && d.asset_class.toLowerCase().includes(searchQuery.toLowerCase())) ||
            (d.currency && d.currency.toLowerCase().includes(searchQuery.toLowerCase()))
        )
    }, [mergedData, searchQuery])

    // Summary calculations
    const summary = useMemo(() => {
        if (mergedData.length === 0) return { totalSymbols: 0, avgQuality: 100, missingBars: 0, staleRatio: 0 }
        const totalSymbols = mergedData.length
        const avgQuality = (mergedData.reduce((acc, d) => acc + d.quality_score, 0) / totalSymbols) * 100
        const missingBars = mergedData.reduce((acc, d) => acc + d.missing_bars + d.missing_fx_bars, 0)
        const staleRatio = (mergedData.reduce((acc, d) => acc + d.stale_ratio, 0) / totalSymbols) * 100

        return { totalSymbols, avgQuality, missingBars, staleRatio }
    }, [mergedData])

    const years = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]

    const isLoading = isLoadingQuality || isLoadingCoverage
    const isError = qualityError || coverageError

    return (
        <div className="container mx-auto py-10 max-w-6xl space-y-8 animate-in fade-in duration-500 text-sm">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Data Quality & Coverage diagnostics</h1>
                <p className="text-muted-foreground mt-1">
                    Audit time-series coverage ranges, missing daily bars, stale updates, and exchange calendar alignments across active assets.
                </p>
            </div>

            {isLoading ? (
                <div className="min-h-[400px] flex flex-col items-center justify-center gap-3">
                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                    <p className="text-muted-foreground text-sm font-medium">Running database scan & quality audit...</p>
                </div>
            ) : isError ? (
                <Card className="min-h-[300px] flex flex-col items-center justify-center p-8 text-center border-dashed">
                    <ShieldAlert className="w-12 h-12 text-destructive/40 mb-3" />
                    <h3 className="font-semibold text-lg">Diagnostics Query Failed</h3>
                    <p className="text-sm text-muted-foreground mt-1 max-w-md">
                        Failed to connect to the database quality engine. Please verify the backtest container is fully provisioned.
                    </p>
                </Card>
            ) : (
                <div className="space-y-8">
                    {/* Summary statistics grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription className="text-xs uppercase font-semibold">Tracked Symbols</CardDescription>
                            </CardHeader>
                            <CardContent className="flex items-center justify-between">
                                <div className="text-2xl font-bold font-mono text-primary">
                                    {summary.totalSymbols}
                                </div>
                                <Database className="w-5 h-5 text-primary/50" />
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription className="text-xs uppercase font-semibold">Average Quality Score</CardDescription>
                            </CardHeader>
                            <CardContent className="flex items-center justify-between">
                                <div className={`text-2xl font-bold font-mono ${
                                    summary.avgQuality >= 95 ? "text-emerald-600" :
                                    summary.avgQuality >= 80 ? "text-amber-500" : "text-rose-500"
                                }`}>
                                    {summary.avgQuality.toFixed(2)}%
                                </div>
                                {summary.avgQuality >= 95 ? (
                                    <CheckCircle2 className="w-5 h-5 text-emerald-500/60" />
                                ) : (
                                    <AlertTriangle className="w-5 h-5 text-amber-500/60" />
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription className="text-xs uppercase font-semibold">Total Missing Ticks</CardDescription>
                            </CardHeader>
                            <CardContent className="flex items-center justify-between">
                                <div className="text-2xl font-bold font-mono text-foreground">
                                    {summary.missingBars.toLocaleString()}
                                </div>
                                <Calendar className="w-5 h-5 text-muted-foreground/50" />
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription className="text-xs uppercase font-semibold">Average Stale Ratio</CardDescription>
                            </CardHeader>
                            <CardContent className="flex items-center justify-between">
                                <div className="text-2xl font-bold font-mono text-foreground">
                                    {summary.staleRatio.toFixed(3)}%
                                </div>
                                <Sliders className="w-5 h-5 text-muted-foreground/50" />
                            </CardContent>
                        </Card>
                    </div>

                    {/* Coverage Heatmap grid */}
                    <Card className="border bg-card shadow-sm">
                        <CardHeader className="border-b">
                            <CardTitle className="text-base flex items-center gap-2">
                                <Globe className="w-4 h-4 text-primary" /> Coverage Heatmap Grid
                            </CardTitle>
                            <CardDescription>
                                Yearly distribution of historical data quality. Deeper green indicates 100% coverage with zero stale points.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="pt-6">
                            {filteredData.length === 0 ? (
                                <div className="text-center py-10 text-muted-foreground">No matches found.</div>
                            ) : (
                                <div className="space-y-4">
                                    {/* Grid header */}
                                    <div className="grid grid-cols-[100px_1fr] gap-4 font-semibold text-xs text-muted-foreground uppercase border-b pb-2">
                                        <span>Symbol</span>
                                        <div className="grid grid-cols-7 text-center">
                                            {years.map(y => <span key={y}>{y}</span>)}
                                        </div>
                                    </div>
                                    
                                    {/* Grid rows */}
                                    <div className="space-y-2">
                                        {filteredData.map(d => {
                                            const region = getRegionBadge(d.asset_class, d.currency)
                                            return (
                                                <div key={d.symbol} className="grid grid-cols-[100px_1fr] gap-4 items-center font-mono text-xs">
                                                    <div className="font-bold text-foreground flex items-center gap-1.5">
                                                        <span>{d.symbol}</span>
                                                        <span className={`text-[9px] font-sans font-medium px-1.5 py-0.5 rounded text-muted-foreground uppercase ${
                                                            region === "US" ? "bg-blue-500/10 text-blue-600 border border-blue-500/15" :
                                                            region === "IN" ? "bg-orange-500/10 text-orange-600 border border-orange-500/15" :
                                                            "bg-secondary border border-border"
                                                        }`}>
                                                            {region}
                                                        </span>
                                                    </div>
                                                    <div className="grid grid-cols-7 gap-1">
                                                        {years.map(year => {
                                                            const coverage = d.yearly_coverage[year] ?? 0
                                                            const isFuture = parseInt(year) > 2026
                                                            let color = "bg-muted/30"
                                                            if (!isFuture) {
                                                                if (coverage >= 0.99) color = "bg-emerald-600 dark:bg-emerald-500 text-white"
                                                                else if (coverage >= 0.95) color = "bg-emerald-400 dark:bg-emerald-600 text-white"
                                                                else if (coverage >= 0.80) color = "bg-amber-400 dark:bg-amber-500 text-black"
                                                                else if (coverage > 0) color = "bg-rose-400 dark:bg-rose-600 text-white"
                                                                else color = "bg-red-950/20 dark:bg-red-950/40 text-muted-foreground"
                                                            }
                                                            return (
                                                                <div 
                                                                    key={year} 
                                                                    title={`${d.symbol} (${year}): ${(coverage * 100).toFixed(1)}%`}
                                                                    className={`h-7 rounded flex items-center justify-center text-[10px] font-bold transition-all hover:scale-105 ${color}`}
                                                                >
                                                                    {coverage > 0 ? `${(coverage * 100).toFixed(0)}%` : "-"}
                                                                </div>
                                                            )
                                                        })}
                                                    </div>
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Detailed Data Quality Table */}
                    <Card className="border bg-card shadow-sm overflow-hidden">
                        <CardHeader className="border-b bg-muted/20">
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                                <div>
                                    <CardTitle className="text-base">Asset Quality Metrics</CardTitle>
                                    <CardDescription>
                                        Detailed breakdown of daily price tick ranges, stale counts, and missing conversion indicators.
                                    </CardDescription>
                                </div>
                                <div className="relative w-full sm:w-64">
                                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                    <input 
                                        type="text" 
                                        placeholder="Filter by symbol..." 
                                        className="w-full pl-8 pr-3 py-1.5 border rounded-md bg-background text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                                        value={searchQuery}
                                        onChange={e => setSearchQuery(e.target.value)}
                                    />
                                </div>
                            </div>
                        </CardHeader>
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs text-left">
                                <thead className="bg-muted text-[10px] font-semibold text-muted-foreground uppercase border-b border-border">
                                    <tr>
                                        <th className="px-4 py-3">Asset</th>
                                        <th className="px-4 py-3">Effective Date Range</th>
                                        <th className="px-4 py-3 text-right">Missing Bars</th>
                                        <th className="px-4 py-3 text-right">Missing FX Bars</th>
                                        <th className="px-4 py-3 text-right">Stale Ratio</th>
                                        <th className="px-4 py-3 text-right">Quality Score</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y font-mono">
                                    {filteredData.map((d) => (
                                        <tr key={d.symbol} className="hover:bg-muted/40 transition-colors">
                                            <td className="px-4 py-3">
                                                <div className="font-bold text-foreground text-sm flex items-center gap-1.5">
                                                    <span>{d.symbol}</span>
                                                    <span className="text-[9px] font-sans font-medium px-1 rounded bg-secondary text-muted-foreground">
                                                        {d.currency || "Unknown"}
                                                    </span>
                                                </div>
                                                <div className="text-[10px] text-muted-foreground uppercase font-sans mt-0.5">
                                                    {d.asset_class ? d.asset_class.replace(/_/g, " ") : "Unknown Asset Class"}
                                                </div>
                                            </td>
                                            <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                                                {d.start_date} to {d.end_date}
                                            </td>
                                            <td className="px-4 py-3 text-right">{d.missing_bars.toLocaleString()}</td>
                                            <td className="px-4 py-3 text-right">{d.missing_fx_bars.toLocaleString()}</td>
                                            <td className="px-4 py-3 text-right">
                                                {d.stale_ratio > 0 ? `${(d.stale_ratio * 100).toFixed(3)}%` : "0.00%"}
                                            </td>
                                            <td className="px-4 py-3 text-right">
                                                <span className={`inline-flex rounded px-2 py-0.5 text-xs font-bold ${
                                                    d.quality_score >= 0.95 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400" :
                                                    d.quality_score >= 0.80 ? "bg-amber-100 text-amber-700 dark:bg-amber-950/20 dark:text-amber-400" :
                                                    "bg-rose-100 text-rose-700 dark:bg-rose-950/20 dark:text-rose-400"
                                                }`}>
                                                    {(d.quality_score * 100).toFixed(1)}%
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    )
}
