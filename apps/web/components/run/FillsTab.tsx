"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { RunFillOut, getRunFills } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
import useSWRInfinite from "swr/infinite"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"

interface FillsTabProps {
    runId: string
    status?: string
    baseCurrency?: string
}

const LIMIT = 100

export function FillsTab({ runId, status, baseCurrency = "USD" }: FillsTabProps) {
    const isSucceeded = status === "SUCCEEDED"

    const getKey = (pageIndex: number, previousPageData: RunFillOut[] | null) => {
        if (!isSucceeded) return null
        if (previousPageData && !previousPageData.length) return null // reached the end
        return `/api/fills?runId=${runId}&limit=${LIMIT}&offset=${pageIndex * LIMIT}`
    }

    const fetcher = (url: string) => {
        const urlParams = new URL(`http://localhost${url}`).searchParams
        const limitParam = Number(urlParams.get("limit"))
        const offsetParam = Number(urlParams.get("offset"))
        return getRunFills(runId, undefined, undefined, limitParam, offsetParam)
    }

    const { data, size, setSize, isLoading, isValidating } = useSWRInfinite<RunFillOut[]>(getKey, fetcher, {
        revalidateOnFocus: false,
        revalidateFirstPage: false
    })

    const allFills = data ? data.flat() : []
    const isLoadingMore = isLoading || (size > 0 && data && typeof data[size - 1] === "undefined")
    const isEmpty = data?.[0]?.length === 0
    const isReachingEnd = isEmpty || (data && data[data.length - 1]?.length < LIMIT)

    return (
        <Card className="col-span-1 md:col-span-2 min-h-[450px]">
            <CardHeader>
                <CardTitle>Trade Fills</CardTitle>
                <CardDescription>
                    History of all execution events for this simulation.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-muted text-muted-foreground border-b border-border">
                            <tr>
                                <th className="px-4 py-3 font-medium">Date</th>
                                <th className="px-4 py-3 font-medium">Symbol</th>
                                <th className="px-4 py-3 font-medium text-right">Side</th>
                                <th className="px-4 py-3 font-medium text-right">Qty</th>
                                <th className="px-4 py-3 font-medium text-right">Price</th>
                                <th className="px-4 py-3 font-medium text-right">Notional</th>
                                <th className="px-4 py-3 font-medium text-right">Commission</th>
                            </tr>
                        </thead>
                        <tbody>
                            {!data && isLoading ? (
                                <tr>
                                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                                        <Loader2 className="w-5 h-5 animate-spin mx-auto" />
                                    </td>
                                </tr>
                            ) : isEmpty ? (
                                <tr>
                                    <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                                        No fills generated for this run.
                                    </td>
                                </tr>
                            ) : (
                                allFills.map((fill, index) => (
                                    <tr key={`${fill.symbol}-${fill.date}-${index}`} className="border-b transition-colors hover:bg-muted/50">
                                        <td className="px-4 py-3 whitespace-nowrap">{new Date(fill.date).toLocaleString()}</td>
                                        <td className="px-4 py-3 font-medium">{fill.symbol}</td>
                                        <td className={`px-4 py-3 text-right font-medium ${fill.side === "BUY" ? "text-green-500" : "text-red-500"}`}>
                                            {fill.side || "N/A"}
                                        </td>
                                        <td className="px-4 py-3 text-right">{fill.qty.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-right">
                                            {formatCurrency(fill.price, baseCurrency)}
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            {formatCurrency(fill.notional, baseCurrency)}
                                        </td>
                                        <td className="px-4 py-3 text-right text-muted-foreground">
                                            {formatCurrency(fill.commission, baseCurrency)}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                
                {data && !isEmpty && !isReachingEnd && (
                    <div className="mt-4 flex justify-center pb-4">
                        <Button
                            variant="outline"
                            onClick={() => setSize(size + 1)}
                            disabled={isLoadingMore}
                        >
                            {isLoadingMore ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Loading...
                                </>
                            ) : (
                                "Load More"
                            )}
                        </Button>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
