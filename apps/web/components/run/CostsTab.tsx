"use client"

import {
    Area,
    AreaChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
    BarChart,
    Bar,
    Cell
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { RunData, RunFillOut, getRunFills } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
import { useEffect, useState } from "react"
import { ArrowDownRight, Percent, DollarSign, Wallet, ShieldAlert } from "lucide-react"

interface CostsTabProps {
    data: RunData
    status?: string
}

export function CostsTab({ data, status }: CostsTabProps) {
    const [fills, setFills] = useState<RunFillOut[]>([]);
    const [isLoadingFills, setIsLoadingFills] = useState(true);
    const [fillsError, setFillsError] = useState(false);

    useEffect(() => {
        setIsLoadingFills(true);
        setFillsError(false);
        getRunFills(data.id)
            .then(res => setFills(res))
            .catch(() => setFillsError(true))
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

    const gross = (costs?.gross_return ?? 0) * 100;
    const fees = (costs?.fee_drag ?? 0) * 100;
    const taxes = (costs?.tax_drag ?? 0) * 100;
    const borrow = (costs?.borrow_drag ?? 0) * 100;
    const margin = (costs?.margin_interest_drag ?? 0) * 100;
    const net = (costs?.net_return ?? 0) * 100;

    // Largest Drag Calculation
    const dragCategories = [
        { label: "Transaction Fees", value: fees, badgeClass: "text-amber-600 bg-amber-500/10 border-amber-500/20" },
        { label: "Tax Liabilities", value: taxes, badgeClass: "text-red-600 bg-red-500/10 border-red-500/20" },
        { label: "Short Borrow Fees", value: borrow, badgeClass: "text-orange-600 bg-orange-500/10 border-orange-500/20" },
        { label: "Margin Financing Interest", value: margin, badgeClass: "text-yellow-600 bg-yellow-500/10 border-yellow-500/20" }
    ];
    const largestDrag = [...dragCategories].sort((a, b) => b.value - a.value)[0];

    // Waterfall Data definition with bps drag and running total
    const grossVal = costs?.gross_return ?? 0;
    const feeVal = costs?.fee_drag ?? 0;
    const taxVal = costs?.tax_drag ?? 0;
    const borrowVal = costs?.borrow_drag ?? 0;
    const marginVal = costs?.margin_interest_drag ?? 0;
    const netVal = costs?.net_return ?? (grossVal - feeVal - taxVal - borrowVal - marginVal);

    const waterfallSteps = [
        { name: "Gross Return", dragPct: grossVal * 100, dragBps: null, runningTotal: grossVal * 100, uv: [0, gross], fill: "hsl(var(--primary))" },
        { name: "Fees", dragPct: -fees, dragBps: Math.round(feeVal * 10000), runningTotal: gross - fees, uv: [gross - fees, gross], fill: "rgba(245, 158, 11, 0.85)" },
        { name: "Taxes", dragPct: -taxes, dragBps: Math.round(taxVal * 10000), runningTotal: gross - fees - taxes, uv: [gross - fees - taxes, gross - fees], fill: "rgba(239, 68, 68, 0.85)" },
        { name: "Borrow Fees", dragPct: -borrow, dragBps: Math.round(borrowVal * 10000), runningTotal: gross - fees - taxes - borrow, uv: [gross - fees - taxes - borrow, gross - fees - taxes], fill: "rgba(249, 115, 22, 0.85)" },
        { name: "Margin Interest", dragPct: -margin, dragBps: Math.round(marginVal * 10000), runningTotal: gross - fees - taxes - borrow - margin, uv: [gross - fees - taxes - borrow - margin, gross - fees - taxes - borrow], fill: "rgba(234, 179, 8, 0.85)" },
        { name: "Net Return", dragPct: net, dragBps: null, runningTotal: net, uv: [0, net], fill: "hsl(var(--chart-1))" }
    ];

    return (
        <div className="space-y-6">
            {/* Top Bar with Title and Largest Drag Badge */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h3 className="text-lg font-bold tracking-tight">Friction & Cost Drag Breakdown</h3>
                    <p className="text-xs text-muted-foreground">Quantifying leakage from transaction fees, taxation, and leverage financing.</p>
                </div>
                {largestDrag && largestDrag.value > 0.01 && (
                    <Badge variant="outline" className={`px-3 py-1 text-xs font-semibold self-start sm:self-center ${largestDrag.badgeClass}`}>
                        <ShieldAlert className="w-3.5 h-3.5 mr-1" /> Largest Drag: {largestDrag.label} (-{largestDrag.value.toFixed(2)}% / {(largestDrag.value * 100).toFixed(0)} bps)
                    </Badge>
                )}
            </div>

            {/* Category Cards with color accents and visual meters */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="border-l-4 border-l-amber-500 overflow-hidden relative">
                    <CardHeader className="py-3.5 pb-2">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center justify-between">
                            Fee Drag <ArrowDownRight className="w-3.5 h-3.5 text-amber-500" />
                        </span>
                        <div className="text-xl font-extrabold font-mono mt-1">{formatDrag(costs?.fee_drag)}</div>
                    </CardHeader>
                    <CardContent className="pt-0 text-[10px] text-muted-foreground flex justify-between">
                        <span>Commissions & slippage</span>
                        <span className="font-mono font-semibold">{Math.round((costs?.fee_drag || 0) * 10000)} bps</span>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-red-500 overflow-hidden relative">
                    <CardHeader className="py-3.5 pb-2">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center justify-between">
                            Tax Drag <ArrowDownRight className="w-3.5 h-3.5 text-red-500" />
                        </span>
                        <div className="text-xl font-extrabold font-mono mt-1">{formatDrag(costs?.tax_drag)}</div>
                    </CardHeader>
                    <CardContent className="pt-0 text-[10px] text-muted-foreground flex justify-between">
                        <span>Realized capital gains taxes</span>
                        <span className="font-mono font-semibold">{Math.round((costs?.tax_drag || 0) * 10000)} bps</span>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-orange-500 overflow-hidden relative">
                    <CardHeader className="py-3.5 pb-2">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center justify-between">
                            Borrow Drag <ArrowDownRight className="w-3.5 h-3.5 text-orange-500" />
                        </span>
                        <div className="text-xl font-extrabold font-mono mt-1">{formatDrag(costs?.borrow_drag)}</div>
                    </CardHeader>
                    <CardContent className="pt-0 text-[10px] text-muted-foreground flex justify-between">
                        <span>Short position borrow fees</span>
                        <span className="font-mono font-semibold">{Math.round((costs?.borrow_drag || 0) * 10000)} bps</span>
                    </CardContent>
                </Card>
                <Card className="border-l-4 border-l-yellow-500 overflow-hidden relative">
                    <CardHeader className="py-3.5 pb-2">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center justify-between">
                            Margin Drag <ArrowDownRight className="w-3.5 h-3.5 text-yellow-500" />
                        </span>
                        <div className="text-xl font-extrabold font-mono mt-1">{formatDrag(costs?.margin_interest_drag)}</div>
                    </CardHeader>
                    <CardContent className="pt-0 text-[10px] text-muted-foreground flex justify-between">
                        <span>Leverage borrowing interest</span>
                        <span className="font-mono font-semibold">{Math.round((costs?.margin_interest_drag || 0) * 10000)} bps</span>
                    </CardContent>
                </Card>
            </div>

            {/* Waterfall Cost Chart & Cumulative chart side by side */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Cost Waterfall Chart with Bps Drag Table */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-semibold">Cost Drag Waterfall</CardTitle>
                        <CardDescription>Decomposition of Gross Return down to Net Return with step bps drag</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="h-[250px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={waterfallSteps} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                    <XAxis dataKey="name" fontSize={10} tickLine={false} axisLine={false} />
                                    <YAxis 
                                        stroke="#888888" 
                                        fontSize={11} 
                                        tickLine={false} 
                                        axisLine={false} 
                                        tickFormatter={(v) => v.toFixed(1) + "%"}
                                    />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))' }}
                                        itemStyle={{ color: 'hsl(var(--foreground))' }}
                                        labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 'bold' }}
                                        formatter={(value: any, name: any, props: any) => {
                                            const step = props.payload;
                                            return [
                                                `${step.runningTotal.toFixed(2)}% (${step.dragBps !== null ? `-${step.dragBps} bps` : "Total"})`,
                                                step.name
                                            ];
                                        }}
                                    />
                                    <Bar dataKey="uv">
                                        {waterfallSteps.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.fill} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Step breakdown table */}
                        <div className="rounded-md border border-border/50 overflow-hidden text-xs">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="bg-muted/40 border-b border-border/50 text-[11px] text-muted-foreground">
                                        <th className="p-2 font-medium">Waterfall Step</th>
                                        <th className="p-2 font-medium text-right">Step Impact</th>
                                        <th className="p-2 font-medium text-right">Drag (bps)</th>
                                        <th className="p-2 font-medium text-right">Running Net</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {waterfallSteps.map((s, idx) => (
                                        <tr key={idx} className="border-b border-border/20 font-mono text-[11px]">
                                            <td className="p-2 font-sans font-medium text-foreground flex items-center gap-1.5">
                                                <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ backgroundColor: s.fill }} />
                                                {s.name}
                                            </td>
                                            <td className="p-2 text-right">
                                                {s.dragBps !== null ? `-${Math.abs(s.dragPct).toFixed(2)}%` : `${s.dragPct.toFixed(2)}%`}
                                            </td>
                                            <td className="p-2 text-right text-muted-foreground">
                                                {s.dragBps !== null ? `-${s.dragBps} bps` : "—"}
                                            </td>
                                            <td className="p-2 text-right font-bold text-foreground">
                                                {s.runningTotal.toFixed(2)}%
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>

                {/* Cumulative Costs Area chart */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm font-semibold">Cumulative Friction Over Time</CardTitle>
                        <CardDescription>Friction costs accumulated over time (Base Currency)</CardDescription>
                    </CardHeader>
                    <CardContent className="pl-0">
                        <div className="h-[300px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={equity} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
                                    <XAxis
                                        dataKey="date"
                                        stroke="#888888"
                                        fontSize={11}
                                        tickLine={false}
                                        axisLine={false}
                                        tickFormatter={(val) => {
                                            const d = new Date(val);
                                            return !isNaN(d.getTime()) ? d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }) : val;
                                        }}
                                    />
                                    <YAxis
                                        stroke="#888888"
                                        fontSize={11}
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
                                        stroke="#ea580c"
                                        fill="#f97316"
                                        fillOpacity={0.1}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="borrow_fees_cum_base"
                                        name="Borrow Fees"
                                        stackId="1"
                                        stroke="#d97706"
                                        fill="#f59e0b"
                                        fillOpacity={0.1}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="taxes_cum_base"
                                        name="Taxes"
                                        stackId="1"
                                        stroke="#16a34a"
                                        fill="#10b981"
                                        fillOpacity={0.1}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="fees_cum_base"
                                        name="Commissions/Slippage"
                                        stackId="1"
                                        stroke="#2563eb"
                                        fill="#3b82f6"
                                        fillOpacity={0.1}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Trades list card */}
            <Card>
                <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 gap-2">
                    <div>
                        <CardTitle className="text-sm font-semibold">Executions Log</CardTitle>
                        <CardDescription>Fills executed during this backtest simulation.</CardDescription>
                    </div>
                    {!isLoadingFills && fills.length > 0 && (
                        <Badge variant="secondary" className="px-3 py-1 font-mono text-xs w-fit">
                            Commission: {formatCurrency(totalCommission, data.baseCurrency)} | Slippage: {formatCurrency(totalSlippage, data.baseCurrency)}
                        </Badge>
                    )}
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border max-h-[300px] overflow-auto">
                        <table className="w-full text-xs text-left relative">
                            <thead className="bg-muted text-muted-foreground border-b border-border sticky top-0 z-10">
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
                                ) : fillsError ? (
                                    <tr>
                                        <td colSpan={7} className="px-4 py-8 text-center text-destructive">
                                            Failed to load trades. Please refresh and try again.
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
                                            <td className="px-4 py-3 font-mono text-[10px] text-muted-foreground">{new Date(fill.date).toLocaleString()}</td>
                                            <td className="px-4 py-3 font-bold">{fill.symbol}</td>
                                            <td className="px-4 py-3">
                                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${fill.side?.toUpperCase() === "BUY" ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400" :
                                                    fill.side?.toUpperCase() === "SELL" ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-400" :
                                                        fill.side?.toUpperCase() === "FX" ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-400" :
                                                        "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400"
                                                    }`}>
                                                    {fill.side || "N/A"}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-right font-mono">{fill.qty.toLocaleString()}</td>
                                            <td className="px-4 py-3 text-right font-mono">{formatCurrency(fill.price, data.baseCurrency)}</td>
                                            <td className="px-4 py-3 text-right font-mono text-muted-foreground">{formatCurrency(fill.commission, data.baseCurrency)}</td>
                                            <td className="px-4 py-3 text-right font-mono text-muted-foreground">{formatCurrency(fill.slippage, data.baseCurrency)}</td>
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
