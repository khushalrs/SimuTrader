"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getMarketSnapshot, getMarketBars, MarketSnapshotOut, MarketBarOut } from "@/lib/market";
import { computeReturns, normalizePerformance, computeDrawdown, rollingVolSeries, correlationMatrix, downsampleData } from "@/lib/analytics";
import { getLeaderLaggardNarrative, getRiskRegimeNarrative, getDiversificationSummary } from "@/lib/narratives";
import { Skeleton } from "@/components/ui/skeleton";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend
} from "recharts";

const DEFAULT_BASKET = ["SPY", "QQQ", "IWM", "TLT", "GLD", "BTC"];
const COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff8042", "#0088fe", "#00C49F"];

export function MarketSnapshot() {
    const [snapshotData, setSnapshotData] = useState<MarketSnapshotOut[]>([]);
    const [barsData, setBarsData] = useState<MarketBarOut[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isChartVisible, setIsChartVisible] = useState(false);
    const chartRef = useRef<HTMLDivElement>(null);

    // Track visibility of below-the-fold charts
    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setIsChartVisible(true);
                    observer.disconnect();
                }
            },
            { rootMargin: "400px" } // Load a bit before it enters the viewport
        );
        if (chartRef.current) observer.observe(chartRef.current);
        return () => observer.disconnect();
    }, []);

    // Fetch snapshot immediately (First Paint)
    useEffect(() => {
        let isMounted = true;
        const fetchSnapshot = async () => {
            setIsLoading(true);
            try {
                const snap = await getMarketSnapshot(DEFAULT_BASKET);
                if (isMounted) setSnapshotData(snap);
            } catch (err) {
                console.error(err);
            } finally {
                if (isMounted) setIsLoading(false);
            }
        };

        fetchSnapshot();
        return () => { isMounted = false; };
    }, []);

    // Fetch bars only when charts are visible
    useEffect(() => {
        if (!isChartVisible) return;
        
        let isMounted = true;
        const fetchBars = async () => {
            try {
                const end = new Date();
                const start = new Date();
                start.setMonth(end.getMonth() - 3); // Reduced to 3 months
                
                const bars = await getMarketBars(
                    DEFAULT_BASKET, 
                    start.toISOString().split("T")[0], 
                    end.toISOString().split("T")[0],
                    "close",
                    "GLOBAL",
                    "RAW",      // Use RAW missing_bar unless continuity strictly required
                    200         // max_points downsampling explicitly via backend
                );
                
                if (isMounted) setBarsData(bars);
            } catch (err) {
                console.error(err);
            }
        };

        fetchBars();
        return () => { isMounted = false; };
    }, [isChartVisible]);

    // 1. Normalized Performance
    const chartDataRebased = useMemo(() => {
        if (!barsData.length) return [];
        
        // Group by symbol
        const bySymbol: Record<string, MarketBarOut[]> = {};
        for (const b of barsData) {
            if (!bySymbol[b.symbol]) bySymbol[b.symbol] = [];
            bySymbol[b.symbol].push(b);
        }

        // Normalize each
        const normSeries: Record<string, { date: string, value: number }[]> = {};
        for (const sym in bySymbol) {
            normSeries[sym] = normalizePerformance(bySymbol[sym], 100) as { date: string, value: number }[];
        }

        // Combine into one array by date
        const combinedByDate: Record<string, any> = {};
        for (const sym in normSeries) {
            for (const item of normSeries[sym]) {
                if (!combinedByDate[item.date]) {
                    combinedByDate[item.date] = { date: item.date };
                }
                combinedByDate[item.date][sym] = item.value;
            }
        }
        
        const combinedArray = Object.values(combinedByDate).sort((a, b) => a.date.localeCompare(b.date));
        return downsampleData(combinedArray, 100); // Downsample for the chart
    }, [barsData]);

    // 2. Correlation Matrix
    const { corrMatrix, symbols } = useMemo(() => {
        if (!barsData.length) return { corrMatrix: {}, symbols: [] };
        
        const bySymbol: Record<string, MarketBarOut[]> = {};
        for (const b of barsData) {
            if (!bySymbol[b.symbol]) bySymbol[b.symbol] = [];
            bySymbol[b.symbol].push(b);
        }

        const returnsBySymbol: Record<string, number[]> = {};
        for (const sym in bySymbol) {
            returnsBySymbol[sym] = computeReturns(bySymbol[sym]).map(r => r.returns);
        }

        // Align lengths 
        // Simple correlation assumes matched series length, skipping alignment complexity for UI demo.
        const minLen = Math.min(...Object.values(returnsBySymbol).map(arr => arr.length));
        for (const sym in returnsBySymbol) {
            returnsBySymbol[sym] = returnsBySymbol[sym].slice(0, minLen);
        }

        return { 
            corrMatrix: correlationMatrix(returnsBySymbol), 
            symbols: Object.keys(returnsBySymbol).sort()
        };
    }, [barsData]);

    const formatPercent = (val?: number | null) => {
        if (val === null || val === undefined) return "N/A";
        return `${(val * 100).toFixed(2)}%`;
    };

    if (isLoading) {
        return (
            <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6 pl-2 pr-2">
                {DEFAULT_BASKET.map((sym) => (
                    <Card key={sym}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <Skeleton className="h-4 w-[60px]" />
                        </CardHeader>
                        <CardContent>
                            <Skeleton className="h-6 w-[80px] mb-2" />
                            <Skeleton className="h-3 w-[120px]" />
                        </CardContent>
                    </Card>
                ))}
            </div>
            <div className="grid gap-6 grid-cols-1 md:grid-cols-3">
                    <Card className="col-span-2">
                        <CardHeader>
                            <Skeleton className="h-6 w-[200px]" />
                            <Skeleton className="h-4 w-[300px] mt-2" />
                        </CardHeader>
                        <CardContent><Skeleton className="h-[300px] w-full" /></CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <Skeleton className="h-6 w-[150px]" />
                            <Skeleton className="h-4 w-[200px] mt-2" />
                        </CardHeader>
                        <CardContent><Skeleton className="h-[250px] w-full" /></CardContent>
                    </Card>
                </div>
            </div>
        );
    }

    const { leader, laggard, dispersion, narrative: leaderText } = getLeaderLaggardNarrative(snapshotData);
    const riskRegimeText = getRiskRegimeNarrative(snapshotData);
    const divSummaryText = getDiversificationSummary(corrMatrix);

    return (
        <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6 pl-2 pr-2">
                {snapshotData.map((asset, i) => (
                    <Card key={asset.symbol}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium" style={{ color: COLORS[i % COLORS.length] }}>
                                {asset.symbol}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-xl font-bold">
                                {formatPercent(asset.return_1y)} <span className="text-[10px] font-normal text-muted-foreground">1Y</span>
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-1">
                                Vol: {formatPercent(asset.recent_vol_20d)}
                            </p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div ref={chartRef} className="grid gap-6 grid-cols-1 md:grid-cols-3">
                <Card className="col-span-2">
                    <CardHeader>
                        <CardTitle>Normalized Performance (1Y, Rebased 100)</CardTitle>
                        <CardDescription>
                            Comparing the selected basket relative performance.
                            <span className="block mt-2 font-medium text-foreground">
                                {leaderText}
                            </span>
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="h-[300px] w-full">
                            {!barsData.length ? (
                                <Skeleton className="h-[300px] w-full" />
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartDataRebased}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                        <XAxis 
                                            dataKey="date" 
                                            tickFormatter={(val) => val.split("-").slice(1).join("/")}
                                            tick={{ fontSize: 12 }}
                                            stroke="hsl(var(--muted-foreground))"
                                            minTickGap={30}
                                        />
                                        <YAxis 
                                            domain={['dataMin - 5', 'dataMax + 5']} 
                                            tickFormatter={(val) => Math.round(val).toString()}
                                            tick={{ fontSize: 12 }}
                                            stroke="hsl(var(--muted-foreground))"
                                        />
                                        <Tooltip 
                                            contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                            itemStyle={{ fontSize: '12px' }}
                                            labelStyle={{ color: 'hsl(var(--foreground))', marginBottom: '4px' }}
                                        />
                                        <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                                        {symbols.map((sym, i) => (
                                            <Line 
                                                key={sym}
                                                type="monotone" 
                                                dataKey={sym} 
                                                stroke={COLORS[i % COLORS.length]} 
                                                dot={false}
                                                strokeWidth={2}
                                            />
                                        ))}
                                    </LineChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Correlation Heatmap</CardTitle>
                        <CardDescription>
                            1Y daily returns correlation matrix.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="w-full aspect-square border-t border-l border-border relative mt-4">
                            {!barsData.length ? (
                                <Skeleton className="w-full h-full" />
                            ) : (
                                <>
                                    {symbols.map((s1, r) => (
                                        <div key={`row-${s1}`} className="flex h-[16.666%]">
                                            {symbols.map((s2, c) => {
                                                const corr = corrMatrix[s1]?.[s2] || 0;
                                                const isPositive = corr > 0;
                                                const intensity = Math.abs(corr);
                                                const bgColor = isPositive 
                                                    ? `rgba(74, 222, 128, ${Math.max(0.1, intensity)})`
                                                    : `rgba(248, 113, 113, ${Math.max(0.1, intensity)})`;
                                                
                                                return (
                                                    <div 
                                                        key={`cell-${s1}-${s2}`}
                                                        className="w-[16.666%] h-full border-r border-b border-border flex items-center justify-center text-[10px] sm:text-xs font-medium cursor-default group relative transition-colors"
                                                        style={{ backgroundColor: s1 === s2 ? 'hsl(var(--muted))' : bgColor }}
                                                    >
                                                        <span className="opacity-0 group-hover:opacity-100 transition-opacity absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10 w-max h-max p-1 rounded-sm shadow-sm m-auto pointer-events-none">
                                                            {s1}/{s2}: {corr.toFixed(2)}
                                                        </span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ))}
                                    {/* Axis Labels - Very tiny on edges */}
                                    <div className="absolute -top-5 left-0 right-0 flex justify-between px-2 text-[10px] text-muted-foreground">
                                        {symbols.map(s => <div key={`top-${s}`} className="w-[16.666%] text-center">{s}</div>)}
                                    </div>
                                    <div className="absolute -left-7 top-0 bottom-0 flex flex-col justify-between py-2 text-[10px] text-muted-foreground">
                                        {symbols.map(s => <div key={`left-${s}`} className="h-[16.666%] flex items-center pr-1">{s.slice(0,3)}</div>)}
                                    </div>
                                </>
                            )}
                        </div>
                        <div className="mt-8 text-xs text-muted-foreground w-full space-y-4">
                            <div>
                                <p className="font-semibold text-foreground">Diversification Summary</p>
                                <p>{divSummaryText}</p>
                            </div>
                            <div>
                                <p className="font-semibold text-foreground">Risk Regime Inference</p>
                                <p>{riskRegimeText}</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
