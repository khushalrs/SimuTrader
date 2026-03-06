"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatCurrency } from "@/lib/utils"
import { useEffect, useState } from "react"
import { RunPositionOut, getRunPositions } from "@/lib/api"

interface InspectorPanelProps {
    runId: string;
    status?: string;
    date?: string;
    equity?: number;
    baseCurrency?: string;
}

export function InspectorPanel({ runId, status, date, equity, baseCurrency }: InspectorPanelProps) {
    const [topHoldings, setTopHoldings] = useState<RunPositionOut[]>([])
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        setIsLoading(true)
        getRunPositions(runId, date)
            .then(data => {
                // sort by market_value_base descending, take top 5
                const sorted = [...data].sort((a, b) => b.market_value_base - a.market_value_base).slice(0, 5)
                setTopHoldings(sorted)
            })
            .catch(err => console.error(err))
            .finally(() => setIsLoading(false))
    }, [runId, status, date])

    return (
        <Card className="col-span-1 h-full border-l-4 border-l-primary/20">
            <CardHeader>
                <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">Inspector</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-6">
                    <div className="space-y-1">
                        <span className="text-xs text-muted-foreground">Date</span>
                        <div className="font-mono text-lg font-medium">{date || "N/A"}</div>
                    </div>

                    <div className="space-y-1">
                        <span className="text-xs text-muted-foreground">Equity</span>
                        <div className="text-2xl font-bold">
                            {equity !== undefined ? formatCurrency(equity, baseCurrency) : "N/A"}
                        </div>
                    </div>

                    {(!isLoading && topHoldings.length > 0) && (
                        <div className="space-y-2 pt-4 border-t">
                            <span className="text-xs text-muted-foreground block">Top Holdings</span>
                            <div className="space-y-2 text-sm">
                                {topHoldings.map(pos => (
                                    <div key={pos.symbol} className="flex justify-between items-center">
                                        <span className="font-medium">{pos.symbol}</span>
                                        <span className="text-muted-foreground">
                                            {pos.weight !== undefined && pos.weight !== null
                                                ? `${(pos.weight * 100).toFixed(1)}%`
                                                : formatCurrency(pos.market_value_base, baseCurrency)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
