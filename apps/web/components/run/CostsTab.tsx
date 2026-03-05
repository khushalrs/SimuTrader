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
import { RunData, RunFillOut, getRunFills } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
import { useEffect, useState } from "react"

interface CostsTabProps {
    data: RunData
    status?: string
}

export function CostsTab({ data, status }: CostsTabProps) {
    const [fills, setFills] = useState<RunFillOut[]>([]);
    const [isLoadingFills, setIsLoadingFills] = useState(true);

    useEffect(() => {
        setIsLoadingFills(true);
        getRunFills(data.id)
            .then(res => setFills(res))
            .catch(err => console.error(err))
            .finally(() => setIsLoadingFills(false));
    }, [data.id, status]);

    const equity = data.equity || [];

    if (equity.length === 0) {
        return <div className="p-4 text-center text-muted-foreground">No data available for cost analysis</div>
    }

    const { costs } = data;

    // Helper to format drag as percentage
    const formatDrag = (val?: number | null) => {
        if (val === undefined || val === null) return "0.00%";
        return `${(val * 100).toFixed(2)}%`;
    }

    const totalCommission = fills.reduce((sum, f) => sum + f.commission, 0);
    const totalSlippage = fills.reduce((sum, f) => sum + f.slippage, 0);

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardHeader className="py-4">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Fee Drag</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{formatDrag(costs?.fee_drag)}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="py-4">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Tax Drag</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{formatDrag(costs?.tax_drag)}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="py-4">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Borrow Drag</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{formatDrag(costs?.borrow_drag)}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="py-4">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Margin Drag</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{formatDrag(costs?.margin_interest_drag)}</div>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Cumulative Costs</CardTitle>
                    <CardDescription>
                        Friction costs accumulated over time (Base Currency).
                    </CardDescription>
                </CardHeader>
                <CardContent className="pl-0">
                    <div className="h-[350px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={equity} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
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
                                    tickFormatter={(value) => formatCurrency(value, data.baseCurrency, true)}
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
                                    dataKey="margin_interest_cum_base"
                                    name="Margin Interest"
                                    stackId="1"
                                    stroke="#ffc658"
                                    fill="#ffc658"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="borrow_fees_cum_base"
                                    name="Borrow Fees"
                                    stackId="1"
                                    stroke="#ff7300"
                                    fill="#ff7300"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="taxes_cum_base"
                                    name="Taxes"
                                    stackId="1"
                                    stroke="#82ca9d"
                                    fill="#82ca9d"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="fees_cum_base"
                                    name="Commissions/Slippage"
                                    stackId="1"
                                    stroke="#8884d8"
                                    fill="#8884d8"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Trades</CardTitle>
                    <CardDescription>
                        Fills executed during this backtest.
                        {!isLoadingFills && fills.length > 0 && (
                            <span className="block mt-1 font-medium">
                                Totals - Commission: {formatCurrency(totalCommission, data.baseCurrency)} | Slippage: {formatCurrency(totalSlippage, data.baseCurrency)}
                            </span>
                        )}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border max-h-[400px] overflow-auto">
                        <table className="w-full text-sm text-left relative">
                            <thead className="bg-muted text-muted-foreground border-b border-border sticky top-0">
                                <tr>
                                    <th className="px-4 py-3 font-medium">Date</th>
                                    <th className="px-4 py-3 font-medium">Symbol</th>
                                    <th className="px-4 py-3 font-medium">Side</th>
                                    <th className="px-4 py-3 font-medium text-right">Qty</th>
                                    <th className="px-4 py-3 font-medium text-right">Price</th>
                                    <th className="px-4 py-3 font-medium text-right">Commission</th>
                                    <th className="px-4 py-3 font-medium text-right">Slippage</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isLoadingFills ? (
                                    <tr>
                                        <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                                            Loading trades...
                                        </td>
                                    </tr>
                                ) : fills.length === 0 ? (
                                    <tr>
                                        <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                                            No trades executed during this run.
                                        </td>
                                    </tr>
                                ) : (
                                    fills.map((fill, i) => (
                                        <tr key={i} className="border-b transition-colors hover:bg-muted/50 whitespace-nowrap">
                                            <td className="px-4 py-3">{new Date(fill.date).toLocaleString()}</td>
                                            <td className="px-4 py-3 font-medium">{fill.symbol}</td>
                                            <td className="px-4 py-3">
                                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${fill.side?.toUpperCase() === "BUY" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                                                    fill.side?.toUpperCase() === "SELL" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
                                                        "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400"
                                                    }`}>
                                                    {fill.side || "N/A"}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-right">{fill.qty.toLocaleString()}</td>
                                            <td className="px-4 py-3 text-right">{formatCurrency(fill.price, data.baseCurrency)}</td>
                                            <td className="px-4 py-3 text-right">{formatCurrency(fill.commission, data.baseCurrency)}</td>
                                            <td className="px-4 py-3 text-right">{formatCurrency(fill.slippage, data.baseCurrency)}</td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
