"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
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
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                >
                    <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl">
                        Backtesting that <span className="text-primary">respects reality.</span>
                    </h1>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                >
                    <p className="max-w-[42rem] leading-normal text-muted-foreground sm:text-xl sm:leading-8">
                        Multi-asset simulation with frictions: fees, taxes, and trading calendars.
                        Run strategies across US, India, and FX.
                    </p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="flex gap-4"
                >
                    <Button size="lg">Run a demo</Button>
                    <Button size="lg" variant="outline">Build a strategy</Button>
                </motion.div>
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
