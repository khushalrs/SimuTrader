"use client"

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import { TrendingUp, BarChart2, Zap, ArrowRight, Layers, Activity } from "lucide-react"
import Link from "next/link"

const presets = [
    {
        id: "buy-hold-us",
        title: "Buy & Hold — US Mega Cap",
        universe: "S&P 500 Top 50",
        behavior: "Passive indexing with quarterly rebalancing.",
        icon: TrendingUp,
        color: "text-blue-500",
    },
    {
        id: "equal-weight-in",
        title: "Equal Weight — India Top 10",
        universe: "NIFTY 50 Top 10",
        behavior: "Contrarian rebalancing to equal weights.",
        icon: Layers,
        color: "text-orange-500",
    },
    {
        id: "momentum",
        title: "Momentum — Top K Monthly",
        universe: "Nasdaq 100",
        behavior: "Aggressive rotation into winners.",
        icon: Zap,
        color: "text-yellow-500",
    },
    {
        id: "mean-reversion",
        title: "Mean Reversion — Conservative",
        universe: "Russell 2000",
        behavior: "Buying dips, selling rips.",
        icon: Activity,
        color: "text-green-500",
    },
]

export default function PlaygroundPage() {
    return (
        <main className="container py-12">
            <div className="mb-8">
                <h1 className="text-3xl font-bold tracking-tight">Playground</h1>
                <p className="text-muted-foreground mt-2">
                    Select a preset strategy to run a simulation instantly. No configuration required.
                </p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {presets.map((preset, index) => (
                    <motion.div
                        key={preset.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: index * 0.1 }}
                    >
                        <Card className="h-full flex flex-col hover:border-primary/50 transition-colors">
                            <CardHeader>
                                <div className={`mb-2 w-10 h-10 rounded-lg bg-muted flex items-center justify-center ${preset.color}`}>
                                    <preset.icon className="w-6 h-6" />
                                </div>
                                <CardTitle>{preset.title}</CardTitle>
                                <CardDescription>{preset.universe}</CardDescription>
                            </CardHeader>
                            <CardContent className="flex-1">
                                <p className="text-sm text-muted-foreground">{preset.behavior}</p>
                            </CardContent>
                            <CardFooter className="flex justify-between gap-2">
                                <Button variant="outline" className="w-full">View Config</Button>
                                <Button className="w-full" asChild>
                                    <Link href={`/runs/mock-${preset.id}`}>
                                        Run <ArrowRight className="ml-2 h-4 w-4" />
                                    </Link>
                                </Button>
                            </CardFooter>
                        </Card>
                    </motion.div>
                ))}
            </div>
        </main>
    )
}
