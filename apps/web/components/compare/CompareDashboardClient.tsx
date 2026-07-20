"use client"

import { useState, useMemo } from "react"
import useSWR from "swr"
import { compareRuns } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Loader2, Plus, X, Layers, TrendingUp, ShieldAlert, Award } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts"
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
    const [chartMode, setChartMode] = useState<"indexed" | "drawdown">("indexed");

    const { data: compareData, isLoading, error: compareError } = useSWR(
        baseRun ? `/compare/${baseRun}?others=${comparisonRuns.join(',')}` : null,
        () => compareRuns(baseRun, comparisonRuns),
        { revalidateOnFocus: false }
    );

    const getRunName = (id: string) => {
        const run = availableRuns.find(r => r.id === id || r.run_id === id);
        return run?.title || run?.name || id.split("-")[0];
    }

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

    const unselectedRuns = availableRuns.filter(r => {
        const runId = r.id || r.run_id;
        return runId !== baseRun && !comparisonRuns.includes(runId) && r.status === "SUCCEEDED";
    });
    const activeIds = [baseRun, ...comparisonRuns].filter(Boolean);

    // Dynamic processing for Indexed Equity or Peak-to-Trough Drawdown series
    const chartData = useMemo(() => {
        if (!compareData || !compareData.equity_series) return [];
        const dateMap: Record<string, any> = {};
        const runningPeaks: Record<string, number> = {};
        const startingValues: Record<string, number> = {};

        compareData.equity_series.forEach(series => {
            if (series.points.length > 0) {
                startingValues[series.run_id] = series.points[0].value;
            }
        });

        compareData.equity_series.forEach(series => {
            series.points.forEach(pt => {
                const day = pt.date.split("T")[0];
                if (!dateMap[day]) {
                    dateMap[day] = { date: day };
                }
                
                const startVal = startingValues[series.run_id] || 1.0;
                if (chartMode === "indexed") {
                    dateMap[day][series.run_id] = pt.value / startVal;
                } else {
                    const currentPeak = runningPeaks[series.run_id] || 0.0;
                    const nextPeak = Math.max(currentPeak, pt.value);
                    runningPeaks[series.run_id] = nextPeak;
                    const drawdown = nextPeak > 0 ? (pt.value / nextPeak) - 1.0 : 0.0;
                    dateMap[day][series.run_id] = drawdown * 100;
                }
            });
        });

        return Object.values(dateMap).sort((a: any, b: any) => a.date.localeCompare(b.date));
    }, [compareData, chartMode]);

    // Winner Badges calculation
    const winners = useMemo(() => {
        if (!compareData || compareData.metric_rows.length === 0) return null;
        const rows = compareData.metric_rows;
        
        const winnerNet = [...rows].sort((a, b) => (b.net_return || 0) - (a.net_return || 0))[0];
        const winnerSharpe = [...rows].sort((a, b) => (b.sharpe || 0) - (a.sharpe || 0))[0];
        const lowestDD = [...rows].sort((a, b) => (b.max_drawdown || 0) - (a.max_drawdown || 0))[0];

        return {
            net: winnerNet,
            sharpe: winnerSharpe,
            drawdown: lowestDD
        };
    }, [compareData]);

    const baseRow = compareData?.metric_rows.find(r => r.run_id === baseRun);

    const renderServerMetric = (
        row: any,
        metricKey: string,
        isPercent = true,
        isSharpe = false,
        inverseColors = false
    ) => {
        const val = row[metricKey];
        if (val === undefined || val === null) return "-";
        const display = isSharpe ? val.toFixed(2) : isPercent ? formatPercent(val) : val.toFixed(2);

        if (row.run_id === baseRun) return display;

        let diff: number | null = null;
        if (row.delta_vs_base && row.delta_vs_base[metricKey] !== undefined && row.delta_vs_base[metricKey] !== null) {
            diff = row.delta_vs_base[metricKey];
        } else if (baseRow && baseRow[metricKey] !== undefined && baseRow[metricKey] !== null) {
            diff = val - baseRow[metricKey];
        }

        if (diff === null || diff === 0) return display;

        const sign = diff > 0 ? "+" : "";
        const isBetter = inverseColors ? diff < 0 : diff > 0;
        const color = isBetter ? "text-emerald-500 font-medium" : diff < 0 ? "text-rose-500" : "text-muted-foreground";
        const deltaDisplay = isSharpe
            ? `${sign}${diff.toFixed(2)}`
            : isPercent
            ? `${sign}${(diff * 100).toFixed(1)}%`
            : `${sign}${diff.toFixed(2)}`;

        return (
            <span className="font-mono">
                {display} <span className={`text-[10px] ml-1 ${color}`}>({deltaDisplay})</span>
            </span>
        );
    }

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
                                Base: {getRunName(baseRun)}
                                <X className="w-3.5 h-3.5 cursor-pointer hover:text-destructive transition-colors ml-1" onClick={() => handleRemove(baseRun)} />
                            </Badge>
                        )}
                        {comparisonRuns.map((id, idx) => (
                            <Badge key={id} variant="secondary" className="px-3 py-1.5 flex items-center gap-2 text-sm">
                                <span style={{ color: COLORS[idx + 1] }}>●</span> {getRunName(id)}
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
            ) : compareError ? (
                <Card className="min-h-[300px] flex flex-col items-center justify-center gap-2 text-destructive">
                    <p className="font-semibold">Failed to load comparison data.</p>
                    <p className="text-sm text-muted-foreground">Please check your connection and try again.</p>
                </Card>
            ) : compareData ? (
                <div className="space-y-6">
                    {/* Top Winners highlights */}
                    {winners && (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <Card className="border-l-4 border-l-emerald-500">
                                <CardHeader className="py-3 pb-1">
                                    <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center gap-1.5">
                                        <Award className="w-4 h-4 text-emerald-500" /> Winner by Net Return
                                    </span>
                                    <div className="text-base font-bold truncate mt-1">
                                        {getRunName(winners.net.run_id)} <span className="text-xs text-emerald-600 font-mono">({formatPercent(winners.net.net_return)})</span>
                                    </div>
                                </CardHeader>
                            </Card>
                            <Card className="border-l-4 border-l-purple-500">
                                <CardHeader className="py-3 pb-1">
                                    <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center gap-1.5">
                                        <Award className="w-4 h-4 text-purple-500" /> Winner by Sharpe
                                    </span>
                                    <div className="text-base font-bold truncate mt-1">
                                        {getRunName(winners.sharpe.run_id)} <span className="text-xs text-purple-600 font-mono">({winners.sharpe.sharpe?.toFixed(2) || "N/A"})</span>
                                    </div>
                                </CardHeader>
                            </Card>
                            <Card className="border-l-4 border-l-teal-500">
                                <CardHeader className="py-3 pb-1">
                                    <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center gap-1.5">
                                        <Award className="w-4 h-4 text-teal-500" /> Lowest Drawdown
                                    </span>
                                    <div className="text-base font-bold truncate mt-1">
                                        {getRunName(winners.drawdown.run_id)} <span className="text-xs text-teal-600 font-mono">({formatPercent(winners.drawdown.max_drawdown)})</span>
                                    </div>
                                </CardHeader>
                            </Card>
                        </div>
                    )}

                    {/* Chart Card with Overlay Toggles */}
                    <Card>
                        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/50 pb-4">
                            <div>
                                <CardTitle>Performance Comparison</CardTitle>
                                <CardDescription>
                                    {chartMode === "indexed" 
                                        ? "Performance comparison rebased to growth of $1 (Start = 1.00x)" 
                                        : "Comparative peak-to-trough drawdowns (%)"
                                    }
                                </CardDescription>
                            </div>
                            <div className="flex bg-muted p-1 rounded-md text-xs w-fit">
                                <Button 
                                    variant={chartMode === "indexed" ? "secondary" : "ghost"} 
                                    size="sm" 
                                    className="h-7 text-xs"
                                    onClick={() => setChartMode("indexed")}
                                >
                                    Indexed Equity
                                </Button>
                                <Button 
                                    variant={chartMode === "drawdown" ? "secondary" : "ghost"} 
                                    size="sm" 
                                    className="h-7 text-xs"
                                    onClick={() => setChartMode("drawdown")}
                                >
                                    Drawdown Overlay
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent className="pt-6">
                            <div className="h-[350px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                        <XAxis dataKey="date" tick={{fontSize: 11}} minTickGap={30} />
                                        <YAxis 
                                            tick={{fontSize: 11}} 
                                            domain={chartMode === "indexed" ? ['auto', 'auto'] : [-30, 0]} 
                                            tickFormatter={(v) => chartMode === "indexed" ? `${parseFloat(v).toFixed(2)}x` : `${v.toFixed(0)}%`} 
                                        />
                                        <Tooltip 
                                            formatter={(value: any, name: any) => [
                                                chartMode === "indexed" 
                                                    ? `Growth: ${parseFloat(value).toFixed(2)}x` 
                                                    : `Drawdown: ${parseFloat(value).toFixed(2)}%`, 
                                                getRunName(name)
                                            ]}
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

                    {/* Metrics comparison table */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Metrics Comparison</CardTitle>
                            <CardDescription>Delta values shown in parentheses represent changes compared against the Base Run.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto border rounded-md">
                                <Table>
                                    <TableHeader className="bg-secondary/20">
                                        <TableRow>
                                            <TableHead className="w-[180px]">Run</TableHead>
                                            <TableHead className="text-right">CAGR</TableHead>
                                            <TableHead className="text-right">Volatility</TableHead>
                                            <TableHead className="text-right">Sharpe</TableHead>
                                            <TableHead className="text-right">Max DD</TableHead>
                                            <TableHead className="text-right border-l">Gross Return</TableHead>
                                            <TableHead className="text-right">Net Return</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {compareData.metric_rows.map((row) => (
                                            <TableRow key={row.run_id} className={row.run_id === baseRun ? "bg-blue-500/5 hover:bg-blue-500/10" : ""}>
                                                <TableCell className="font-semibold flex items-center gap-2">
                                                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[activeIds.indexOf(row.run_id)] }}></div>
                                                    <span className="truncate max-w-[120px]">{getRunName(row.run_id)}</span>
                                                    {row.run_id === baseRun && <span className="text-[9px] bg-blue-100 text-blue-700 px-1 py-0.5 rounded ml-1">BASE</span>}
                                                </TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "cagr", true, false, false)}</TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "volatility", true, false, true)}</TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "sharpe", false, true, false)}</TableCell>
                                                <TableCell className="text-right text-rose-500">{renderServerMetric(row, "max_drawdown", true, false, false)}</TableCell>
                                                <TableCell className="text-right border-l">{renderServerMetric(row, "gross_return", true, false, false)}</TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "net_return", true, false, false)}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Cost/Tax Comparison Delta Table */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Leakage & Drag Deltas</CardTitle>
                            <CardDescription>Comparison of return drags relative to the Base Run.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto border rounded-md">
                                <Table>
                                    <TableHeader className="bg-secondary/20">
                                        <TableRow>
                                            <TableHead className="w-[180px]">Run</TableHead>
                                            <TableHead className="text-right">Transaction Fee Drag</TableHead>
                                            <TableHead className="text-right">Tax Drag</TableHead>
                                            <TableHead className="text-right">Short Borrow Drag</TableHead>
                                            <TableHead className="text-right">Margin Interest Drag</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {compareData.metric_rows.map((row) => (
                                            <TableRow key={row.run_id} className={row.run_id === baseRun ? "bg-blue-500/5 hover:bg-blue-500/10" : ""}>
                                                <TableCell className="font-semibold flex items-center gap-2">
                                                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[activeIds.indexOf(row.run_id)] }}></div>
                                                    <span className="truncate max-w-[120px]">{getRunName(row.run_id)}</span>
                                                </TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "fee_drag", true, false, true)}</TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "tax_drag", true, false, true)}</TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "borrow_drag", true, false, true)}</TableCell>
                                                <TableCell className="text-right">{renderServerMetric(row, "margin_interest_drag", true, false, true)}</TableCell>
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
