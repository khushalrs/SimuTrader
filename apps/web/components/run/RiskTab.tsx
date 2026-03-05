"use client"

import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { RunEquityPoint } from "@/lib/api"

interface RiskTabProps {
    equity?: RunEquityPoint[]
}

export function RiskTab({ equity }: RiskTabProps) {
    if (!equity || equity.length === 0) {
        return <div className="p-4 text-center text-muted-foreground">No data available for risk analysis</div>
    }

    // Prepare Returns Distribution Data
    const returns: number[] = []
    let minReturn = 0;
    let maxReturn = 0;

    for (let i = 1; i < equity.length; i++) {
        const prev = equity[i - 1].value
        const curr = equity[i].value
        if (prev > 0) {
            const ret = (curr - prev) / prev;
            returns.push(ret)
            if (ret < minReturn) minReturn = ret;
            if (ret > maxReturn) maxReturn = ret;
        }
    }

    // Create 20 bins for the distribution
    const numBins = 20;
    const binSize = (maxReturn - minReturn) / numBins;
    const bins = Array.from({ length: numBins }, (_, i) => ({
        binStart: minReturn + i * binSize,
        binEnd: minReturn + (i + 1) * binSize,
        count: 0,
        label: `${((minReturn + (i + 0.5) * binSize) * 100).toFixed(1)}%`
    }));

    returns.forEach(ret => {
        let binIndex = Math.floor((ret - minReturn) / binSize);
        if (binIndex >= numBins) binIndex = numBins - 1;
        if (binIndex < 0) binIndex = 0;
        bins[binIndex].count += 1;
    });

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="col-span-1 md:col-span-2">
                <CardHeader>
                    <CardTitle>Drawdown</CardTitle>
                    <CardDescription>
                        Peak-to-trough decline over the period.
                    </CardDescription>
                </CardHeader>
                <CardContent className="pl-0">
                    <div className="h-[250px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={equity} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="hsl(var(--destructive))" stopOpacity={0.8} />
                                        <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0.1} />
                                    </linearGradient>
                                </defs>
                                <XAxis
                                    dataKey="date"
                                    stroke="#888888"
                                    fontSize={12}
                                    tickLine={false}
                                    axisLine={false}
                                    tickFormatter={(val) => {
                                        const d = new Date(val);
                                        return !isNaN(d.getTime()) ? d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }) : val;
                                    }}
                                />
                                <YAxis
                                    stroke="#888888"
                                    fontSize={12}
                                    tickLine={false}
                                    axisLine={false}
                                    tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                    width={60}
                                />
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                <Tooltip
                                    contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                    itemStyle={{ color: 'hsl(var(--foreground))' }}
                                    formatter={(value: any) => {
                                        if (typeof value === 'number') return [`${(value * 100).toFixed(2)}%`, 'Drawdown'];
                                        return [value, 'Drawdown'];
                                    }}
                                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                                />
                                <Area
                                    type="stepAfter"
                                    dataKey="drawdown"
                                    stroke="hsl(var(--destructive))"
                                    fillOpacity={1}
                                    fill="url(#colorDrawdown)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </CardContent>
            </Card>

            <Card className="col-span-1 md:col-span-2">
                <CardHeader>
                    <CardTitle>Daily Returns Distribution</CardTitle>
                    <CardDescription>
                        Histogram of daily return frequencies.
                    </CardDescription>
                </CardHeader>
                <CardContent className="pl-0">
                    <div className="h-[250px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={bins} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                <XAxis
                                    dataKey="label"
                                    stroke="#888888"
                                    fontSize={12}
                                    tickLine={false}
                                    axisLine={false}
                                />
                                <YAxis
                                    stroke="#888888"
                                    fontSize={12}
                                    tickLine={false}
                                    axisLine={false}
                                    width={40}
                                />
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                <Tooltip
                                    contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                    itemStyle={{ color: 'hsl(var(--foreground))' }}
                                    formatter={(value: any) => [value, 'Days']}
                                />
                                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
