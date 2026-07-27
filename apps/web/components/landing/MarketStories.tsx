"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { TrendingUp, Activity, BarChart2, Zap, ArrowRight, Sparkles, Scale, AlertCircle } from "lucide-react"
import {
    AreaChart,
    Area,
    LineChart,
    Line,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    CartesianGrid,
    Legend,
    ReferenceLine
} from "recharts"

// --- Datasets for Market Stories ---

const usVsIndiaData = [
    { year: "2018", spy: 100, nifty: 100 },
    { year: "2019", spy: 128, nifty: 114 },
    { year: "2020", spy: 148, nifty: 129 },
    { year: "2021", spy: 187, nifty: 161 },
    { year: "2022", spy: 153, nifty: 168 },
    { year: "2023", spy: 191, nifty: 202 },
    { year: "2024", spy: 234, nifty: 245 },
]

const usjpyData = [
    { date: "Jan", rate: 130.2, vol: 11.2, carryYield: 4.5 },
    { date: "Mar", rate: 134.5, vol: 12.8, carryYield: 4.8 },
    { date: "May", rate: 139.8, vol: 10.4, carryYield: 5.0 },
    { date: "Jul", rate: 144.1, vol: 14.1, carryYield: 5.2 },
    { date: "Sep", rate: 149.3, vol: 15.6, carryYield: 5.3 },
    { date: "Nov", rate: 151.7, vol: 13.2, carryYield: 5.4 },
    { date: "Dec (Unwind)", rate: 141.5, vol: 24.5, carryYield: 4.9 },
]

const correlationData = [
    { month: "M1", correlation: -0.15, stress: 0, xlk: 102, xle: 98 },
    { month: "M2", correlation: 0.05, stress: 0, xlk: 105, xle: 101 },
    { month: "M3", correlation: -0.22, stress: 0, xlk: 109, xle: 95 },
    { month: "M4", correlation: 0.12, stress: 0, xlk: 112, xle: 104 },
    { month: "M5 (Crash)", correlation: 0.88, stress: 1, xlk: 88, xle: 84 },
    { month: "M6", correlation: 0.94, stress: 1, xlk: 82, xle: 79 },
    { month: "M7", correlation: 0.35, stress: 0, xlk: 95, xle: 92 },
    { month: "M8", correlation: 0.08, stress: 0, xlk: 104, xle: 99 },
]

const vixTermStructureData = [
    { maturity: "M1", contango: 13.5, backwardation: 38.5 },
    { maturity: "M2", contango: 14.8, backwardation: 32.1 },
    { maturity: "M3", contango: 15.9, backwardation: 27.8 },
    { maturity: "M4", contango: 16.7, backwardation: 25.2 },
    { maturity: "M5", contango: 17.4, backwardation: 23.4 },
    { maturity: "M6", contango: 18.0, backwardation: 22.1 },
    { maturity: "M7", contango: 18.5, backwardation: 21.3 },
    { maturity: "M8", contango: 18.9, backwardation: 20.8 },
]

