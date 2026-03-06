"use client"

import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PerformanceChart } from "@/components/run/PerformanceChart"
import { RiskTab } from "@/components/run/RiskTab"
import { CostsTab } from "@/components/run/CostsTab"
import { PortfolioTab } from "@/components/run/PortfolioTab"
import { ConfigTab } from "@/components/run/ConfigTab"
import { InspectorPanel } from "@/components/run/InspectorPanel"
import { RunData } from "@/lib/api"

export function RunDashboardClient({ runData }: { runData: RunData }) {
    const equityData = runData?.equity || [];
    const latestPoint = equityData.length > 0 ? equityData[equityData.length - 1] : null;

    const [hoveredPoint, setHoveredPoint] = useState<{ date: string; value: number } | null>(null);

    const inspectorDate = hoveredPoint ? hoveredPoint.date : (latestPoint ? latestPoint.date : undefined);
    const inspectorEquity = hoveredPoint ? hoveredPoint.value : (latestPoint ? latestPoint.value : undefined);

    return (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-[500px] pb-10">
            <div className="lg:col-span-3 space-y-4">
                <Tabs defaultValue="performance" className="w-full">
                    <div className="flex items-center justify-between mb-4">
                        <TabsList>
                            <TabsTrigger value="performance">Performance</TabsTrigger>
                            <TabsTrigger value="risk">Risk</TabsTrigger>
                            <TabsTrigger value="costs">Costs</TabsTrigger>
                            <TabsTrigger value="portfolio">Portfolio</TabsTrigger>
                            <TabsTrigger value="configuration">Configuration</TabsTrigger>
                        </TabsList>
                    </div>

                    <TabsContent value="performance" className="mt-0 min-h-[450px]">
                        <PerformanceChart
                            data={runData.equity}
                            baseCurrency={runData.baseCurrency}
                            onHover={setHoveredPoint}
                        />
                    </TabsContent>
                    <TabsContent value="risk" className="mt-0 min-h-[450px]">
                        <RiskTab equity={runData.equity} />
                    </TabsContent>
                    <TabsContent value="costs" className="mt-0 min-h-[450px]">
                        <CostsTab data={runData} status={runData.status} />
                    </TabsContent>
                    <TabsContent value="portfolio" className="mt-0 min-h-[450px]">
                        <PortfolioTab runId={runData.id} equity={runData.equity} baseCurrency={runData.baseCurrency} status={runData.status} />
                    </TabsContent>
                    <TabsContent value="configuration" className="mt-0 min-h-[450px]">
                        <ConfigTab data={runData} />
                    </TabsContent>
                </Tabs>
            </div>

            <div className="hidden lg:block lg:col-span-1 h-full">
                <InspectorPanel
                    runId={runData.id}
                    date={inspectorDate}
                    equity={inspectorEquity}
                    baseCurrency={runData.baseCurrency}
                    status={runData.status}
                />
            </div>
        </div>
    )
}
