"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Area, AreaChart, ResponsiveContainer, YAxis, XAxis, Tooltip } from "recharts"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const assetDatasets = {
    us: [
        { name: "Jan", value: 100 },
        { name: "Feb", value: 102 },
        { name: "Mar", value: 101 },
        { name: "Apr", value: 105 },
        { name: "May", value: 104 },
        { name: "Jun", value: 108 },
        { name: "Jul", value: 112 },
        { name: "Aug", value: 110 },
        { name: "Sep", value: 115 },
        { name: "Oct", value: 118 },
        { name: "Nov", value: 122 },
        { name: "Dec", value: 125 },
    ],
    india: [
        { name: "Jan", value: 100 },
        { name: "Feb", value: 104 },
        { name: "Mar", value: 103 },
        { name: "Apr", value: 109 },
        { name: "May", value: 112 },
        { name: "Jun", value: 115 },
        { name: "Jul", value: 121 },
        { name: "Aug", value: 119 },
        { name: "Sep", value: 126 },
        { name: "Oct", value: 132 },
        { name: "Nov", value: 138 },
        { name: "Dec", value: 142 },
    ],
    fx: [
        { name: "Jan", value: 100 },
        { name: "Feb", value: 101.5 },
        { name: "Mar", value: 103.0 },
        { name: "Apr", value: 102.2 },
        { name: "May", value: 106.1 },
        { name: "Jun", value: 108.5 },
        { name: "Jul", value: 107.0 },
        { name: "Aug", value: 111.2 },
        { name: "Sep", value: 105.4 },
        { name: "Oct", value: 102.1 },
        { name: "Nov", value: 99.8 },
        { name: "Dec", value: 97.5 },
    ]
}

export function Hero() {
    const [mounted, setMounted] = useState(false)
    const [activeAsset, setActiveAsset] = useState<"us" | "india" | "fx">("us")

    useEffect(() => {
        setMounted(true)
    }, [])

    const activeData = assetDatasets[activeAsset]
    const strokeColor = activeAsset === "us" ? "#3b82f6" : activeAsset === "india" ? "#f97316" : "#10b981"

    return (
        <section className="relative flex min-h-[80vh] flex-col items-center justify-center overflow-hidden border-b bg-background pt-16" data-tour="home-overview">
            <div className="absolute inset-0 z-0 opacity-10">
                {/* Grid pattern background */}
                <div className="h-full w-full bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]" />
            </div>

            <div className="z-10 container flex flex-col items-center gap-6 text-center">
                <div className="anim-fade-slide" style={{ animationDelay: "0ms" }}>
                    <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl">
                        Backtesting that <span className="text-primary">respects reality.</span>
                    </h1>
                </div>

                <div className="anim-fade-slide" style={{ animationDelay: "100ms" }}>
                    <p className="max-w-[42rem] leading-normal text-muted-foreground sm:text-xl sm:leading-8">
                        Multi-asset simulation with frictions: fees, taxes, and trading calendars.
                        Run strategies across US, India, and FX.
                    </p>
                </div>

                <div className="anim-fade-slide flex gap-4" style={{ animationDelay: "200ms" }}>
                    <Button size="lg" asChild>
                        <Link href="/playground">Run a demo</Link>
                    </Button>
                    <Button size="lg" variant="outline" asChild>
                        <Link href="/build_page">Build a strategy</Link>
                    </Button>
                </div>
            </div>

            <div className="relative mt-16 w-full max-w-5xl px-4 lg:px-0">
                {/* Animated Chart Area */}
                <div className="h-[300px] w-full lg:h-[400px]">
                    {mounted && (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={activeData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="heroGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor={strokeColor} stopOpacity={0.35} />
                                        <stop offset="95%" stopColor={strokeColor} stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <YAxis hide domain={['dataMin - 5', 'dataMax + 5']} />
                                <XAxis dataKey="name" hide />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: "hsl(var(--background))",
                                        borderColor: "hsl(var(--border))",
                                        borderRadius: "8px",
                                        fontSize: "12px",
                                    }}
                                    formatter={(val: any) => [`${val} pts`, "Index Level"]}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="value"
                                    stroke={strokeColor}
                                    fillOpacity={1}
                                    fill="url(#heroGradient)"
                                    strokeWidth={2.5}
                                    isAnimationActive={true}
                                    animationDuration={1000}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>
                {/* Overlay controls/chips */}
                <div className="absolute top-4 right-4 flex gap-2 z-20">
                    <button
                        onClick={() => setActiveAsset("us")}
                        className={cn(
                            "rounded-full px-3 py-1 text-xs font-medium backdrop-blur border transition-all cursor-pointer",
                            activeAsset === "us"
                                ? "bg-primary text-primary-foreground border-primary shadow-sm"
                                : "bg-background/50 hover:bg-background/80 text-muted-foreground border-border"
                        )}
                    >
                        US Equity
                    </button>
                    <button
                        onClick={() => setActiveAsset("india")}
                        className={cn(
                            "rounded-full px-3 py-1 text-xs font-medium backdrop-blur border transition-all cursor-pointer",
                            activeAsset === "india"
                                ? "bg-primary text-primary-foreground border-primary shadow-sm"
                                : "bg-background/50 hover:bg-background/80 text-muted-foreground border-border"
                        )}
                    >
                        India Equity
                    </button>
                    <button
                        onClick={() => setActiveAsset("fx")}
                        className={cn(
                            "rounded-full px-3 py-1 text-xs font-medium backdrop-blur border transition-all cursor-pointer",
                            activeAsset === "fx"
                                ? "bg-primary text-primary-foreground border-primary shadow-sm"
                                : "bg-background/50 hover:bg-background/80 text-muted-foreground border-border"
                        )}
                    >
                        FX Carry
                    </button>
                </div>
            </div>
        </section>
    )
}
