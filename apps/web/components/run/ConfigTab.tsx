"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { RunData } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"

interface ConfigTabProps {
    data: RunData
}

export function ConfigTab({ data }: ConfigTabProps) {
    const config = data.config_snapshot || {};

    // Safe extraction of top level config boundaries
    const backtest = config.backtest || {};

    // Hyperparameters mapping
    const params = config.strategy_params || {};
    const strategyType = config.strategy || 'N/A';

    // Universe might be an array of objects like [{ symbol: "AAPL" }, { symbol: "MSFT" }] or direct strings.
    const rawUniverse = config.universe?.instruments || config.universe || [];
    const universe = Array.isArray(rawUniverse) ? rawUniverse.map((i: any) => typeof i === "object" ? i.symbol : i).filter(Boolean) : [];

    const baseCurrency = data.baseCurrency || 'USD';
    const initialCash = backtest.initial_cash || 0;
    const startDate = backtest.start_date || 'N/A';
    const endDate = backtest.end_date || 'N/A';

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                    <CardHeader>
                        <CardTitle>Strategy Parameters</CardTitle>
                        <CardDescription>Hyperparameters passed to the core engine.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-2 text-sm border-b pb-2">
                                <span className="text-muted-foreground font-medium">Strategy Type</span>
                                <span className="font-mono">{strategyType}</span>
                            </div>
                            {Object.entries(params).length > 0 ? (
                                Object.entries(params).map(([key, value]) => (
                                    <div key={key} className="grid grid-cols-2 gap-2 text-sm border-b pb-2 last:border-0 last:pb-0">
                                        <span className="text-muted-foreground font-medium">{key}</span>
                                        <span className="font-mono">{JSON.stringify(value)}</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-sm text-muted-foreground italic">No parameters provided.</div>
                            )}
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Backtest Environment</CardTitle>
                        <CardDescription>Capital, timeframe, and universe conditions.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-2 text-sm border-b pb-2">
                                <span className="text-muted-foreground font-medium">Universe</span>
                                <span className="font-mono truncate" title={universe.join(', ')}>
                                    {universe.length > 0 ? universe.join(', ') : 'None'}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-sm border-b pb-2">
                                <span className="text-muted-foreground font-medium">Base Currency</span>
                                <span className="font-mono">{baseCurrency}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-sm border-b pb-2">
                                <span className="text-muted-foreground font-medium">Initial Capital</span>
                                <span className="font-mono">{formatCurrency(initialCash, baseCurrency)}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-sm border-b pb-2">
                                <span className="text-muted-foreground font-medium">Start Date</span>
                                <span className="font-mono">{startDate}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                                <span className="text-muted-foreground font-medium">End Date</span>
                                <span className="font-mono">{endDate}</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="col-span-1 md:col-span-2">
                    <CardHeader>
                        <CardTitle>Raw Configuration Rules</CardTitle>
                        <CardDescription>Execution settings and realism overrides.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <pre className="p-4 bg-muted rounded-md text-xs font-mono overflow-auto max-h-[300px]">
                            {JSON.stringify(config, null, 2)}
                        </pre>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
