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
import { Scale, TrendingUp, ShieldAlert, ArrowDownRight, Globe } from "lucide-react"

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

    // Calculate Short-Term vs Long-Term splits & alternative simulations
    let shortTermTax = 0;
    let longTermTax = 0;
    let shortTermPnl = 0;
    let longTermPnl = 0;

    let simulatedUsTax = 0;
    let simulatedInTax = 0;

    const activeRegime = events[0]?.bucket?.startsWith("US") ? "US" : (events[0]?.bucket?.startsWith("INDIA") ? "INDIA" : "NONE");

    events.forEach(evt => {
        const isShort = evt.bucket.endsWith("_ST") || evt.holding_period_days <= 365;
        const pnl = evt.realized_pnl_base;
        const gain = Math.max(pnl, 0.0);

        if (evt.bucket.endsWith("_ST")) {
            shortTermTax += evt.tax_due_base;
            shortTermPnl += pnl;
        } else {
            longTermTax += evt.tax_due_base;
            longTermPnl += pnl;
        }

        // US regime simulation: ST (30%), LT (15%)
        simulatedUsTax += isShort ? (gain * 0.30) : (gain * 0.15);
        // India regime simulation: ST (20%), LT (12.5%)
        simulatedInTax += isShort ? (gain * 0.20) : (gain * 0.125);
    });

    return (
        <div className="space-y-6">
            {/* Top row Category Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="border-l-4 border-l-destructive">
                    <CardHeader className="py-3 pb-1">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center justify-between">
                            Total Tax Due <ArrowDownRight className="w-3.5 h-3.5 text-destructive" />
                        </span>
                        <div className="text-xl font-extrabold font-mono text-destructive mt-0.5">
                            {formatCurrency(total_tax_due_base, baseCurrency)}
                        </div>
                    </CardHeader>
                </Card>
                <Card className={`border-l-4 ${total_realized_pnl_base >= 0 ? 'border-l-emerald-500' : 'border-l-amber-500'}`}>
                    <CardHeader className="py-3 pb-1">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground flex items-center justify-between">
                            Realized PnL <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                        </span>
                        <div className={`text-xl font-extrabold font-mono mt-0.5 ${total_realized_pnl_base >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600"}`}>
                            {formatCurrency(total_realized_pnl_base, baseCurrency)}
                        </div>
                    </CardHeader>
                </Card>
                <Card className="border-l-4 border-l-indigo-500">
                    <CardHeader className="py-3 pb-1">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Short-Term Tax / PnL</span>
                        <div className="text-base font-bold font-mono mt-0.5 text-foreground">
                            {formatCurrency(shortTermTax, baseCurrency)} <span className="text-xs font-normal text-muted-foreground">/ {formatCurrency(shortTermPnl, baseCurrency)}</span>
                        </div>
                    </CardHeader>
                </Card>
                <Card className="border-l-4 border-l-teal-500">
                    <CardHeader className="py-3 pb-1">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Long-Term Tax / PnL</span>
                        <div className="text-base font-bold font-mono mt-0.5 text-foreground">
                            {formatCurrency(longTermTax, baseCurrency)} <span className="text-xs font-normal text-muted-foreground">/ {formatCurrency(longTermPnl, baseCurrency)}</span>
                        </div>
                    </CardHeader>
                </Card>
            </div>

            {/* US vs India Regime Alternative Simulation Panel */}
            <Card className="border-primary/20 bg-primary/[0.02]">
                <CardHeader className="pb-3 border-b border-border/50">
                    <CardTitle className="text-sm font-bold flex items-center gap-2">
                        <Globe className="w-4 h-4 text-primary animate-pulse" /> Cross-Border Tax Regime Simulation
                    </CardTitle>
                    <CardDescription>
                        Compare identical trade execution outcomes under standard tax rules side-by-side.
                    </CardDescription>
                </CardHeader>
                <CardContent className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
                    {/* US Regime details */}
                    <div className="space-y-2.5 p-3 rounded-lg border bg-background/50">
                        <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground flex items-center gap-1.5">
                                🇺🇸 United States Rules
                                {activeRegime === "US" && <Badge variant="secondary" className="text-[9px] bg-blue-100 text-blue-700">Active</Badge>}
                            </span>
                            <span className="font-mono font-bold text-base text-foreground">
                                {formatCurrency(simulatedUsTax, baseCurrency)}
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Applies a blended rate of <strong className="text-foreground">30.0%</strong> on short-term gains (held &le; 365 days) and <strong className="text-foreground">15.0%</strong> on long-term capital gains.
                        </p>
                    </div>

                    {/* India Regime details */}
                    <div className="space-y-2.5 p-3 rounded-lg border bg-background/50">
                        <div className="flex items-center justify-between">
                            <span className="font-semibold text-foreground flex items-center gap-1.5">
                                🇮🇳 India Rules (Listed Equity)
                                {activeRegime === "INDIA" && <Badge variant="secondary" className="text-[9px] bg-blue-100 text-blue-700">Active</Badge>}
                            </span>
                            <span className="font-mono font-bold text-base text-foreground">
                                {formatCurrency(simulatedInTax, baseCurrency)}
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Applies <strong className="text-foreground">20.0%</strong> on short-term gains (held &le; 365 days) and <strong className="text-foreground">12.5%</strong> on long-term listed equity capital gains (effective post-July 2024).
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* Badges buckets */}
            <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Active Buckets:</span>
                {Object.entries(by_bucket_tax_due_base).map(([bucket, amount]) => (
                    <Badge variant="outline" key={bucket} className="font-mono text-xs py-1 px-2.5">
                        <span className="font-medium opacity-75 mr-2">{bucket}:</span>
                        <span className={amount > 0 ? "text-destructive font-semibold" : ""}>{formatCurrency(amount, baseCurrency)}</span>
                    </Badge>
                ))}
            </div>

            {/* Taxable events list */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-sm font-semibold">Taxable Ledger events</CardTitle>
                    <CardDescription>FIFO matching events recorded during rebalancing trades.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border overflow-hidden">
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow className="bg-muted/55">
                                        <TableHead className="w-[120px]">Date</TableHead>
                                        <TableHead>Symbol</TableHead>
                                        <TableHead className="text-right">Qty</TableHead>
                                        <TableHead className="text-right">Realized PnL</TableHead>
                                        <TableHead className="text-right">Holding (Days)</TableHead>
                                        <TableHead>Classification</TableHead>
                                        <TableHead className="text-right">Rate</TableHead>
                                        <TableHead className="text-right border-l font-semibold bg-destructive/5 text-destructive dark:text-red-400">Tax Due</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {sortedEvents.map((evt, idx) => (
                                        <TableRow key={`${evt.date}-${evt.symbol}-${idx}`} className="text-xs">
                                            <TableCell className="font-mono text-[10px] text-muted-foreground whitespace-nowrap">{evt.date.split("T")[0]}</TableCell>
                                            <TableCell className="font-bold">{evt.symbol}</TableCell>
                                            <TableCell className="text-right font-mono">{evt.quantity.toLocaleString()}</TableCell>
                                            <TableCell className={`text-right font-mono font-medium ${evt.realized_pnl_base >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600"}`}>
                                                {formatCurrency(evt.realized_pnl_base, baseCurrency)}
                                            </TableCell>
                                            <TableCell className="text-right font-mono opacity-80">{evt.holding_period_days}</TableCell>
                                            <TableCell>
                                                <Badge variant="secondary" className="text-[9px] uppercase font-mono tracking-wider opacity-90 py-0.5 bg-muted/40">
                                                    {evt.bucket.endsWith("_ST") ? "Short Term" : "Long Term"} ({evt.bucket})
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-right font-mono opacity-70">{(evt.tax_rate * 100).toFixed(1)}%</TableCell>
                                            <TableCell className="text-right font-mono font-bold border-l bg-destructive/5 text-destructive dark:text-red-400">
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
