import { RunHeader } from "@/components/run/RunHeader"
import { KPIGrid } from "@/components/run/KPIGrid"
import { PerformanceChart } from "@/components/run/PerformanceChart"
import { InspectorPanel } from "@/components/run/InspectorPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { getRun } from "@/lib/api"

export default async function RunDashboardPage({ params }: { params: { runId: string } }) {
    const runData = await getRun(params.runId);

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
                            <PerformanceChart data={runData.equity} />
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
