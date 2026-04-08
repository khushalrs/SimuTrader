"use client"

import useSWR from "swr"
import { getRunTaxes } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

interface TaxesTabProps {
    runId: string;
    baseCurrency: string;
    status: string;
}

export function TaxesTab({ runId, baseCurrency, status }: TaxesTabProps) {
    const { data: taxes, isLoading } = useSWR(
        status === "SUCCEEDED" ? `/runs/${runId}/taxes` : null,
        () => getRunTaxes(runId),
        { revalidateOnFocus: false }
    );

    if (isLoading || status === "RUNNING" || status === "QUEUED") {
        return <Skeleton className="w-full h-[400px] rounded-lg" />
    }

    if (!taxes) {
        return (
            <div className="flex flex-col items-center justify-center p-8 text-center bg-secondary/10 rounded-lg min-h-[400px]">
                <p className="text-muted-foreground font-medium">No tax data available for this run.</p>
                <p className="text-sm text-muted-foreground mt-2 max-w-md">Make sure you have enabled a tax regime in your strategy and that trades were executed.</p>
            </div>
        )
    }

    const { 
        event_count, 
        total_realized_pnl_base, 
        total_tax_due_base, 
        by_bucket_tax_due_base, 
        events 
    } = taxes;

    if (event_count === 0 || !events || events.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-8 text-center bg-secondary/10 rounded-lg min-h-[400px]">
                <p className="text-muted-foreground font-medium">No taxable events recorded.</p>
                <p className="text-sm text-muted-foreground mt-2 max-w-md">There were no realized gains/losses subject to taxation during this run.</p>
            </div>
        )
    }

    // Sort events by date descending
    const sortedEvents = [...events].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="border-l-4 border-l-destructive/50">
                    <CardHeader className="pb-4">
                        <CardDescription>Total Tax Due</CardDescription>
                        <CardTitle className="text-2xl text-destructive font-mono">
                            {formatCurrency(total_tax_due_base, baseCurrency)}
                        </CardTitle>
                    </CardHeader>
                </Card>
                <Card className={`border-l-4 ${total_realized_pnl_base >= 0 ? 'border-l-emerald-500/50' : 'border-l-amber-500/50'}`}>
                    <CardHeader className="pb-4">
                        <CardDescription>Total Realized PnL</CardDescription>
                        <CardTitle className={`text-2xl font-mono ${total_realized_pnl_base >= 0 ? "text-emerald-500" : "text-amber-500"}`}>
                            {formatCurrency(total_realized_pnl_base, baseCurrency)}
                        </CardTitle>
                    </CardHeader>
                </Card>
                <Card className="md:col-span-2">
                    <CardHeader className="pb-4">
                        <CardDescription>Tax Due By Bucket</CardDescription>
                        <div className="flex flex-wrap gap-2 pt-2">
                            {Object.entries(by_bucket_tax_due_base).length > 0 ? Object.entries(by_bucket_tax_due_base).map(([bucket, amount]) => (
                                <Badge variant="secondary" key={bucket} className="flex items-center gap-2 font-mono text-xs py-1.5 px-3">
                                    <span className="font-semibold uppercase opacity-70 tracking-wider">{bucket}</span>
                                    <span className={amount > 0 ? "text-destructive font-medium" : ""}>{formatCurrency(amount, baseCurrency)}</span>
                                </Badge>
                            )) : (
                                <span className="text-sm text-muted-foreground">None</span>
                            )}
                        </div>
                    </CardHeader>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Taxable Events</CardTitle>
                    <CardDescription>Line items of realized gains/losses over the backtest period.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border overflow-hidden">
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow className="bg-secondary/20">
                                        <TableHead className="w-[120px]">Date</TableHead>
                                        <TableHead>Symbol</TableHead>
                                        <TableHead className="text-right">Qty</TableHead>
                                        <TableHead className="text-right">Realized PnL</TableHead>
                                        <TableHead className="text-right">Hold (Days)</TableHead>
                                        <TableHead>Bucket</TableHead>
                                        <TableHead className="text-right">Rate</TableHead>
                                        <TableHead className="text-right border-l font-semibold bg-destructive/5 text-destructive dark:text-red-400">Tax Due</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {sortedEvents.map((evt, idx) => (
                                        <TableRow key={`${evt.date}-${evt.symbol}-${idx}`}>
                                            <TableCell className="font-mono text-xs whitespace-nowrap text-muted-foreground">{evt.date.split("T")[0]}</TableCell>
                                            <TableCell className="font-medium">{evt.symbol}</TableCell>
                                            <TableCell className="text-right font-mono text-xs">{evt.quantity}</TableCell>
                                            <TableCell className={`text-right font-mono text-xs ${evt.realized_pnl_base >= 0 ? "text-emerald-500" : "text-amber-500"}`}>
                                                {formatCurrency(evt.realized_pnl_base, baseCurrency)}
                                            </TableCell>
                                            <TableCell className="text-right font-mono text-xs opacity-70">{evt.holding_period_days}</TableCell>
                                            <TableCell>
                                                <Badge variant="outline" className="text-[10px] uppercase font-mono tracking-wider opacity-70 bg-secondary/30">
                                                    {evt.bucket}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-right font-mono text-xs opacity-70">{(evt.tax_rate * 100).toFixed(1)}%</TableCell>
                                            <TableCell className="text-right font-mono text-xs font-medium border-l bg-destructive/5 text-destructive dark:text-red-400">
                                                {formatCurrency(evt.tax_due_base, baseCurrency)}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
