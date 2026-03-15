"use client";

import React, { useEffect, useState, useMemo } from "react";
import { AssetOut } from "@/lib/api";
import { getMarketBars, MarketBarOut } from "@/lib/market";
import { computeReturns, computeDrawdown, downsampleData } from "@/lib/analytics";
import { X } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
    LineChart,
    Line,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    AreaChart,
    Area
} from "recharts";

interface AssetDetailDrawerProps {
    asset: AssetOut | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function AssetDetailDrawer({ asset, open, onOpenChange }: AssetDetailDrawerProps) {
    const [bars, setBars] = useState<MarketBarOut[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (!open || !asset) return;
        
        let isMounted = true;
        const fetchData = async () => {
            setIsLoading(true);
            try {
                const end = new Date();
                const start = new Date();
                start.setMonth(end.getMonth() - 6);
                
                const data = await getMarketBars(
                    [asset.symbol],
                    start.toISOString().split("T")[0],
                    end.toISOString().split("T")[0],
                    "close",
                    "GLOBAL",
                    "RAW",
                    120,
                );
                if (isMounted) setBars(data);
            } catch (err) {
                console.error(err);
            } finally {
                if (isMounted) setIsLoading(false);
            }
        };

        fetchData();
        return () => { isMounted = false; };
    }, [asset, open]);

    const { closeSeries, returnsHist, drawdowns, stats } = useMemo(() => {
        if (!bars.length) return { closeSeries: [], returnsHist: [], drawdowns: [], stats: {} };

        // 1. Close Chart
        const closeSeriesRaw = bars.map(b => ({ date: b.date, close: b.close }));
        const closeSeries = downsampleData(closeSeriesRaw, 100);

        // 2. Returns Hist (Fat tails analysis)
        const rets = computeReturns(bars);
        const buckets: Record<string, number> = {
            "<-3%": 0, "-3% to -1%": 0, "-1% to 0%": 0, "0% to 1%": 0, "1% to 3%": 0, ">3%": 0
        };
        
        rets.forEach(r => {
            const p = r.returns * 100;
            if (p < -3) buckets["<-3%"]++;
            else if (p < -1) buckets["-3% to -1%"]++;
            else if (p < 0) buckets["-1% to 0%"]++;
            else if (p < 1) buckets["0% to 1%"]++;
            else if (p < 3) buckets["1% to 3%"]++;
            else buckets[">3%"]++;
        });

        const returnsHist = Object.keys(buckets).map(k => ({ bucket: k, count: buckets[k] }));

        // 3. Drawdowns
        const ddRaw = computeDrawdown(bars);
        const drawdownsRaw = ddRaw.map(d => ({ date: d.date, drawdown: d.drawdown * 100 }));
        const drawdowns = downsampleData(drawdownsRaw, 100);
        
        const maxDd = Math.min(...drawdownsRaw.map(d => d.drawdown));
        const currentDd = drawdownsRaw[drawdownsRaw.length - 1]?.drawdown || 0;

        // Returns inferences
        const getRet = (days: number) => {
            if (bars.length < days + 1) return null;
            const pxStart = bars[bars.length - 1 - days].close;
            const pxEnd = bars[bars.length - 1].close;
            if (!pxStart || !pxEnd) return null;
            return (pxEnd / pxStart) - 1;
        };

        const ret1m = getRet(21);
        const ret3m = getRet(63);
        const ret1y = getRet(252);

        let momentumNarrative = "Neutral momentum.";
        if (ret1m && ret1y) {
            if (ret1m > 0 && ret1y < 0) momentumNarrative = "Short-term momentum strong vs long-term weak.";
            else if (ret1m < 0 && ret1y > 0) momentumNarrative = "Short-term pullback in long-term uptrend.";
            else if (ret1m > 0 && ret1y > 0) momentumNarrative = "Strong momentum across both horizons.";
        }

        const extremeDays = buckets["<-3%"] + buckets[">3%"];
        const fatTailsNarrative = extremeDays > (rets.length * 0.05) ? "Fat tails: Extreme days occur frequently." : "Normal tail distribution observed.";

        return { 
            closeSeries, 
            returnsHist, 
            drawdowns,
            stats: { maxDd, currentDd, ret1m, ret3m, ret1y, momentumNarrative, fatTailsNarrative }
        };
    }, [bars]);

    if (!open) return null;

    const formatPct = (val?: number | null) => val != null ? `${(val * 100).toFixed(2)}%` : "N/A";

