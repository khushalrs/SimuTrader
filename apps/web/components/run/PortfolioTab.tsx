"use client"

import {
    Area,
    AreaChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { RunEquityPoint } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"

interface PortfolioTabProps {
    equity?: RunEquityPoint[]
    baseCurrency?: string
}

export function PortfolioTab({ equity, baseCurrency }: PortfolioTabProps) {
    if (!equity || equity.length === 0) {
        return <div className="p-4 text-center text-muted-foreground">No data available for portfolio analysis</div>
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="col-span-1 md:col-span-2">
                <CardHeader>
                    <CardTitle>Exposure</CardTitle>
                    <CardDescription>
                        Gross and Net Exposure base value over time.
                    </CardDescription>
                </CardHeader>
                <CardContent className="pl-0">
                    <div className="h-[250px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={equity} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorGross" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8} />
                                        <stop offset="95%" stopColor="#8884d8" stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id="colorNet" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#82ca9d" stopOpacity={0.8} />
                                        <stop offset="95%" stopColor="#82ca9d" stopOpacity={0} />
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
                                    tickFormatter={(value) => {
                                        if (Math.abs(value) >= 1000000) {
                                            return formatCurrency(value / 1000000, baseCurrency, true) + 'M';
                                        }
                                        return formatCurrency(value, baseCurrency, true);
                                    }}
                                    width={60}
                                />
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                <Tooltip
                                    contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                    itemStyle={{ color: 'hsl(var(--foreground))' }}
                                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="gross_exposure_base"
                                    name="Gross Exposure"
                                    stroke="#8884d8"
                                    fillOpacity={1}
                                    fill="url(#colorGross)"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="net_exposure_base"
                                    name="Net Exposure"
                                    stroke="#82ca9d"
                                    fillOpacity={1}
                                    fill="url(#colorNet)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </CardContent>
            </Card>

            <Card className="col-span-1 md:col-span-2">
                <CardHeader>
                    <CardTitle>Current Holdings</CardTitle>
                    <CardDescription>
                        Positions snapshot at the end of the backtest. (MVP Placeholder)
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-muted text-muted-foreground border-b border-border">
                                <tr>
                                    <th className="px-4 py-3 font-medium">Symbol</th>
                                    <th className="px-4 py-3 font-medium text-right">Weight</th>
                                    <th className="px-4 py-3 font-medium text-right">Shares</th>
                                    <th className="px-4 py-3 font-medium text-right">Value (Base)</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                                        Positions endpoint not yet implemented in backend.<br />
                                        Holdings snapshot will appear here.
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
