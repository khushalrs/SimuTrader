"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { motion } from "framer-motion"
import { TrendingUp, Activity, BarChart2, Zap } from "lucide-react"

const stories = [
    {
        title: "Same decade, different worlds",
        description: "US vs India Equities",
        icon: TrendingUp,
        insight: "See how emerging markets decoupled in 2023.",
        details: "Interactive chart showing normalized comparison of S&P 500 vs NIFTY 50 over the last 10 years."
    },
    {
        title: "FX regimes",
        description: "USD/JPY Volatility",
        icon: Activity,
        insight: "When carry trades unwind.",
        details: "Analyzing the impact of interest rate differentials on currency pairs."
    },
    {
        title: "Correlation breaks",
        description: "Tech vs Energy",
        icon: Zap,
        insight: "Diversification fails when everything falls.",
        details: "Rolling correlation analysis showing periods of stress where correlations converge to 1."
    },
    {
        title: "Volatility story",
        description: "VIX Term Structure",
        icon: BarChart2,
        insight: "Fear is not constant.",
        details: "Visualizing the term structure of volatility during market crashes."
    },
]

export function MarketStories() {
    return (
        <section className="container py-24">
            <div className="mb-12 text-center">
                <h2 className="text-3xl font-bold tracking-tight sm:text-4xl text-foreground">Market Stories</h2>
                <p className="mt-4 text-lg text-muted-foreground">Real market phenomena, visualized.</p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                {stories.map((story, index) => (
                    <Dialog key={story.title}>
                        <DialogTrigger asChild>
                            <div className="cursor-pointer">
                                <motion.div
                                    whileHover={{ scale: 1.05 }}
                                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                                >
                                    <Card className="h-full transition-shadow hover:shadow-lg">
                                        <CardHeader>
                                            <story.icon className="h-8 w-8 text-primary mb-2" />
                                            <CardTitle className="text-xl">{story.title}</CardTitle>
                                            <CardDescription>{story.description}</CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-sm text-muted-foreground">{story.insight}</p>
                                            <div className="mt-4 h-24 rounded-md bg-muted/50 flex items-center justify-center text-xs text-muted-foreground">
                                                Mini Chart Preview
                                            </div>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            </div>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[800px] h-[80vh] flex flex-col">
                            <DialogHeader>
                                <DialogTitle>{story.title}</DialogTitle>
                                <DialogDescription>{story.description} - {story.insight}</DialogDescription>
                            </DialogHeader>
                            <div className="flex-1 bg-muted/30 rounded-md border flex items-center justify-center p-4">
                                {/* This would be the full interactive ModalChartLab */}
                                <div className="text-center space-y-2">
                                    <BarChart2 className="h-16 w-16 mx-auto text-muted-foreground/50" />
                                    <p className="text-muted-foreground">{story.details}</p>
                                    <p className="text-xs text-muted-foreground">(Interactive details chart placeholder)</p>
                                </div>
                            </div>
                        </DialogContent>
                    </Dialog>
                ))}
            </div>
        </section>
    )
}