    return (
        <div className="fixed inset-0 z-50 flex justify-end bg-background/80 backdrop-blur-sm transition-all duration-300">
            <div className="h-full w-full max-w-2xl bg-background border-l border-border shadow-xl flex flex-col animate-in slide-in-from-right duration-300">
                <div className="flex items-center justify-between px-6 py-4 border-b border-border">
                    <div>
                        <h2 className="text-xl font-bold tracking-tight">{asset?.symbol} Drilldown</h2>
                        <p className="text-sm text-muted-foreground">{asset?.name} &bull; {asset?.asset_class}</p>
                    </div>
                    <button 
                        onClick={() => onOpenChange(false)}
                        className="rounded-full p-2 hover:bg-muted text-muted-foreground"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <div className="p-6 overflow-y-auto flex-1 space-y-8">
                    {isLoading ? (
                        <div className="space-y-6">
                            <div className="grid grid-cols-3 gap-4">
                                <Skeleton className="h-24 w-full" />
                                <Skeleton className="h-24 w-full" />
                                <Skeleton className="h-24 w-full" />
                            </div>
                            <div className="space-y-2">
                                <Skeleton className="h-4 w-[120px]" />
                                <Skeleton className="h-[250px] w-full" />
                            </div>
                            <div className="space-y-2">
                                <Skeleton className="h-4 w-[120px]" />
                                <Skeleton className="h-[150px] w-full" />
                            </div>
                            <div className="space-y-2">
                                <Skeleton className="h-4 w-[120px]" />
                                <Skeleton className="h-[200px] w-full" />
                            </div>
                        </div>
                    ) : bars.length === 0 ? (
                        <div className="flex h-full items-center justify-center text-muted-foreground">
                            No market data found for {asset?.symbol}.
                        </div>
                    ) : (
                        <>
                            {/* Vital Stats */}
                            <div className="grid grid-cols-3 gap-4">
                                <div className="p-4 rounded-lg border border-border bg-card">
                                    <p className="text-xs text-muted-foreground mb-1">1M / 3M / 1Y</p>
                                    <p className="font-semibold text-sm">
                                        {formatPct(stats.ret1m)} / {formatPct(stats.ret3m)} / {formatPct(stats.ret1y)}
                                    </p>
                                    <p className="text-[10px] text-muted-foreground mt-2">{stats.momentumNarrative}</p>
                                </div>
                                <div className="p-4 rounded-lg border border-border bg-card">
                                    <p className="text-xs text-muted-foreground mb-1">Max Drawdown (3Y)</p>
                                    <p className="font-semibold text-sm text-red-500">
                                        {stats.maxDd?.toFixed(2)}%
                                    </p>
                                    <p className="text-[10px] text-muted-foreground mt-2">Currently {stats.currentDd?.toFixed(2)}% off peak</p>
                                </div>
                                <div className="p-4 rounded-lg border border-border bg-card">
                                    <p className="text-xs text-muted-foreground mb-1">Return Dist</p>
                                    <p className="font-semibold text-sm">Volatility Analysis</p>
                                    <p className="text-[10px] text-muted-foreground mt-2">{stats.fatTailsNarrative}</p>
                                </div>
                            </div>

                            {/* Price Chart */}
                            <div className="space-y-2">
                                <h3 className="font-semibold text-sm">Price History (3Y)</h3>
                                <div className="h-[250px] w-full border border-border rounded-lg p-4 bg-card">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={closeSeries}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground)/0.2)" />
                                            <XAxis 
                                                dataKey="date" 
                                                tickFormatter={(val) => val.split("-")[0]}
                                                tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))"
                                                minTickGap={30}
                                            />
                                            <YAxis 
                                                domain={['auto', 'auto']} 
                                                tickFormatter={(val) => val.toFixed(2)}
                                                tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))"
                                                width={40}
                                            />
                                            <Tooltip 
                                                contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', fontSize: '12px' }}
                                                labelStyle={{ color: 'hsl(var(--muted-foreground))' }}
                                            />
                                            <Line type="monotone" dataKey="close" stroke="hsl(var(--primary))" dot={false} strokeWidth={2} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* Drawdown Area */}
                            <div className="space-y-2">
                                <h3 className="font-semibold text-sm">Drawdown</h3>
                                <div className="h-[150px] w-full border border-border rounded-lg p-4 bg-card">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={drawdowns}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground)/0.2)" />
                                            <XAxis dataKey="date" hide />
                                            <YAxis 
                                                domain={['auto', 0]} 
                                                tickFormatter={(v) => `${v.toFixed(0)}%`}
                                                tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))"
                                                width={40}
                                            />
                                            <Tooltip 
                                                contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', fontSize: '12px' }}
                                                labelStyle={{ color: 'hsl(var(--muted-foreground))' }}
                                                formatter={(val: number | string | undefined) => [typeof val === 'number' ? `${val.toFixed(2)}%` : val, 'Drawdown']}
                                            />
                                            <Area type="step" dataKey="drawdown" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* Distribution Histogram */}
                            <div className="space-y-2 pb-8">
                                <h3 className="font-semibold text-sm">Daily Returns Distribution</h3>
                                <div className="h-[200px] w-full border border-border rounded-lg p-4 bg-card">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={returnsHist}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground)/0.2)" />
                                            <XAxis dataKey="bucket" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                                            <YAxis tickFormatter={(val) => `${(val * 100).toFixed(0)}%`} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" width={32} />
                                            <Tooltip 
                                                cursor={{ fill: 'hsl(var(--muted))' }}
                                                contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', fontSize: '12px' }}
                                                formatter={(val: number | string | undefined) => [val, 'Days']}
                                            />
                                            <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
