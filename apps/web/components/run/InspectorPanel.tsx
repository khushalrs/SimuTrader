"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { formatCurrency } from "@/lib/utils"
import { useEffect, useState } from "react"
import useSWR from "swr"
import { RunPositionOut, getRunTopHoldings, RunFillOut } from "@/lib/api"
import { WhyThisTradePanel } from "./WhyThisTradePanel"
import { Layers, HelpCircle } from "lucide-react"

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
    selectedFill?: RunFillOut | null;
    onClearSelectedFill?: () => void;
}

export function InspectorPanel({
    runId,
    status,
    date,
    equity,
    baseCurrency = "USD",
    selectedFill,
    onClearSelectedFill
}: InspectorPanelProps) {
    const [viewMode, setViewMode] = useState<"holdings" | "trade">("holdings")
    const debouncedDate = useDebounce(date, 200);

    const { data: topHoldings, isLoading } = useSWR(
        status === "SUCCEEDED" ? `/runs/${runId}/top-holdings?limit=5` : null,
        () => getRunTopHoldings(runId, 5),
        { revalidateOnFocus: false }
    );
    const holdings = topHoldings || [];

    // Switch to trade view automatically if selectedFill arrives
    useEffect(() => {
        if (selectedFill) {
            setViewMode("trade")
        }
    }, [selectedFill])

    return (
        <Card className="col-span-1 h-full border-l-4 border-l-primary/20 flex flex-col justify-between">
            <div>
                <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
                    <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">Inspector</CardTitle>
                    <div className="flex items-center gap-1">
                        <Button
                            variant={viewMode === "holdings" ? "secondary" : "ghost"}
                            size="sm"
                            className="h-6 px-2 text-[10px] gap-1"
                            onClick={() => setViewMode("holdings")}
                        >
                            <Layers className="w-3 h-3" /> Holdings
                        </Button>
                        <Button
                            variant={viewMode === "trade" ? "secondary" : "ghost"}
                            size="sm"
                            className="h-6 px-2 text-[10px] gap-1"
                            onClick={() => setViewMode("trade")}
                        >
                            <HelpCircle className="w-3 h-3" /> Why Trade?
                        </Button>
                    </div>
                </CardHeader>

                <CardContent className="pt-2">
                    {viewMode === "trade" || selectedFill ? (
                        <div className="space-y-3">
                            <WhyThisTradePanel fill={selectedFill} baseCurrency={baseCurrency} />
                            {selectedFill && onClearSelectedFill && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="w-full text-xs text-muted-foreground hover:text-foreground h-7"
                                    onClick={onClearSelectedFill}
                                >
                                    Clear Selected Fill
                                </Button>
                            )}
                        </div>
                    ) : (
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
                                    <span className="text-xs text-muted-foreground block font-semibold uppercase">Top Holdings</span>
                                    <div className="space-y-2 text-sm">
                                        {holdings.map(pos => (
                                            <div key={pos.symbol} className="flex justify-between items-center">
                                                <span className="font-medium">{pos.symbol}</span>
                                                <span className="text-muted-foreground font-mono">
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
                    )}
                </CardContent>
            </div>
        </Card>
    )
}
