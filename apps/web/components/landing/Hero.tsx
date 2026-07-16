"use client"

import { useState, useEffect } from "react"
import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts"
import { Button } from "@/components/ui/button"

const data = [
    { name: "Mon", value: 100 },
    { name: "Tue", value: 102 },
    { name: "Wed", value: 101 },
    { name: "Thu", value: 104 },
    { name: "Fri", value: 103 },
    { name: "Sat", value: 106 },
    { name: "Sun", value: 108 },
    { name: "Mon2", value: 107 },
    { name: "Tue2", value: 110 },
    { name: "Wed2", value: 112 },
    { name: "Thu2", value: 111 },
    { name: "Fri2", value: 114 },
    { name: "Sat2", value: 116 },
    { name: "Sun2", value: 115 },
]

export function Hero() {
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
    }, [])

    return (
        <section className="relative flex min-h-[80vh] flex-col items-center justify-center overflow-hidden border-b bg-background pt-16">
            <div className="absolute inset-0 z-0 opacity-10">
                {/* Grid or background pattern could go here */}
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
                    <Button size="lg">Run a demo</Button>
                    <Button size="lg" variant="outline">Build a strategy</Button>
                </div>
            </div>

            <div className="relative mt-16 w-full max-w-5xl px-4 lg:px-0">
                {/* Animated Chart Area */}
                <div className="h-[300px] w-full lg:h-[400px]">
                    {mounted && (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data}>
                                <defs>
                                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <YAxis hide domain={['dataMin - 5', 'dataMax + 5']} />
                                <Area
                                    type="monotone"
                                    dataKey="value"
                                    stroke="hsl(var(--primary))"
                                    fillOpacity={1}
                                    fill="url(#colorValue)"
                                    strokeWidth={2}
                                    isAnimationActive={true}
                                    animationDuration={2000}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>
                {/* Overlay controls/chips could go here */}
                <div className="absolute top-4 right-4 flex gap-2">
                    <span className="rounded-full bg-background/50 px-3 py-1 text-xs font-medium backdrop-blur border">US Equity</span>
                    <span className="rounded-full bg-background/50 px-3 py-1 text-xs font-medium backdrop-blur border opacity-50">India Equity</span>
                    <span className="rounded-full bg-background/50 px-3 py-1 text-xs font-medium backdrop-blur border opacity-50">FX</span>
                </div>
            </div>
        </section>
    )
}
