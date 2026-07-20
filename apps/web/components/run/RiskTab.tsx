"use client"

import { useMemo } from "react"
import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { RunEquityPoint } from "@/lib/api"
import { ChartFrame, CHART_THEME } from "./ChartFrame"
import { ShieldAlert, TrendingUp, TrendingDown, Percent, Award, AlertTriangle, Scale } from "lucide-react"

interface RiskTabProps {
    equity?: RunEquityPoint[]
}

export function RiskTab({ equity }: RiskTabProps) {
    const calculatedMetrics = useMemo(() => {
        if (!equity || equity.length === 0) return null

        // 1. Prepare Daily Returns
        const dailyReturns: { date: string; ret: number }[] = []
        for (let i = 1; i < equity.length; i++) {
            const prev = equity[i - 1].value
            const curr = equity[i].value
            if (prev > 0) {
                dailyReturns.push({
                    date: equity[i].date,
                    ret: (curr - prev) / prev
                })
            }
        }

        if (dailyReturns.length === 0) return null

        // 2. Win Rate
        const positiveDays = dailyReturns.filter(d => d.ret > 0).length
        const winRate = positiveDays / dailyReturns.length

        // 3. Best / Worst Day
        const bestDay = Math.max(...dailyReturns.map(d => d.ret))
        const worstDay = Math.min(...dailyReturns.map(d => d.ret))

        // 4. VaR / CVaR (95%)
        const sortedReturns = [...dailyReturns].sort((a, b) => a.ret - b.ret)
        const varIndex = Math.floor(sortedReturns.length * 0.05)
        const var95 = sortedReturns[varIndex]?.ret || 0
        const worstReturns = sortedReturns.slice(0, Math.max(1, varIndex))
        const sumWorst = worstReturns.reduce((sum, d) => sum + d.ret, 0)
        const cvar95 = sumWorst / worstReturns.length

        // 5. Sortino Ratio
        const meanReturn = dailyReturns.reduce((sum, d) => sum + d.ret, 0) / dailyReturns.length
        const negativeReturns = dailyReturns.filter(d => d.ret < 0).map(d => Math.pow(d.ret, 2))
        const downsideVariance = negativeReturns.length > 0 
            ? negativeReturns.reduce((sum, v) => sum + v, 0) / dailyReturns.length 
            : 0
        const downsideDeviation = Math.sqrt(downsideVariance)
        const sortino = downsideDeviation > 0 ? (meanReturn / downsideDeviation) * Math.sqrt(252) : 0

        // 6. Calmar Ratio
        const maxDrawdown = Math.max(...equity.map(e => Math.abs(e.drawdown || 0)))
        let calmar = 0
        if (equity.length > 1 && maxDrawdown > 0) {
            const startVal = equity[0].value
            const endVal = equity[equity.length - 1].value
            const totalReturn = (endVal - startVal) / startVal
            const startDate = new Date(equity[0].date)
            const endDate = new Date(equity[equity.length - 1].date)
            const diffYears = Math.max(0.1, (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24 * 365.25))
            const cagr = Math.pow(totalReturn + 1, 1 / diffYears) - 1
            calmar = cagr / maxDrawdown
        }

        // 7. Longest Drawdown Duration (Days)
        let maxDrawdownDurationDays = 0
        let currentDrawdownStart: Date | null = null
        equity.forEach(pt => {
            const dd = pt.drawdown || 0
            if (dd < -0.0001) {
                if (!currentDrawdownStart) {
                    currentDrawdownStart = new Date(pt.date)
                } else {
                    const diffTime = Math.abs(new Date(pt.date).getTime() - currentDrawdownStart.getTime())
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
                    if (diffDays > maxDrawdownDurationDays) {
                        maxDrawdownDurationDays = diffDays
                    }
                }
            } else {
                currentDrawdownStart = null
            }
        })

        // 8. Histogram Bins
        const numBins = 20
        let bins: { binStart: number; binEnd: number; count: number; label: string }[] = []
        if (sortedReturns.length > 0) {
            const minRet = sortedReturns[0].ret
            const maxRet = sortedReturns[sortedReturns.length - 1].ret
            if (maxRet === minRet) {
                bins = [{ binStart: minRet - 0.01, binEnd: minRet + 0.01, count: sortedReturns.length, label: `${(minRet * 100).toFixed(1)}%` }]
            } else {
                const binSize = (maxRet - minRet) / numBins
                bins = Array.from({ length: numBins }, (_, i) => ({
                    binStart: minRet + i * binSize,
                    binEnd: minRet + (i + 1) * binSize,
                    count: 0,
                    label: `${((minRet + (i + 0.5) * binSize) * 100).toFixed(1)}%`
                }))
                dailyReturns.forEach(d => {
                    let binIndex = Math.floor((d.ret - minRet) / binSize)
                    if (binIndex >= numBins) binIndex = numBins - 1
                    if (binIndex < 0) binIndex = 0
                    bins[binIndex].count += 1
                })
            }
        }

        // 9. Rolling Metrics
        const rollingData: { date: string; vol30?: number; sharpe90?: number }[] = []
        for (let i = 0; i < dailyReturns.length; i++) {
            const date = dailyReturns[i].date.split("T")[0]
            let vol30: number | undefined = undefined
            let sharpe90: number | undefined = undefined

            // 30d rolling vol
            if (i >= 29) {
                const windowReturns = dailyReturns.slice(i - 29, i + 1).map(d => d.ret)
                const mean = windowReturns.reduce((s, r) => s + r, 0) / 30
                const variance = windowReturns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / 29
                vol30 = Math.sqrt(variance) * Math.sqrt(252)
            }

            // 90d rolling Sharpe
            if (i >= 89) {
                const windowReturns = dailyReturns.slice(i - 89, i + 1).map(d => d.ret)
                const mean = windowReturns.reduce((s, r) => s + r, 0) / 90
                const std = Math.sqrt(windowReturns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / 89)
                sharpe90 = std > 0 ? (mean / std) * Math.sqrt(252) : 0
            }

            if (vol30 !== undefined || sharpe90 !== undefined) {
                rollingData.push({ date, vol30, sharpe90 })
            }
        }

        return {
            winRate,
            bestDay,
            worstDay,
            var95,
            cvar95,
            sortino,
            calmar,
            maxDrawdownDurationDays,
            bins,
            rollingData
        }
    }, [equity])

    if (!equity || equity.length === 0 || !calculatedMetrics) {
        return <div className="p-4 text-center text-muted-foreground">No data available for risk analysis</div>
    }

    const {
        winRate,
        bestDay,
        worstDay,
        var95,
        cvar95,
        sortino,
        calmar,
        maxDrawdownDurationDays,
        bins,
        rollingData
    } = calculatedMetrics

    return (
        <div className="space-y-6">
            {/* Risk Stat Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Value at Risk (95% VaR)</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-rose-500">
                            {(var95 * 100).toFixed(2)}%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">95% threshold of worst daily loss.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Expected Shortfall (CVaR)</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-rose-600">
                            {(cvar95 * 100).toFixed(2)}%
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Average return of worst 5% days.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Sortino Ratio</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                            {sortino.toFixed(2)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">Return relative to downside volatility.</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardDescription className="text-xs uppercase font-semibold">Calmar Ratio</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold font-mono text-primary">
                            {calmar.toFixed(2)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">CAGR relative to Max Drawdown.</p>
                    </CardContent>
                </Card>
            </div>

            {/* Next Grid: Extremes & Win Rate */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="pt-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs uppercase text-muted-foreground font-semibold">Win Rate</p>
                            <h4 className="text-lg font-bold font-mono text-foreground mt-1">{(winRate * 100).toFixed(1)}%</h4>
                        </div>
                        <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-none">Win %</Badge>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs uppercase text-muted-foreground font-semibold">Best Day</p>
                            <h4 className="text-lg font-bold font-mono text-emerald-600 mt-1">{(bestDay * 100).toFixed(2)}%</h4>
                        </div>
                        <TrendingUp className="w-5 h-5 text-emerald-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs uppercase text-muted-foreground font-semibold">Worst Day</p>
                            <h4 className="text-lg font-bold font-mono text-rose-500 mt-1">{(worstDay * 100).toFixed(2)}%</h4>
                        </div>
                        <TrendingDown className="w-5 h-5 text-rose-500" />
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="pt-4 flex items-center justify-between">
                        <div>
                            <p className="text-xs uppercase text-muted-foreground font-semibold">Max DD Duration</p>
                            <h4 className="text-lg font-bold font-mono text-foreground mt-1">{maxDrawdownDurationDays} Days</h4>
                        </div>
                        <Badge variant="outline" className="text-amber-600 border-amber-500/30">Drawdown</Badge>
                    </CardContent>
                </Card>
            </div>

            {/* Underwater Drawdown Chart */}
            <ChartFrame title="Underwater Drawdown" description="Peak-to-trough decline (drawdown curve) over the backtest duration.">
                <div className="h-[250px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={equity} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="hsl(var(--destructive))" stopOpacity={0.4} />
                                    <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <XAxis
                                dataKey="date"
                                {...CHART_THEME.axis}
                                tickFormatter={(val) => {
                                    const d = new Date(val)
                                    return !isNaN(d.getTime()) ? d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }) : val
                                }}
                            />
                            <YAxis
                                {...CHART_THEME.axis}
                                tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                width={60}
                            />
                            <CartesianGrid {...CHART_THEME.grid} />
                            <Tooltip
                                contentStyle={CHART_THEME.tooltip.contentStyle}
                                itemStyle={CHART_THEME.tooltip.itemStyle}
                                formatter={(value: any) => [`${(value * 100).toFixed(2)}%`, 'Drawdown']}
                                labelFormatter={(label) => new Date(label).toLocaleDateString()}
                            />
                            <Area
                                type="stepAfter"
                                dataKey="drawdown"
                                stroke="hsl(var(--destructive))"
                                fillOpacity={1}
                                fill="url(#colorDrawdown)"
                                strokeWidth={1.5}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </ChartFrame>

            {/* Returns Distribution Histogram */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <ChartFrame title="Daily Returns Distribution" description="Frequency histogram of daily returns across the simulation.">
                    <div className="h-[250px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={bins} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                <XAxis
                                    dataKey="label"
                                    {...CHART_THEME.axis}
                                />
                                <YAxis
                                    {...CHART_THEME.axis}
                                    width={40}
                                />
                                <CartesianGrid {...CHART_THEME.grid} />
                                <Tooltip
                                    contentStyle={CHART_THEME.tooltip.contentStyle}
                                    itemStyle={CHART_THEME.tooltip.itemStyle}
                                    formatter={(value: any) => [value, 'Days']}
                                />
                                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </ChartFrame>

                {/* Rolling Risk Metrics Chart */}
                <ChartFrame title="Rolling Risk Metrics" description="Rolling 30d annualized volatility and rolling 90d Sharpe ratio.">
                    <div className="h-[250px] w-full">
                        {rollingData.length === 0 ? (
                            <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
                                Not enough historical data to compute rolling metrics.
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={rollingData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                    <XAxis
                                        dataKey="date"
                                        {...CHART_THEME.axis}
                                        tickFormatter={(val) => {
                                            const d = new Date(val)
                                            return !isNaN(d.getTime()) ? d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }) : val
                                        }}
                                    />
                                    <YAxis
                                        yAxisId="vol"
                                        {...CHART_THEME.axis}
                                        tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                                        width={50}
                                    />
                                    <YAxis
                                        yAxisId="sharpe"
                                        orientation="right"
                                        {...CHART_THEME.axis}
                                        width={40}
                                    />
                                    <CartesianGrid {...CHART_THEME.grid} />
                                    <Tooltip
                                        contentStyle={CHART_THEME.tooltip.contentStyle}
                                        itemStyle={CHART_THEME.tooltip.itemStyle}
                                        formatter={(value: any, name: string) => {
                                            if (name === "vol30") return [`${(value * 100).toFixed(2)}%`, "30d Volatility"];
                                            return [value.toFixed(2), "90d Sharpe Ratio"];
                                        }}
                                    />
                                    <Line
                                        yAxisId="vol"
                                        type="monotone"
                                        dataKey="vol30"
                                        stroke="hsl(var(--destructive))"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                    <Line
                                        yAxisId="sharpe"
                                        type="monotone"
                                        dataKey="sharpe90"
                                        stroke="hsl(var(--primary))"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </ChartFrame>
            </div>
        </div>
    )
}
