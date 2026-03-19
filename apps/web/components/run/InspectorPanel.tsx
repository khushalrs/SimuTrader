"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatCurrency } from "@/lib/utils"
import { useEffect, useState } from "react"
import useSWR from "swr"
import { RunPositionOut, getRunPositions } from "@/lib/api"

export function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value);
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);
        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);
    return debouncedValue;
}

interface InspectorPanelProps {
    runId: string;
    status?: string;
    date?: string;
    equity?: number;
    baseCurrency?: string;
}

export function InspectorPanel({ runId, status, date, equity, baseCurrency }: InspectorPanelProps) {
    const debouncedDate = useDebounce(date, 200);
    const { data: topHoldings, isLoading } = useSWR(
        status === "SUCCEEDED" ? `/runs/${runId}/positions?date=${debouncedDate}&limit=5` : null,
        () => getRunPositions(runId, debouncedDate, 5),
        { revalidateOnFocus: false }
    );
    const holdings = topHoldings || [];

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

                    {(!isLoading && holdings.length > 0) && (
                        <div className="space-y-2 pt-4 border-t">
                            <span className="text-xs text-muted-foreground block">Top Holdings</span>
                            <div className="space-y-2 text-sm">
                                {holdings.map(pos => (
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
