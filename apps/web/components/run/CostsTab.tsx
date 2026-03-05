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
import { RunData } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"

interface CostsTabProps {
    data: RunData
}

export function CostsTab({ data }: CostsTabProps) {
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
        </div>
    )
}
