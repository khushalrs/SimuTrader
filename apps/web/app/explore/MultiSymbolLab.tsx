"use client";

import React, { useState, useEffect, useMemo } from "react";
import { AssetSearch } from "./AssetSearch";
import { AssetOut } from "@/lib/api";
import { getMarketBars, MarketBarOut } from "@/lib/market";
import { computeReturns, normalizePerformance, correlationMatrix, rollingVol, downsampleData } from "@/lib/analytics";
import { X, Plus } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
    LineChart,
    Line,
    ScatterChart,
    Scatter,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    ZAxis
} from "recharts";

const COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff8042", "#0088fe", "#00C49F", "#e83e8c", "#6f42c1", "#20c997", "#fd7e14"];
const MAX_SYMBOLS = 10;
const STORAGE_KEY = "simutrader_watchlist";

export function MultiSymbolLab() {
    const [symbols, setSymbols] = useState<AssetOut[]>([]);
    const [barsData, setBarsData] = useState<MarketBarOut[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    // Load from local storage on mount
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                if (Array.isArray(parsed)) {
                    setSymbols(parsed);
                }
            } catch (e) { console.error(e); }
        }
    }, []);

    // Save to local storage on change
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(symbols));
    }, [symbols]);

    // Fetch data when symbols change
    useEffect(() => {
        if (symbols.length === 0) {
            setBarsData([]);
            return;
        }

        let isMounted = true;
        const fetchData = async () => {
            setIsLoading(true);
            try {
                const end = new Date();
                const start = new Date();
                start.setFullYear(end.getFullYear() - 1);
                
                const data = await getMarketBars(
                    symbols.map(s => s.symbol), 
                    start.toISOString().split("T")[0], 
                    end.toISOString().split("T")[0]
                );
                
                if (isMounted) setBarsData(data);
            } catch (err) {
                console.error(err);
            } finally {
                if (isMounted) setIsLoading(false);
            }
        };

        fetchData();
        return () => { isMounted = false; };
    }, [symbols]);

    const handleAddSymbol = (asset: AssetOut) => {
        if (symbols.some(s => s.symbol === asset.symbol)) return;
        if (symbols.length >= MAX_SYMBOLS) return;
        setSymbols([...symbols, asset]);
    };

    const handleRemoveSymbol = (symbolToRemove: string) => {
        setSymbols(symbols.filter(s => s.symbol !== symbolToRemove));
    };

    // 1. Normalized Line Chart
    const chartDataRebased = useMemo(() => {
        if (!barsData.length) return [];
        
        const bySymbol: Record<string, MarketBarOut[]> = {};
        for (const b of barsData) {
            if (!bySymbol[b.symbol]) bySymbol[b.symbol] = [];
            bySymbol[b.symbol].push(b);
        }

        const normSeries: Record<string, { date: string, value: number }[]> = {};
        for (const sym in bySymbol) {
            normSeries[sym] = normalizePerformance(bySymbol[sym], 100) as { date: string, value: number }[];
        }

        const combinedByDate: Record<string, any> = {};
        for (const sym in normSeries) {
            for (const item of normSeries[sym]) {
                if (!combinedByDate[item.date]) combinedByDate[item.date] = { date: item.date };
                combinedByDate[item.date][sym] = item.value;
            }
        }
        
        const combinedArray = Object.values(combinedByDate).sort((a, b) => a.date.localeCompare(b.date));
        return downsampleData(combinedArray, 100);
    }, [barsData]);

    // 2. Risk-Return Scatter & Correlation Heatmap
    const { scatterData, corrMatrix, symbolKeys } = useMemo(() => {
        if (!barsData.length) return { scatterData: [], corrMatrix: {}, symbolKeys: [] };
        
        const bySymbol: Record<string, MarketBarOut[]> = {};
        for (const b of barsData) {
            if (!bySymbol[b.symbol]) bySymbol[b.symbol] = [];
            bySymbol[b.symbol].push(b);
        }

        const returnsBySymbol: Record<string, number[]> = {};
        const scatterData = [];

        for (const sym in bySymbol) {
            const rets = computeReturns(bySymbol[sym]).map(r => r.returns);
            returnsBySymbol[sym] = rets;

            // Compute cumulative 1Y return loosely for scatter
            const firstPx = bySymbol[sym][0]?.close;
            const lastPx = bySymbol[sym][bySymbol[sym].length - 1]?.close;
            let ret1y = 0;
            if (firstPx && lastPx) ret1y = (lastPx / firstPx) - 1;

            // Compute Vol 
            let vol = 0;
            if (rets.length > 0) {
                const vols = rollingVol(rets, rets.length); // approx whole sample vol
                if (vols.length > 0) vol = vols[vols.length - 1];
            }

            scatterData.push({
                symbol: sym,
                return: ret1y * 100,
                volatility: vol * 100
            });
        }

        const minLen = Math.min(...Object.values(returnsBySymbol).map(arr => arr.length));
        for (const sym in returnsBySymbol) {
            returnsBySymbol[sym] = returnsBySymbol[sym].slice(0, minLen);
        }

        return { 
            scatterData,
            corrMatrix: correlationMatrix(returnsBySymbol), 
            symbolKeys: Object.keys(returnsBySymbol).sort()
        };
    }, [barsData]);

    // Pair spread (if exactly 2)
    const pairSpreadSeries = useMemo(() => {
        if (symbols.length !== 2 || !barsData.length) return null;
        const s1 = symbols[0].symbol;
        const s2 = symbols[1].symbol;

        const combinedByDate: Record<string, any> = {};
        for (const b of barsData) {
            if (!combinedByDate[b.date]) combinedByDate[b.date] = { date: b.date };
            combinedByDate[b.date][b.symbol] = b.close;
        }

        const spreadSeries = [];
        let mean = 0;
        let count = 0;

        // Spread = Price s1 / Price s2 (ratio)
        // Or Log ratio math.Log(s1/s2). Let's use simple ratio for visualization
        for (const date in combinedByDate) {
            const row = combinedByDate[date];
            if (row[s1] && row[s2]) {
                const ratio = row[s1] / row[s2];
                spreadSeries.push({ date, ratio, s1: row[s1], s2: row[s2] });
                mean += ratio;
                count++;
            }
        }

        mean = mean / count;
        // Approx standard dev
        let variance = 0;
        spreadSeries.forEach(r => variance += Math.pow(r.ratio - mean, 2));
        const std = Math.sqrt(variance / count);

        // Add bands
        spreadSeries.forEach(r => {
            (r as any).upperBound = mean + (2 * std);
            (r as any).lowerBound = mean - (2 * std);
            (r as any).mean = mean;
        });

        spreadSeries.sort((a, b) => a.date.localeCompare(b.date));
        return { series: downsampleData(spreadSeries, 100), mean, std, active: true };

    }, [symbols, barsData]);

    const formatPct = (val?: number | null) => val != null ? `${val.toFixed(2)}%` : "N/A";

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row gap-4">
                <div className="w-full md:w-1/3 border border-border rounded-lg bg-card p-4 space-y-4">
                    <div>
                        <h3 className="font-semibold mb-2">Watchlist ({symbols.length}/{MAX_SYMBOLS})</h3>
                        <AssetSearch 
                            onSelectAsset={handleAddSymbol} 
                            placeholder="Add symbol..." 
                            className="mb-4"
                        />
                        {symbols.length === 0 ? (
                            <p className="text-sm text-muted-foreground italic">List is empty. Add symbols to start the lab.</p>
                        ) : (
                            <ul className="space-y-2">
                                {symbols.map((s, i) => (
                                    <li key={s.symbol} className="flex items-center justify-between p-2 rounded-md bg-muted/50 text-sm">
                                        <div className="flex items-center space-x-2">
                                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }}></div>
                                            <span className="font-bold">{s.symbol}</span>
                                        </div>
                                        <button onClick={() => handleRemoveSymbol(s.symbol)} className="text-muted-foreground hover:text-destructive">
                                            <X className="w-4 h-4" />
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                        <p className="text-[10px] text-muted-foreground mt-4">
                            Saved locally in your browser. Select exactly 2 symbols to unlock the Pair Trading view.
                        </p>
                    </div>
                </div>

                <div className="w-full md:w-2/3 border border-border rounded-lg bg-card p-4">
                    {symbols.length === 0 ? (
                        <div className="h-full min-h-[300px] flex items-center justify-center text-muted-foreground flex-col gap-2">
                            <Plus className="w-8 h-8 opacity-20" />
                            <p>Build your watchlist to view comparative Lab analytics.</p>
                        </div>
                    ) : isLoading ? (
                        <div className="space-y-8">
                            <div>
                                <h3 className="font-semibold text-sm mb-4">Overlay Normalized Performance (1Y)</h3>
                                <Skeleton className="h-[250px] w-full" />
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-border">
                                <div>
                                    <h3 className="font-semibold text-sm mb-4">Risk-Return Scatter</h3>
                                    <Skeleton className="h-[200px] w-full" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-sm mb-4">Correlation Core</h3>
                                    <Skeleton className="w-full aspect-square max-w-[200px] mx-auto" />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-8">
                            
                            {/* 1. Normalized Performance */}
                            <div>
                                <h3 className="font-semibold text-sm mb-4">Overlay Normalized Performance (1Y)</h3>
                                <div className="h-[250px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={chartDataRebased}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground)/0.2)" />
                                            <XAxis dataKey="date" tickFormatter={(v) => v.split("-")[0]} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" minTickGap={30} />
                                            <YAxis domain={['dataMin - 5', 'dataMax + 5']} tickFormatter={(val) => Math.round(val).toString()} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                                            <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', fontSize: '10px' }} />
                                            {symbolKeys.map((sym, i) => (
                                                <Line key={sym} type="monotone" dataKey={sym} stroke={COLORS[i % COLORS.length]} dot={false} strokeWidth={2} />
                                            ))}
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-border">
                                {/* 2. Risk-Return Scatter */}
                                <div>
                                    <h3 className="font-semibold text-sm mb-4">Risk-Return Scatter</h3>
                                    <div className="h-[200px] w-full border border-border rounded-lg bg-background p-2">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted-foreground)/0.2)" />
                                                <XAxis type="number" dataKey="volatility" name="Volatility" unit="%" tickFormatter={(val) => Math.round(val).toString()} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))">
                                                    <title>1Y Volatility</title>
                                                </XAxis>
                                                <YAxis type="number" dataKey="return" name="Return" unit="%" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                                                <ZAxis type="category" dataKey="symbol" name="Symbol" />
                                                <Tooltip cursor={{ strokeDasharray: '3 3' }} 
                                                    contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', fontSize: '12px' }}
                                                    formatter={(val: number | string | undefined) => typeof val === 'number' ? `${val.toFixed(2)}%` : val}
                                                />
                                                {scatterData.map((entry, index) => (
                                                    <Scatter key={entry.symbol} name={entry.symbol} data={[entry]} fill={COLORS[index % COLORS.length]} />
                                                ))}
                                            </ScatterChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <p className="text-[10px] text-muted-foreground mt-2 text-center">X: Volatility (Risk) | Y: Return (Reward)</p>
                                </div>

                                {/* 3. Correlation Heatmap */}
                                <div>
                                    <h3 className="font-semibold text-sm mb-4">Correlation Core</h3>
                                    <div className="w-full aspect-square border-t border-l border-border relative max-w-[200px] mx-auto">
                                        {symbolKeys.map((s1, r) => (
                                            <div key={`row-${s1}`} className="flex" style={{ height: `${100/symbolKeys.length}%` }}>
                                                {symbolKeys.map((s2, c) => {
                                                    const corr = corrMatrix[s1]?.[s2] || 0;
                                                    const intensity = Math.abs(corr);
                                                    const bgColor = corr > 0 
                                                        ? `rgba(74, 222, 128, ${Math.max(0.1, intensity)})` 
                                                        : `rgba(248, 113, 113, ${Math.max(0.1, intensity)})`;
                                                    
                                                    return (
                                                        <div 
                                                            key={`cell-${s1}-${s2}`}
                                                            title={`${s1}/${s2}: ${corr.toFixed(2)}`}
                                                            className="border-r border-b border-border flex items-center justify-center text-[8px] font-medium cursor-default"
                                                            style={{ width: `${100/symbolKeys.length}%`, backgroundColor: s1 === s2 ? 'hsl(var(--muted))' : bgColor }}
                                                        >
                                                            {corr.toFixed(1)}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* 4. Pair Spread Tool */}
                            {pairSpreadSeries?.active && pairSpreadSeries.series.length > 0 && (
                                <div className="pt-8 border-t border-border">
                                    <h3 className="font-semibold text-sm mb-4">Pair Spread: Ratio ({symbols[0].symbol} / {symbols[1].symbol})</h3>
                                    <div className="h-[200px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={pairSpreadSeries.series}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground)/0.2)" />
                                                <XAxis dataKey="date" tickFormatter={(v) => v.split("-").slice(1).join("/")} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" minTickGap={30} />
                                                <YAxis domain={['auto', 'auto']} tickFormatter={(val) => val.toFixed(2)} tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" width={40} />
                                                <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', fontSize: '10px' }} />
                                                <Line type="monotone" dataKey="ratio" stroke="hsl(var(--primary))" dot={false} strokeWidth={2} name="Ratio" />
                                                <Line type="monotone" dataKey="mean" stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" dot={false} name="Mean" />
                                                <Line type="monotone" dataKey="upperBound" stroke="#ef4444" strokeDasharray="2 2" dot={false} name="+2σ" />
                                                <Line type="monotone" dataKey="lowerBound" stroke="#22c55e" strokeDasharray="2 2" dot={false} name="-2σ" />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <p className="text-[10px] text-muted-foreground mt-4 text-center">
                                        Spread is ±2σ bands. Used for mean reversion statistical arbitrage inference.
                                    </p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
