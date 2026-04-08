"use client"

import { useState, useMemo } from "react"
import useSWR from "swr"
import { compareRuns, RunCompareOut } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Loader2, Plus, X, Layers } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

const COLORS = [
    "#3b82f6", // blue-500 (Base Run)
    "#10b981", // emerald-500
    "#f59e0b", // amber-500
    "#8b5cf6", // violet-500
    "#ef4444"  // red-500
];

function formatPercent(value?: number | null): string {
    if (value === undefined || value === null) return "-"
    const pct = value * 100
    const sign = pct > 0 ? "+" : ""
    return `${sign}${pct.toFixed(2)}%`
}

export function CompareDashboardClient({ availableRuns }: { availableRuns: any[] }) {
    const [baseRun, setBaseRun] = useState<string>("");
    const [comparisonRuns, setComparisonRuns] = useState<string[]>([]);
    const [runSelectorOpen, setRunSelectorOpen] = useState(false);

    const { data: compareData, isLoading } = useSWR(
        baseRun ? `/compare/${baseRun}?others=${comparisonRuns.join(',')}` : null,
        () => compareRuns(baseRun, comparisonRuns),
        { revalidateOnFocus: false }
    );

    const handleAddCompare = (id: string) => {
        if (!baseRun) {
            setBaseRun(id);
        } else if (!comparisonRuns.includes(id)) {
            setComparisonRuns(prev => [...prev, id]);
        }
        setRunSelectorOpen(false);
    }

    const handleRemove = (id: string) => {
        if (id === baseRun) {
            setBaseRun("");
            setComparisonRuns([]);
        } else {
            setComparisonRuns(prev => prev.filter(r => r !== id));
        }
    }

    const unselectedRuns = availableRuns.filter(r => r.id !== baseRun && !comparisonRuns.includes(r.id) && r.status === "SUCCEEDED");
    const activeIds = [baseRun, ...comparisonRuns].filter(Boolean);

    const chartData = useMemo(() => {
        if (!compareData || !compareData.equity_series) return [];
        const dateMap: Record<string, any> = {};
        
        compareData.equity_series.forEach(series => {
            series.points.forEach(pt => {
                const day = pt.date.split("T")[0];
                if (!dateMap[day]) {
                    dateMap[day] = { date: day };
                }
                // Normalize to index 100 for proper comparison if starting cash differed?
                // The backend compareRuns currently returns raw equities, let's just plot raw ones for now unless user wants indexing.
                dateMap[day][series.run_id] = pt.value;
            });
        });

        return Object.values(dateMap).sort((a: any, b: any) => a.date.localeCompare(b.date));
    }, [compareData]);

    return (
        <div className="space-y-6">
            <Card className="bg-card shadow-sm border-border">
                <CardHeader className="pb-4 border-b border-border/50">
                    <CardTitle className="text-lg">Run Selection</CardTitle>
                    <CardDescription>Select the base run and up to 4 comparison runs to analyze.</CardDescription>
                </CardHeader>
                <CardContent className="pt-6">
                    <div className="flex flex-wrap gap-2 items-center">
                        {baseRun && (
                            <Badge variant="outline" className="px-3 py-1.5 flex items-center gap-2 bg-blue-500/10 text-blue-600 border-blue-500/20 text-sm font-medium">
                                Base: {baseRun.split("-")[0]}
                                <X className="w-3.5 h-3.5 cursor-pointer hover:text-destructive transition-colors ml-1" onClick={() => handleRemove(baseRun)} />
                            </Badge>
                        )}
                        {comparisonRuns.map((id, idx) => (
                            <Badge key={id} variant="secondary" className="px-3 py-1.5 flex items-center gap-2 text-sm">
                                <span style={{ color: COLORS[idx + 1] }}>●</span> {id.split("-")[0]}
                                <X className="w-3.5 h-3.5 cursor-pointer hover:text-destructive transition-colors ml-1" onClick={() => handleRemove(id)} />
                            </Badge>
                        ))}
                        {(comparisonRuns.length < 4 || !baseRun) && (
                            <div className="relative">
                                <Button variant="outline" size="sm" className="border-dashed" onClick={() => setRunSelectorOpen(!runSelectorOpen)}>
                                    <Plus className="w-4 h-4 mr-1" />
                                    Add Run
                                </Button>
                                {runSelectorOpen && (
                                    <div className="absolute top-full left-0 mt-2 w-64 bg-card border rounded-md shadow-lg z-50 max-h-60 overflow-y-auto">
                                        <div className="p-2">
                                            {unselectedRuns.length === 0 ? (
                                                <p className="text-sm text-muted-foreground p-2 text-center">No more succeeded runs available.</p>
                                            ) : (
                                                unselectedRuns.map(run => (
                                                    <div 
                                                        key={run.id} 
                                                        className="px-3 py-2 hover:bg-secondary rounded-sm cursor-pointer text-sm"
                                                        onClick={() => handleAddCompare(run.id)}
                                                    >
                                                        <div className="font-medium text-foreground">{run.title || "Untitled"}</div>
                                                        <div className="text-xs text-muted-foreground font-mono mt-0.5">{run.id.split("-")[0]}</div>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            {!baseRun ? (
                <div className="flex flex-col items-center justify-center p-12 text-center bg-card border rounded-xl shadow-sm min-h-[400px]">
                    <Layers className="h-12 w-12 text-muted-foreground/30 mb-4" />
                    <p className="text-lg font-semibold">Select a Target</p>
                    <p className="text-muted-foreground mt-2 max-w-sm">Please select a base run above to begin your comparison against your simulation library.</p>
                </div>
            ) : isLoading ? (
                <Card className="min-h-[500px] flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-primary opacity-50" />
                </Card>
            ) : compareData ? (
                <div className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Comparative Equity Overlay</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="h-[400px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                                        <XAxis dataKey="date" tick={{fontSize: 12}} minTickGap={30} />
                                        <YAxis tick={{fontSize: 12}} domain={['auto', 'auto']} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                                        <Tooltip 
                                            formatter={(value: any, name: any) => [`$${value.toLocaleString()}`, name.split("-")[0]]}
                                            labelStyle={{color: '#000'}} 
                                        />
                                        {activeIds.map((id, idx) => (
                                            <Line 
                                                key={id} 
                                                type="monotone" 
                                                dataKey={id} 
                                                stroke={COLORS[idx % COLORS.length]} 
                                                strokeWidth={id === baseRun ? 3 : 2} 
                                                dot={false} 
                                                className={id !== baseRun ? "opacity-80" : ""}
                                            />
                                        ))}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Metrics Breakdown</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto border rounded-md">
                                <Table>
                                    <TableHeader className="bg-secondary/20">
                                        <TableRow>
                                            <TableHead className="w-[120px]">Run</TableHead>
                                            <TableHead className="text-right">CAGR</TableHead>
                                            <TableHead className="text-right">Volatility</TableHead>
                                            <TableHead className="text-right">Sharpe</TableHead>
                                            <TableHead className="text-right">Max DD</TableHead>
                                            <TableHead className="text-right border-l">Gross Return</TableHead>
                                            <TableHead className="text-right">Net Return</TableHead>
                                            <TableHead className="text-right border-l">Fee Drag</TableHead>
                                            <TableHead className="text-right">Tax Drag</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {compareData.metric_rows.map((row) => (
                                            <TableRow key={row.run_id} className={row.run_id === baseRun ? "bg-blue-500/5 hover:bg-blue-500/10" : ""}>
                                                <TableCell className="font-mono text-xs font-semibold flex items-center gap-2">
                                                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[activeIds.indexOf(row.run_id)] }}></div>
                                                    {row.run_id.split("-")[0]}
                                                    {row.run_id === baseRun && <span className="text-[9px] bg-blue-100 text-blue-700 px-1 py-0.5 rounded ml-1">BASE</span>}
                                                </TableCell>
                                                <TableCell className="text-right font-mono">{formatPercent(row.cagr)}</TableCell>
                                                <TableCell className="text-right font-mono">{formatPercent(row.volatility)}</TableCell>
                                                <TableCell className="text-right font-mono">{row.sharpe ? row.sharpe.toFixed(2) : "-"}</TableCell>
                                                <TableCell className="text-right font-mono text-destructive">{formatPercent(row.max_drawdown)}</TableCell>
                                                <TableCell className="text-right font-mono border-l">{formatPercent(row.gross_return)}</TableCell>
                                                <TableCell className={`text-right font-mono font-medium ${row.net_return && row.net_return > 0 ? "text-emerald-500" : ""}`}>
                                                    {formatPercent(row.net_return)}
                                                </TableCell>
                                                <TableCell className="text-right font-mono border-l opacity-75">{formatPercent(row.fee_drag)}</TableCell>
                                                <TableCell className="text-right font-mono opacity-75">{formatPercent(row.tax_drag)}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            ) : null}
        </div>
    )
}
