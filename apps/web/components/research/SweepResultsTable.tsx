"use client"

import { useState, useMemo } from "react"
import useSWR from "swr"
import { useRouter } from "next/navigation"
import { getResearchJobResults, ResearchSweepResultOut } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowUpDown, Search, ExternalLink, Activity, Trophy } from "lucide-react"

interface SweepResultsTableProps {
    jobId: string
    onSelectRun?: (runId: string) => void
}

export function SweepResultsTable({ jobId, onSelectRun }: SweepResultsTableProps) {
    const router = useRouter()
    const [searchFilter, setSearchFilter] = useState("")
    const [sortKey, setSortKey] = useState<string>("sharpe")
    const [sortAsc, setSortAsc] = useState(false)

    const { data: results, isLoading } = useSWR<ResearchSweepResultOut[]>(
        jobId ? `/research/jobs/${jobId}/results` : null,
        () => getResearchJobResults(jobId),
        { refreshInterval: 3000 }
    )

    // Extract all unique parameter keys dynamically
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

    // Sort and filter results
    const processedResults = useMemo(() => {
        if (!results) return []

        let filtered = results.filter(r => {
            if (!searchFilter.trim()) return true
            const query = searchFilter.toLowerCase()
            const paramMatch = Object.entries(r.params || {}).some(([k, v]) => `${k}:${v}`.toLowerCase().includes(query))
            const statusMatch = (r.status || "").toLowerCase().includes(query)
            const runMatch = (r.run_id || "").toLowerCase().includes(query)
            return paramMatch || statusMatch || runMatch
        })

        return filtered.sort((a, b) => {
            let mult = sortAsc ? 1 : -1
            if (paramKeys.includes(sortKey)) {
                const valA = a.params?.[sortKey] ?? ""
                const valB = b.params?.[sortKey] ?? ""
                return mult * String(valA).localeCompare(String(valB), undefined, { numeric: true })
            } else {
                const metricA = (a.metrics as any)?.[sortKey] ?? -9999
                const metricB = (b.metrics as any)?.[sortKey] ?? -9999
                return mult * (Number(metricA) - Number(metricB))
            }
        })
    }, [results, searchFilter, sortKey, sortAsc, paramKeys])

    const handleSort = (key: string) => {
        if (sortKey === key) {
            setSortAsc(!sortAsc)
        } else {
            setSortKey(key)
            setSortAsc(false)
        }
    }

    const bestRunId = useMemo(() => {
        if (!results || results.length === 0) return null
        const succeeded = results.filter(r => r.run_id && r.metrics?.sharpe !== undefined && r.metrics?.sharpe !== null)
        if (succeeded.length === 0) return null
        return [...succeeded].sort((a, b) => (b.metrics?.sharpe || -999) - (a.metrics?.sharpe || -999))[0].run_id
    }, [results])

    if (isLoading) {
        return (
            <Card className="p-6 space-y-4">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-64 w-full" />
            </Card>
        )
    }

    if (!results || results.length === 0) {
        return (
            <Card className="p-8 text-center border-dashed">
                <Activity className="w-10 h-10 text-muted-foreground/30 mx-auto mb-2" />
                <h4 className="font-semibold text-sm">No Sweep Results Available</h4>
                <p className="text-xs text-muted-foreground mt-1">Child runs are either initializing or pending dispatch.</p>
            </Card>
        )
    }

    return (
        <Card className="border border-border shadow-sm">
            <CardHeader className="pb-3 border-b border-border/40 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <CardTitle className="text-base font-bold flex items-center gap-2">
                        Optimization Results Explorer
                        <Badge variant="secondary" className="font-mono text-xs">{results.length} Points</Badge>
                    </CardTitle>
                    <CardDescription className="text-xs">Sort, filter, and drill into sweep parameter configurations and metrics.</CardDescription>
                </div>

                <div className="flex items-center gap-2">
                    <div className="relative w-56">
                        <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
                        <Input
                            placeholder="Filter parameters..."
                            value={searchFilter}
                            onChange={e => setSearchFilter(e.target.value)}
                            className="h-8 pl-8 text-xs font-mono"
                        />
                    </div>
                </div>
            </CardHeader>

            <CardContent className="p-0 overflow-x-auto">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-muted/40 text-xs select-none">
                            <TableHead className="w-12 font-semibold">#</TableHead>
                            
                            {/* Dynamic Parameter Columns */}
                            {paramKeys.map(pk => (
                                <TableHead
                                    key={pk}
                                    className="font-semibold cursor-pointer hover:text-foreground font-mono"
                                    onClick={() => handleSort(pk)}
                                >
                                    <span className="flex items-center gap-1">
                                        {pk} {sortKey === pk ? (sortAsc ? "↑" : "↓") : ""}
                                    </span>
                                </TableHead>
                            ))}

                            {/* Standard Performance Metric Columns */}
                            <TableHead className="text-right font-semibold cursor-pointer hover:text-foreground" onClick={() => handleSort("sharpe")}>
                                Sharpe {sortKey === "sharpe" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="text-right font-semibold cursor-pointer hover:text-foreground" onClick={() => handleSort("cagr")}>
                                CAGR {sortKey === "cagr" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="text-right font-semibold cursor-pointer hover:text-foreground" onClick={() => handleSort("volatility")}>
                                Volatility {sortKey === "volatility" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="text-right font-semibold cursor-pointer hover:text-foreground" onClick={() => handleSort("max_drawdown")}>
                                Max DD {sortKey === "max_drawdown" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="text-right font-semibold cursor-pointer hover:text-foreground" onClick={() => handleSort("net_return")}>
                                Net Return {sortKey === "net_return" ? (sortAsc ? "↑" : "↓") : ""}
                            </TableHead>
                            <TableHead className="w-24 text-center font-semibold">Status</TableHead>
                            <TableHead className="w-20 text-right font-semibold">Action</TableHead>
                        </TableRow>
                    </TableHeader>

                    <TableBody className="text-xs">
                        {processedResults.map((item, idx) => {
                            const isBest = item.run_id && item.run_id === bestRunId
                            const metrics = item.metrics

                            return (
                                <TableRow
                                    key={idx}
                                    className={`hover:bg-primary/5 transition-colors cursor-pointer ${isBest ? "bg-amber-500/10 font-medium" : ""}`}
                                    onClick={() => {
                                        if (item.run_id) {
                                            if (onSelectRun) onSelectRun(item.run_id)
                                            else router.push(`/runs/${item.run_id}`)
                                        }
                                    }}
                                >
                                    <TableCell className="font-mono text-muted-foreground flex items-center gap-1">
                                        {isBest && <Trophy className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                                        {idx + 1}
                                    </TableCell>

                                    {/* Parameter values */}
                                    {paramKeys.map(pk => (
                                        <TableCell key={pk} className="font-mono font-semibold text-foreground">
                                            {String(item.params?.[pk] ?? "—")}
                                        </TableCell>
                                    ))}

                                    {/* Metrics */}
                                    <TableCell className="text-right font-mono font-bold text-foreground">
                                        {metrics?.sharpe !== undefined && metrics?.sharpe !== null ? metrics.sharpe.toFixed(2) : "—"}
                                    </TableCell>
                                    <TableCell className={`text-right font-mono ${metrics?.cagr && metrics.cagr > 0 ? "text-emerald-600 font-semibold" : ""}`}>
                                        {metrics?.cagr !== undefined && metrics?.cagr !== null ? `${(metrics.cagr * 100).toFixed(1)}%` : "—"}
                                    </TableCell>
                                    <TableCell className="text-right font-mono">
                                        {metrics?.volatility !== undefined && metrics?.volatility !== null ? `${(metrics.volatility * 100).toFixed(1)}%` : "—"}
                                    </TableCell>
                                    <TableCell className="text-right font-mono text-rose-500">
                                        {metrics?.max_drawdown !== undefined && metrics?.max_drawdown !== null ? `${(metrics.max_drawdown * 100).toFixed(1)}%` : "—"}
                                    </TableCell>
                                    <TableCell className={`text-right font-mono ${metrics?.net_return && metrics.net_return > 0 ? "text-emerald-600 font-semibold" : ""}`}>
                                        {metrics?.net_return !== undefined && metrics?.net_return !== null ? `${(metrics.net_return * 100).toFixed(1)}%` : "—"}
                                    </TableCell>

                                    <TableCell className="text-center">
                                        <Badge
                                            variant={item.status === "SUCCEEDED" ? "default" : item.status === "FAILED" ? "destructive" : "outline"}
                                            className="text-[10px]"
                                        >
                                            {item.status || "PLANNED"}
                                        </Badge>
                                    </TableCell>

                                    <TableCell className="text-right">
                                        {item.run_id && (
                                            <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                                                <ExternalLink className="w-3.5 h-3.5" />
                                            </Button>
                                        )}
                                    </TableCell>
                                </TableRow>
                            )
                        })}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    )
}
