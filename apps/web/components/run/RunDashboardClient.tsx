"use client"

import { useState } from "react"
import useSWR from "swr";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PerformanceChart } from "@/components/run/PerformanceChart"
import { RiskTab } from "@/components/run/RiskTab"
import { CostsTab } from "@/components/run/CostsTab"
import { PortfolioTab } from "@/components/run/PortfolioTab"
import { ConfigTab } from "@/components/run/ConfigTab"
import { InspectorPanel } from "@/components/run/InspectorPanel"
import { RunHeader } from "@/components/run/RunHeader"
import { KPIGrid } from "@/components/run/KPIGrid"
import { RunRetryButton } from "@/components/run/RunRetryButton"
import { AlertCircle, Loader2 } from "lucide-react"
import { RunData, getRun, getRunMetrics, getRunEquity } from "@/lib/api"

export function RunDashboardClient({ runId }: { runId: string }) {
    const { data: runDataRaw, isLoading } = useSWR(
        runId ? `/runs/${runId}` : null,
        () => getRun(runId),
        {
            refreshInterval: (data) => {
                if (data?.status === "QUEUED" || data?.status === "RUNNING") return 1000;
                return 0;
            }
        }
    );

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 p-4 rounded-lg border bg-muted/30">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Loading run...</span>
            </div>
        );
    }
    if (!runDataRaw) {
        return (
            <div className="p-4 rounded-lg border border-destructive/20 bg-destructive/10 text-destructive">
                Run not found for this session. If this run was created in another browser/session, open it there.
            </div>
        )
    }

    const runDataSummary = runDataRaw;
    const isSucceeded = runDataSummary.status === "SUCCEEDED";

    const { data: metricsData } = useSWR(
        isSucceeded ? `/runs/${runId}/metrics` : null,
        () => getRunMetrics(runId),
        { revalidateOnFocus: false }
    );

    const { data: equityDataList } = useSWR(
        isSucceeded ? `/runs/${runId}/equity` : null,
        () => getRunEquity(runId),
        { revalidateOnFocus: false }
    );

    const runData: RunData = {
        ...runDataSummary,
        metrics: metricsData?.metrics || runDataSummary.metrics,
        costs: metricsData?.costs || runDataSummary.costs,
        equity: equityDataList || runDataSummary.equity,
        effective_start_date: equityDataList?.[0]?.date || runDataSummary.effective_start_date,
        effective_end_date: equityDataList?.[equityDataList.length - 1]?.date || runDataSummary.effective_end_date,
    };

    const equityData = runData.equity || [];
    const latestPoint = equityData.length > 0 ? equityData[equityData.length - 1] : null;

    const [hoveredPoint, setHoveredPoint] = useState<{ date: string; value: number } | null>(null);

    const inspectorDate = hoveredPoint ? hoveredPoint.date : (latestPoint ? latestPoint.date : undefined);
    const inspectorEquity = hoveredPoint ? hoveredPoint.value : (latestPoint ? latestPoint.value : undefined);

    const getFriendlyErrorMessage = (code?: string | null) => {
        if (!code) return runData.error_message_public || "The simulation failed unexpectedly. Please retry.";
        if (code === "MARKET_DATA_UNAVAILABLE") return "Market data was unavailable for this run.";
        if (code === "NO_TRADING_DAYS") return "No trading days were found in the selected range.";
        return runData.error_message_public || "The simulation failed unexpectedly. Please retry.";
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {runData.status === "QUEUED" || runData.status === "RUNNING" ? (
                <div className="flex items-center gap-2 p-4 bg-primary/10 text-primary border border-primary/20 rounded-lg">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Simulation is {runData.status.toLowerCase()}...</span>
                </div>
            ) : null}

            {runData.status === "FAILED" && (
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-destructive">
                    <div className="flex items-start sm:items-center gap-3">
                        <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 sm:mt-0" />
                        <div>
                            <h3 className="font-semibold">Run Failed</h3>
                            <p className="text-sm opacity-90">
                                {getFriendlyErrorMessage(runData.error_code)}
                            </p>
                            {runData.error_code && (
                                <p className="mt-1 text-[10px] opacity-60 font-mono tracking-tight">
                                    {runData.error_code}
                                    {runData.error_id ? ` | ID: ${runData.error_id}` : ""}
                                </p>
                            )}
                        </div>
                    </div>
                    {runData.error_retryable !== false && (
                        <RunRetryButton config={runData.config_snapshot} />
                    )}
                </div>
            )}

            <RunHeader
                runId={runData.id}
                title={runData.title}
                date={runData.date}
                tags={runData.tags}
                requestedStart={runData.requested_start_date}
                requestedEnd={runData.requested_end_date}
                effectiveStart={runData.effective_start_date}
                effectiveEnd={runData.effective_end_date}
                configSnapshot={runData.config_snapshot}
                equity={runData.equity}
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
        </div>
    )
}