export function MarketStories() {
    const [mounted, setMounted] = useState(false)
    const [activeVixTab, setActiveVixTab] = useState<"contango" | "backwardation">("contango")

    useEffect(() => {
        setMounted(true)
    }, [])

    return (
        <section className="container py-24 border-b">
            <div className="mb-12 text-center">
                <Badge variant="outline" className="mb-3 px-3 py-1 text-xs">
                    <Sparkles className="w-3.5 h-3.5 mr-1 text-primary" /> Visual Insights
                </Badge>
                <h2 className="text-3xl font-bold tracking-tight sm:text-4xl text-foreground">Market Stories</h2>
                <p className="mt-4 text-lg text-muted-foreground">Real market phenomena, interactive previews.</p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">

                {/* --- STORY 1: US vs India Equities --- */}
                <Dialog>
                    <DialogTrigger asChild>
                        <div className="cursor-pointer group">
                            <div className="transition-transform duration-300 group-hover:-translate-y-1 h-full">
                                <Card className="h-full border-border/60 transition-all group-hover:border-primary/50 group-hover:shadow-md flex flex-col justify-between">
                                    <CardHeader className="pb-2">
                                        <TrendingUp className="h-7 w-7 text-blue-500 mb-2" />
                                        <CardTitle className="text-lg">Same decade, different worlds</CardTitle>
                                        <CardDescription>US vs India Equities</CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <p className="text-xs text-muted-foreground line-clamp-2">
                                            See how emerging markets decoupled with +245% gains.
                                        </p>
                                        {/* Mini Chart Preview */}
                                        <div className="h-24 w-full rounded-md bg-muted/30 p-1 border">
                                            {mounted && (
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <LineChart data={usVsIndiaData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                                                        <Line type="monotone" dataKey="spy" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={true} />
                                                        <Line type="monotone" dataKey="nifty" stroke="#f97316" strokeWidth={2} dot={false} isAnimationActive={true} />
                                                    </LineChart>
                                                </ResponsiveContainer>
                                            )}
                                        </div>
                                        <div className="flex justify-between items-center text-xs text-muted-foreground pt-1">
                                            <span className="flex items-center gap-1 font-medium text-blue-500">● S&P 500</span>
                                            <span className="flex items-center gap-1 font-medium text-orange-500">● NIFTY 50</span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </DialogTrigger>

                    <DialogContent className="sm:max-w-[750px] max-h-[90vh] flex flex-col overflow-y-auto">
                        <DialogHeader>
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary">Equities</Badge>
                                <Badge variant="outline">Cross-Border FX</Badge>
                            </div>
                            <DialogTitle className="text-2xl mt-1">Same decade, different worlds: US vs India</DialogTitle>
                            <DialogDescription>
                                Historical normalized performance (Base = 100 in 2018). India&apos;s NIFTY 50 outperformed S&P 500 driven by earnings growth and currency movements.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="my-4 space-y-4">
                            <div className="h-[280px] w-full bg-muted/20 p-4 rounded-xl border">
                                {mounted && (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={usVsIndiaData}>
                                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                            <XAxis dataKey="year" />
                                            <YAxis domain={['dataMin - 10', 'dataMax + 10']} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: "hsl(var(--background))", borderRadius: "8px", borderColor: "hsl(var(--border))" }}
                                                formatter={(val: any) => [`${val} (Indexed)`, "Value"]}
                                            />
                                            <Legend />
                                            <Line type="monotone" name="S&P 500 (US)" dataKey="spy" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4 }} />
                                            <Line type="monotone" name="NIFTY 50 (India)" dataKey="nifty" stroke="#f97316" strokeWidth={3} dot={{ r: 4 }} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                )}
                            </div>

                            <div className="grid grid-cols-3 gap-3 text-center">
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">NIFTY 50 CAGR</span>
                                    <span className="text-lg font-bold text-orange-500">+16.1% / yr</span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">S&P 500 CAGR</span>
                                    <span className="text-lg font-bold text-blue-500">+15.2% / yr</span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">SimuTrader Friction</span>
                                    <span className="text-sm font-semibold text-foreground">Tax & INR FX Hedging</span>
                                </div>
                            </div>

                            <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs text-muted-foreground flex gap-2.5 items-start">
                                <Scale className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">SimuTrader Realism Model:</strong> Backtests automatically incorporate withholding tax rates for cross-border investments and currency exchange rate drift between USD and INR.
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 pt-2 border-t">
                            <Button asChild>
                                <Link href="/playground">
                                    Run Demo Strategy in Playground <ArrowRight className="ml-1.5 h-4 w-4" />
                                </Link>
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>


                {/* --- STORY 2: FX Regimes --- */}
                <Dialog>
                    <DialogTrigger asChild>
                        <div className="cursor-pointer group">
                            <div className="transition-transform duration-300 group-hover:-translate-y-1 h-full">
                                <Card className="h-full border-border/60 transition-all group-hover:border-primary/50 group-hover:shadow-md flex flex-col justify-between">
                                    <CardHeader className="pb-2">
                                        <Activity className="h-7 w-7 text-emerald-500 mb-2" />
                                        <CardTitle className="text-lg">FX Regimes</CardTitle>
                                        <CardDescription>USD/JPY Carry & Volatility</CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <p className="text-xs text-muted-foreground line-clamp-2">
                                            When rate differentials collapse and carry trades unwind.
                                        </p>
                                        {/* Mini Chart Preview */}
                                        <div className="h-24 w-full rounded-md bg-muted/30 p-1 border">
                                            {mounted && (
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <AreaChart data={usjpyData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                                                        <defs>
                                                            <linearGradient id="fxMiniGrad" x1="0" y1="0" x2="0" y2="1">
                                                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                                                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                                            </linearGradient>
                                                        </defs>
                                                        <Area type="monotone" dataKey="rate" stroke="#10b981" fill="url(#fxMiniGrad)" strokeWidth={2} isAnimationActive={true} />
                                                    </AreaChart>
                                                </ResponsiveContainer>
                                            )}
                                        </div>
                                        <div className="flex justify-between items-center text-xs text-muted-foreground pt-1">
                                            <span className="font-medium">Spot: 151.7 → 141.5</span>
                                            <span className="text-emerald-500 font-medium">Vol Spike: 24.5%</span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </DialogTrigger>

                    <DialogContent className="sm:max-w-[750px] max-h-[90vh] flex flex-col overflow-y-auto">
                        <DialogHeader>
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary">Foreign Exchange</Badge>
                                <Badge variant="outline">Yield Carry</Badge>
                            </div>
                            <DialogTitle className="text-2xl mt-1">FX Regimes: USD/JPY Carry Trade Unwind</DialogTitle>
                            <DialogDescription>
                                Interest rate differentials created high yield carry, until central bank policy shifts triggered violent rapid unwinds.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="my-4 space-y-4">
                            <div className="h-[280px] w-full bg-muted/20 p-4 rounded-xl border">
                                {mounted && (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={usjpyData}>
                                            <defs>
                                                <linearGradient id="fxFullGrad" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                            <XAxis dataKey="date" />
                                            <YAxis domain={['dataMin - 5', 'dataMax + 5']} />
                                            <Tooltip contentStyle={{ backgroundColor: "hsl(var(--background))", borderRadius: "8px", borderColor: "hsl(var(--border))" }} />
                                            <Legend />
                                            <Area type="monotone" name="USD/JPY Exchange Rate" dataKey="rate" stroke="#10b981" fill="url(#fxFullGrad)" strokeWidth={3} />
                                            <Line type="monotone" name="Realized Volatility (%)" dataKey="vol" stroke="#ef4444" strokeWidth={2.5} strokeDasharray="4 4" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                )}
                            </div>

                            <div className="grid grid-cols-3 gap-3 text-center">
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">Peak Yield Spread</span>
                                    <span className="text-lg font-bold text-emerald-500">5.40% p.a.</span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">Unwind Drawdown</span>
                                    <span className="text-lg font-bold text-red-500">-6.7% in 5 Days</span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">SimuTrader Friction</span>
                                    <span className="text-sm font-semibold text-foreground">Overnight Carry Rates</span>
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 pt-2 border-t">
                            <Button asChild>
                                <Link href="/playground">
                                    Test Carry Strategy in Playground <ArrowRight className="ml-1.5 h-4 w-4" />
                                </Link>
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>


                {/* --- STORY 3: Correlation Breaks --- */}
                <Dialog>
                    <DialogTrigger asChild>
                        <div className="cursor-pointer group">
                            <div className="transition-transform duration-300 group-hover:-translate-y-1 h-full">
                                <Card className="h-full border-border/60 transition-all group-hover:border-primary/50 group-hover:shadow-md flex flex-col justify-between">
                                    <CardHeader className="pb-2">
                                        <Zap className="h-7 w-7 text-purple-500 mb-2" />
                                        <CardTitle className="text-lg">Correlation breaks</CardTitle>
                                        <CardDescription>Tech (XLK) vs Energy (XLE)</CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <p className="text-xs text-muted-foreground line-clamp-2">
                                            Diversification fails when everything falls simultaneously.
                                        </p>
                                        {/* Mini Chart Preview */}
                                        <div className="h-24 w-full rounded-md bg-muted/30 p-1 border">
                                            {mounted && (
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <AreaChart data={correlationData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                                                        <defs>
                                                            <linearGradient id="corrGrad" x1="0" y1="0" x2="0" y2="1">
                                                                <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4} />
                                                                <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                                                            </linearGradient>
                                                        </defs>
                                                        <ReferenceLine y={0.7} stroke="#ef4444" strokeDasharray="2 2" />
                                                        <Area type="monotone" dataKey="correlation" stroke="#a855f7" fill="url(#corrGrad)" strokeWidth={2} isAnimationActive={true} />
                                                    </AreaChart>
                                                </ResponsiveContainer>
                                            )}
                                        </div>
                                        <div className="flex justify-between items-center text-xs text-muted-foreground pt-1">
                                            <span className="font-medium">Normal: -0.15</span>
                                            <span className="text-purple-500 font-medium">Stress Peak: +0.94</span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </DialogTrigger>

                    <DialogContent className="sm:max-w-[750px] max-h-[90vh] flex flex-col overflow-y-auto">
                        <DialogHeader>
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary">Risk & Correlation</Badge>
                                <Badge variant="outline">Portfolio Stress</Badge>
                            </div>
                            <DialogTitle className="text-2xl mt-1">Correlation Breaks: Tech vs Energy Breakdown</DialogTitle>
                            <DialogDescription>
                                Rolling 30-day correlation spikes towards +1.0 during market crashes, causing multi-asset portfolio diversification benefits to vanish when needed most.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="my-4 space-y-4">
                            <div className="h-[280px] w-full bg-muted/20 p-4 rounded-xl border">
                                {mounted && (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={correlationData}>
                                            <defs>
                                                <linearGradient id="corrFullGrad" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4} />
                                                    <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                            <XAxis dataKey="month" />
                                            <YAxis domain={[-0.4, 1.0]} />
                                            <Tooltip contentStyle={{ backgroundColor: "hsl(var(--background))", borderRadius: "8px", borderColor: "hsl(var(--border))" }} />
                                            <Legend />
                                            <ReferenceLine y={0.7} label={{ value: "Stress Limit (0.7)", fill: "#ef4444", fontSize: 11 }} stroke="#ef4444" strokeDasharray="3 3" />
                                            <Area type="monotone" name="Rolling 30D Correlation" dataKey="correlation" stroke="#a855f7" fill="url(#corrFullGrad)" strokeWidth={3} />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                )}
                            </div>

                            <div className="grid grid-cols-3 gap-3 text-center">
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">Calm Regime Correlation</span>
                                    <span className="text-lg font-bold text-foreground">-0.15 (Uncorrelated)</span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">Crisis Regime Correlation</span>
                                    <span className="text-lg font-bold text-red-500">+0.94 (Converged)</span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">SimuTrader Friction</span>
                                    <span className="text-sm font-semibold text-foreground">Regime-Based Covariance</span>
                                </div>
                            </div>

                            <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20 text-xs text-muted-foreground flex gap-2.5 items-start">
                                <AlertCircle className="w-4 h-4 text-purple-500 shrink-0 mt-0.5" />
                                <div>
                                    <strong className="text-foreground">Risk Insight:</strong> Simple mean-variance backtests assume constant correlations. SimuTrader tests your strategy against liquidity stress windows where assets fall together.
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 pt-2 border-t">
                            <Button asChild>
                                <Link href="/build_page">
                                    Build Risk-Managed Strategy <ArrowRight className="ml-1.5 h-4 w-4" />
                                </Link>
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>


                {/* --- STORY 4: Volatility Story --- */}
                <Dialog>
                    <DialogTrigger asChild>
                        <div className="cursor-pointer group">
                            <div className="transition-transform duration-300 group-hover:-translate-y-1 h-full">
                                <Card className="h-full border-border/60 transition-all group-hover:border-primary/50 group-hover:shadow-md flex flex-col justify-between">
                                    <CardHeader className="pb-2">
                                        <BarChart2 className="h-7 w-7 text-amber-500 mb-2" />
                                        <CardTitle className="text-lg">Volatility story</CardTitle>
                                        <CardDescription>VIX Term Structure</CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <p className="text-xs text-muted-foreground line-clamp-2">
                                            Contango vs panic inversion in futures curves.
                                        </p>
                                        {/* Mini Chart Preview */}
                                        <div className="h-24 w-full rounded-md bg-muted/30 p-1 border">
                                            {mounted && (
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <BarChart data={vixTermStructureData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                                                        <Bar dataKey="contango" fill="#3b82f6" radius={[2, 2, 0, 0]} isAnimationActive={true} />
                                                        <Bar dataKey="backwardation" fill="#ef4444" radius={[2, 2, 0, 0]} isAnimationActive={true} />
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            )}
                                        </div>
                                        <div className="flex justify-between items-center text-xs text-muted-foreground pt-1">
                                            <span className="flex items-center gap-1 font-medium text-blue-500">● Contango</span>
                                            <span className="flex items-center gap-1 font-medium text-red-500">● Inverted</span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        </div>
                    </DialogTrigger>

                    <DialogContent className="sm:max-w-[750px] max-h-[90vh] flex flex-col overflow-y-auto">
                        <DialogHeader>
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary">Volatility</Badge>
                                <Badge variant="outline">Futures Roll Yield</Badge>
                            </div>
                            <DialogTitle className="text-2xl mt-1">Volatility Story: VIX Term Structure Shifts</DialogTitle>
                            <DialogDescription>
                                VIX futures spend ~85% of time in upward-sloping Contango (causing roll yield drag), but violently invert into Backwardation during market selloffs.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="my-4 space-y-4">
                            <Tabs value={activeVixTab} onValueChange={(v: any) => setActiveVixTab(v)} className="w-full">
                                <TabsList className="grid grid-cols-2 w-full max-w-xs mx-auto mb-4">
                                    <TabsTrigger value="contango">Normal (Contango)</TabsTrigger>
                                    <TabsTrigger value="backwardation">Panic (Backwardation)</TabsTrigger>
                                </TabsList>

                                <div className="h-[260px] w-full bg-muted/20 p-4 rounded-xl border">
                                    {mounted && (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={vixTermStructureData}>
                                                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                                <XAxis dataKey="maturity" />
                                                <YAxis domain={[0, 45]} />
                                                <Tooltip contentStyle={{ backgroundColor: "hsl(var(--background))", borderRadius: "8px", borderColor: "hsl(var(--border))" }} />
                                                <Legend />
                                                {activeVixTab === "contango" ? (
                                                    <Bar name="Contango Curve (Normal)" dataKey="contango" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                                ) : (
                                                    <Bar name="Backwardation Curve (Spike)" dataKey="backwardation" fill="#ef4444" radius={[4, 4, 0, 0]} />
                                                )}
                                            </BarChart>
                                        </ResponsiveContainer>
                                    )}
                                </div>
                            </Tabs>

                            <div className="grid grid-cols-3 gap-3 text-center">
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">Front Month VIX (M1)</span>
                                    <span className="text-lg font-bold text-foreground">
                                        {activeVixTab === "contango" ? "13.5 pts" : "38.5 pts"}
                                    </span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">Roll Cost Impact</span>
                                    <span className="text-lg font-bold text-amber-500">
                                        {activeVixTab === "contango" ? "-1.2% / month" : "+4.8% / month"}
                                    </span>
                                </div>
                                <div className="p-3 rounded-lg bg-muted/40 border">
                                    <span className="text-xs text-muted-foreground block">SimuTrader Friction</span>
                                    <span className="text-sm font-semibold text-foreground">Futures Expiry & Carry</span>
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 pt-2 border-t">
                            <Button asChild>
                                <Link href="/playground">
                                    Explore Volatility Demos in Playground <ArrowRight className="ml-1.5 h-4 w-4" />
                                </Link>
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>

            </div>
        </section>
    )
}

