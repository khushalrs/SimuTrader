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
    onSelectFill?: (fill: RunFillOut) => void
    selectedFillId?: string
}

const LIMIT = 100

export function FillsTab({ runId, status, baseCurrency = "USD", onSelectFill, selectedFillId }: FillsTabProps) {
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
                    History of all execution events for this simulation. Click any row to inspect decision trace.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border overflow-x-auto">
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
                                allFills.map((fill, index) => {
                                    const fillId = fill.id || `${fill.symbol}-${fill.date}-${index}`
                                    const isSelected = selectedFillId === fillId

                                    const formatFillDate = (dateStr: string) => {
                                        const d = new Date(dateStr)
                                        if (isNaN(d.getTime())) return dateStr
                                        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                                            const year = d.getUTCFullYear()
                                            const month = String(d.getUTCMonth() + 1).padStart(2, '0')
                                            const day = String(d.getUTCDate()).padStart(2, '0')
                                            return `${year}-${month}-${day}`
                                        }
                                        const year = d.getUTCFullYear()
                                        const month = String(d.getUTCMonth() + 1).padStart(2, '0')
                                        const day = String(d.getUTCDate()).padStart(2, '0')
                                        const hours = String(d.getUTCHours()).padStart(2, '0')
                                        const minutes = String(d.getUTCMinutes()).padStart(2, '0')
                                        const seconds = String(d.getUTCSeconds()).padStart(2, '0')
                                        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds} UTC`
                                    }

                                    return (
                                        <tr
                                            key={fillId}
                                            className={`border-b transition-colors cursor-pointer ${isSelected ? "bg-primary/15 font-semibold" : "hover:bg-muted/50"}`}
                                            onClick={() => onSelectFill?.(fill)}
                                        >
                                            <td className="px-4 py-3 whitespace-nowrap">{formatFillDate(fill.date)}</td>
                                            <td className="px-4 py-3 font-medium">{fill.symbol}</td>
                                            <td className="px-4 py-3 text-right font-medium">
                                                <span className={`inline-flex rounded px-2 py-0.5 text-xs font-semibold ${fill.side === "BUY" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" :
                                                    fill.side === "FX" ? "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300" :
                                                        "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                                                    }`}>
                                                    {fill.side || "N/A"}
                                                </span>
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
                                    )
                                })
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
                                "Load More Fills"
                            )}
                        </Button>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
