import { RunHeader } from "@/components/run/RunHeader"
import { KPIGrid } from "@/components/run/KPIGrid"
import { PerformanceChart } from "@/components/run/PerformanceChart"
import { InspectorPanel } from "@/components/run/InspectorPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { RiskTab } from "@/components/run/RiskTab"
import { CostsTab } from "@/components/run/CostsTab"
import { PortfolioTab } from "@/components/run/PortfolioTab"
import { ConfigTab } from "@/components/run/ConfigTab"
import { getRun } from "@/lib/api"

export default async function RunDashboardPage({ params }: { params: { runId: string } }) {
    const runData = await getRun(params.runId);

    const equityData = runData?.equity || [];
    const latestPoint = equityData.length > 0 ? equityData[equityData.length - 1] : null;
    const inspectorDate = latestPoint ? latestPoint.date : undefined;
    const inspectorEquity = latestPoint ? latestPoint.value : undefined;

    if (!runData) {
        // Fallback UI or 404
        return (
            <main className="container py-8">
                <div className="text-center">
                    <h1 className="text-2xl font-bold">Run Not Found</h1>
                    <p className="text-muted-foreground">Could not fetch data for run: {params.runId}</p>
                    <p className="text-xs text-muted-foreground mt-2">Ensure backend is running on http://localhost:8000</p>
                </div>
            </main>
        );
    }

    return (
        <main className="container py-8 space-y-8">
            <RunHeader
                runId={runData.id}
                title={runData.title}
                date={runData.date}
                tags={runData.tags}
                requestedStart={runData.requested_start_date}
                requestedEnd={runData.requested_end_date}
                effectiveStart={runData.effective_start_date}
                effectiveEnd={runData.effective_end_date}
            />

            <KPIGrid metrics={runData.metrics} />

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
                            <PerformanceChart data={runData.equity} baseCurrency={runData.baseCurrency} />
                        </TabsContent>
                        <TabsContent value="risk" className="mt-0 min-h-[450px]">
                            <RiskTab equity={runData.equity} />
                        </TabsContent>
                        <TabsContent value="costs" className="mt-0 min-h-[450px]">
                            <CostsTab data={runData} />
                        </TabsContent>
                        <TabsContent value="portfolio" className="mt-0 min-h-[450px]">
                            <PortfolioTab equity={runData.equity} baseCurrency={runData.baseCurrency} />
                        </TabsContent>
                        <TabsContent value="configuration" className="mt-0 min-h-[450px]">
                            <ConfigTab data={runData} />
                        </TabsContent>
                    </Tabs>
                </div>

                <div className="hidden lg:block lg:col-span-1 h-full">
                    <InspectorPanel date={inspectorDate} equity={inspectorEquity} baseCurrency={runData.baseCurrency} />
                </div>
            </div>
        </main>
    )
}
