"use client"

import { RunHeader } from "@/components/run/RunHeader"
import { KPIGrid } from "@/components/run/KPIGrid"
import { PerformanceChart } from "@/components/run/PerformanceChart"
import { InspectorPanel } from "@/components/run/InspectorPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function RunDashboardPage({ params }: { params: { runId: string } }) {
    // Mock data - in real app would fetch based on params.runId
    const mockRuns: Record<string, any> = {
        "mock-buy-hold-us": {
            id: "buy-hold-us",
            title: "Buy & Hold — US Mega Cap",
            date: "Ran on Mar 10, 2024 at 09:00",
            tags: ["Passive", "US Equity", "Quarterly Rebalance"],
            metrics: [
                { label: "Total Return", value: "+12.4%", change: "Benchmark", trend: "up" },
                { label: "Sharpe Ratio", value: "0.85", change: "Market aligned", trend: "neutral" },
                { label: "Max Drawdown", value: "-18.2%", change: "Standard", trend: "down" },
                { label: "Win Rate", value: "N/A", trend: "neutral" },
            ]
        },
        "mock-equal-weight-in": {
            id: "equal-weight-in",
            title: "Equal Weight — India Top 10",
            date: "Ran on Mar 11, 2024 at 10:30",
            tags: ["Smart Beta", "India Equity", "Monthly Rebalance"],
            metrics: [
                { label: "Total Return", value: "+22.1%", change: "+5.4% vs NIFTY", trend: "up" },
                { label: "Sharpe Ratio", value: "1.12", change: "Top 20%", trend: "up" },
                { label: "Max Drawdown", value: "-15.5%", change: "Moderate", trend: "neutral" },
                { label: "Win Rate", value: "62%", trend: "up" },
            ]
        },
        "mock-momentum": {
            id: "momentum",
            title: "Momentum — Top K Monthly",
            date: "Ran on Mar 10, 2024 at 14:30",
            tags: ["Momentum", "US Equity", "Monthly Rebalance"],
            metrics: [
                { label: "Total Return", value: "+18.5%", change: "+2.3% vs SPY", trend: "up" },
                { label: "Sharpe Ratio", value: "1.45", change: "Top 5%", trend: "up" },
                { label: "Max Drawdown", value: "-12.4%", change: "Within limits", trend: "neutral" },
                { label: "Win Rate", value: "58%", trend: "up" },
            ]
        },
        "mock-mean-reversion": {
            id: "mean-reversion",
            title: "Mean Reversion — Conservative",
            date: "Ran on Mar 12, 2024 at 11:15",
            tags: ["Mean Reversion", "Small Cap", "Daily Rebalance"],
            metrics: [
                { label: "Total Return", value: "+8.2%", change: "Volatile", trend: "neutral" },
                { label: "Sharpe Ratio", value: "0.65", change: "High Risk", trend: "down" },
                { label: "Max Drawdown", value: "-24.0%", change: "High", trend: "down" },
                { label: "Win Rate", value: "65%", trend: "up" },
            ]
        }
    }

    // Fallback to momentum if ID not found, but try to find strict match first
    const runData = mockRuns[params.runId] || mockRuns["mock-momentum"]

    return (
        <main className="container py-8 space-y-8">
            <RunHeader
                runId={runData.id}
                title={runData.title}
                date={runData.date}
                tags={runData.tags}
            />

            <KPIGrid metrics={runData.metrics} />

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[500px]">
                <div className="lg:col-span-3 space-y-4">
                    <Tabs defaultValue="performance" className="w-full">
                        <div className="flex items-center justify-between mb-4">
                            <TabsList>
                                <TabsTrigger value="performance">Performance</TabsTrigger>
                                <TabsTrigger value="risk" disabled>Risk</TabsTrigger>
                                <TabsTrigger value="costs" disabled>Costs</TabsTrigger>
                                <TabsTrigger value="portfolio" disabled>Portfolio</TabsTrigger>
                            </TabsList>
                        </div>

                        <TabsContent value="performance" className="mt-0 h-[450px]">
                            <PerformanceChart />
                        </TabsContent>
                    </Tabs>
                </div>

                <div className="hidden lg:block lg:col-span-1 h-full">
                    <InspectorPanel />
                </div>
            </div>
        </main>
    )
}
