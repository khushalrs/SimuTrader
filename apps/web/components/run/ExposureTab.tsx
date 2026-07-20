"use client"

import useSWR from "swr"
import { getRunExposure, type RunExposureBreakdown } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ChartFrame, CHART_THEME } from "./ChartFrame"
import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from "recharts"
import { ShieldAlert } from "lucide-react"

const COLOR_PALETTE = [
    "#3b82f6", // blue
    "#10b981", // emerald
    "#f59e0b", // amber
    "#8b5cf6", // violet
    "#ec4899", // pink
    "#06b6d4", // cyan
    "#f43f5e", // rose
]

export function ExposureTab({ runId }: { runId: string }) {
    const { data: exposureData, isLoading, error } = useSWR(
        runId ? `/runs/${runId}/exposure` : null,
        () => getRunExposure(runId),
        { revalidateOnFocus: false }
    )

    if (isLoading) {
        return (
            <div className="space-y-6 animate-pulse">
                <Skeleton className="h-64 w-full rounded-xl" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Skeleton className="h-64 w-full rounded-xl" />
                    <Skeleton className="h-64 w-full rounded-xl" />
                </div>
            </div>
        )
    }

    if (error || !exposureData || exposureData.length === 0) {
        return (
            <Card className="min-h-[300px] flex flex-col items-center justify-center p-8 text-center border-dashed">
                <ShieldAlert className="w-12 h-12 text-muted-foreground/30 mb-3" />
                <h3 className="font-semibold text-lg">No Exposure Data Available</h3>
                <p className="text-sm text-muted-foreground mt-1 max-w-md">
                    Exposure breakdowns over time could not be retrieved for this simulation.
                </p>
            </Card>
        )
    }

    const timeSeries = exposureData
    
    // Extract unique currencies
    const currencyKeys = Array.from(
        new Set(
            timeSeries.flatMap((d) => Object.keys(d.exposure_base_by_currency || {}))
        )
    )

    // Flat data for Recharts stacked area
    const areaChartData = timeSeries.map((d) => {
        const flat: Record<string, any> = { date: d.date.split("T")[0] }
        const nav = d.long_base + d.short_base
        currencyKeys.forEach(curr => {
            const b = d.exposure_base_by_currency?.[curr]
            flat[curr] = b && nav > 0 ? b.net_base / nav : 0
        })
        return flat
    })

    // Latest state
    const latestPoint = timeSeries[timeSeries.length - 1]
    const nav = latestPoint.long_base + latestPoint.short_base
    const currentLeverage = latestPoint.leverage ?? (nav > 0 ? latestPoint.gross_base / nav : 1.0)
    const netExposureVal = nav > 0 ? latestPoint.net_base / nav : 1.0
    const grossExposureVal = nav > 0 ? latestPoint.gross_base / nav : 1.0

    // Country & Asset Class Breakdown lists (weights relative to NAV)
    const countries = Object.entries(latestPoint.by_country || {}).map(([name, breakdown]) => {
        const b = breakdown as RunExposureBreakdown
        const weight = nav > 0 ? (b.net_base / nav) * 100 : 0
        return { name, value: weight }
    }).sort((a, b) => b.value - a.value)

    const assets = Object.entries(latestPoint.by_asset_class || {}).map(([name, breakdown]) => {
        const b = breakdown as RunExposureBreakdown
        const weight = nav > 0 ? (b.net_base / nav) * 100 : 0
        return { name, value: weight }
    }).sort((a, b) => b.value - a.value)

    // Normalize timeSeries for line chart
    const lineChartData = timeSeries.map((d) => {
        const ptNav = d.long_base + d.short_base
        return {
            date: d.date.split("T")[0],
            gross_exposure: ptNav > 0 ? d.gross_base / ptNav : 0,
            net_exposure: ptNav > 0 ? d.net_base / ptNav : 0,
            leverage: d.leverage ?? 1
        }
    })

    return (
        <div className="space-y-6">
            {/* Top Stat Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Current Leverage</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-primary">
                            {currentLeverage.toFixed(2)}x
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Total assets / Net Asset Value.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Net Exposure</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-foreground">
                            {(netExposureVal * 100).toFixed(1)}%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Long minus short position weights.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Gross Exposure</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-foreground">
                            {(grossExposureVal * 100).toFixed(1)}%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Sum of absolute position weights.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Primary Currency</CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-center justify-between">
                        <div className="text-2xl font-bold font-mono text-foreground uppercase">
                            {currencyKeys[0] || "USD"}
                        </div>
                        <Badge className="bg-primary/10 text-primary border-none">FX</Badge>
                    </CardContent>
                </Card>
            </div>

            {/* Stacked Area Currency Exposure Over Time */}
            {currencyKeys.length > 0 && (
                <ChartFrame title="Currency Exposure Over Time" description="Stacked currency asset allocation (weights in base currency terms) over the backtest timeline.">
                    <div className="h-[300px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={areaChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                <XAxis
                                    dataKey="date"
                                    {...CHART_THEME.axis}
                                />
                                <YAxis
                                    {...CHART_THEME.axis}
                                    tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                                    width={45}
                                />
                                <CartesianGrid {...CHART_THEME.grid} />
                                <Tooltip
                                    contentStyle={CHART_THEME.tooltip.contentStyle}
                                    itemStyle={CHART_THEME.tooltip.itemStyle}
                                    formatter={((value: any, name?: string) => [`${(parseFloat(value) * 100).toFixed(2)}%`, name || ""]) as any}
                                />
                                <Legend />
                                {currencyKeys.map((curr, idx) => (
                                    <Area
                                        key={curr}
                                        type="monotone"
                                        dataKey={curr}
                                        stackId="1"
                                        stroke={COLOR_PALETTE[idx % COLOR_PALETTE.length]}
                                        fill={COLOR_PALETTE[idx % COLOR_PALETTE.length]}
                                        fillOpacity={0.6}
                                    />
                                ))}
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </ChartFrame>
            )}

            {/* Leverage & Net/Gross Exposure Line Chart */}
            <ChartFrame title="Leverage & Net/Gross Exposures" description="Historical timeline of gross exposure, net exposure, and active strategy leverage.">
                <div className="h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={lineChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <XAxis
                                dataKey="date"
                                {...CHART_THEME.axis}
                            />
                            <YAxis
                                yAxisId="weight"
                                {...CHART_THEME.axis}
                                tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                                width={50}
                            />
                            <YAxis
                                yAxisId="lev"
                                orientation="right"
                                {...CHART_THEME.axis}
                                tickFormatter={(val) => `${val}x`}
                                width={40}
                            />
                            <CartesianGrid {...CHART_THEME.grid} />
                            <Tooltip
                                contentStyle={CHART_THEME.tooltip.contentStyle}
                                itemStyle={CHART_THEME.tooltip.itemStyle}
                                formatter={((value: any, name?: string) => {
                                    if (name === "gross_exposure") return [`${(value * 100).toFixed(1)}%`, "Gross Exposure"]
                                    if (name === "net_exposure") return [`${(value * 100).toFixed(1)}%`, "Net Exposure"]
                                    return [`${value.toFixed(2)}x`, "Leverage"]
                                }) as any}
                            />
                            <Legend />
                            <Line yAxisId="weight" type="monotone" dataKey="gross_exposure" name="Gross Exposure" stroke="#3b82f6" strokeWidth={2} dot={false} />
                            <Line yAxisId="weight" type="monotone" dataKey="net_exposure" name="Net Exposure" stroke="#10b981" strokeWidth={2} dot={false} />
                            <Line yAxisId="lev" type="monotone" dataKey="leverage" name="Leverage" stroke="#f59e0b" strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </ChartFrame>

            {/* Country and Asset Breakdown Grids */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Asset Class Allocation */}
                <ChartFrame title="Asset Class Breakdown" description="Distribution of portfolio weights across asset classes.">
                    <div className="h-[250px] w-full">
                        {assets.length === 0 ? (
                            <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
                                No asset class breakdowns.
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={assets} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                                    <XAxis type="number" {...CHART_THEME.axis} tickFormatter={(val) => `${val}%`} />
                                    <YAxis dataKey="name" type="category" {...CHART_THEME.axis} width={80} />
                                    <CartesianGrid {...CHART_THEME.grid} />
                                    <Tooltip
                                        contentStyle={CHART_THEME.tooltip.contentStyle}
                                        itemStyle={CHART_THEME.tooltip.itemStyle}
                                        formatter={(value: any) => [`${parseFloat(value).toFixed(2)}%`, 'Weight']}
                                    />
                                    <Bar dataKey="value" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </ChartFrame>

                {/* Country Allocation */}
                <ChartFrame title="Country Allocation" description="Geographical distribution of assets.">
                    <div className="h-[250px] w-full">
                        {countries.length === 0 ? (
                            <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
                                No geographical country breakdowns.
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={countries} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                                    <XAxis type="number" {...CHART_THEME.axis} tickFormatter={(val) => `${val}%`} />
                                    <YAxis dataKey="name" type="category" {...CHART_THEME.axis} width={80} />
                                    <CartesianGrid {...CHART_THEME.grid} />
                                    <Tooltip
                                        contentStyle={CHART_THEME.tooltip.contentStyle}
                                        itemStyle={CHART_THEME.tooltip.itemStyle}
                                        formatter={(value: any) => [`${parseFloat(value).toFixed(2)}%`, 'Weight']}
                                    />
                                    <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </ChartFrame>
            </div>
        </div>
    )
}
