"use client"

import { useState } from "react"
import useSWR from "swr";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PerformanceChart } from "@/components/run/PerformanceChart"
import { RiskTab } from "@/components/run/RiskTab"
import { CostsTab } from "@/components/run/CostsTab"
import { PortfolioTab } from "@/components/run/PortfolioTab"
import { FillsTab } from "@/components/run/FillsTab"
import { ConfigTab } from "@/components/run/ConfigTab"
import { InspectorPanel } from "@/components/run/InspectorPanel"
import { RunHeader } from "@/components/run/RunHeader"
import { KPIGrid } from "@/components/run/KPIGrid"
import { RunRetryButton } from "@/components/run/RunRetryButton"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, Loader2 } from "lucide-react"
import { RunData, getRun, getRunMetrics, getRunEquity, getRunStatus } from "@/lib/api"

export function RunDashboardClient({ runId }: { runId: string }) {
    const { data: statusData, isLoading: isStatusLoading } = useSWR(
        runId ? `/runs/${runId}/status` : null,
        () => getRunStatus(runId),
        {
            refreshInterval: (data: any) => {
                if (!data) return 1000;
                if (data.status === "QUEUED" || data.status === "RUNNING") return 1000;
                return 0;
            },
            keepPreviousData: true
        }
    );

    const { data: runSummaryData, isLoading: isRunSummaryLoading } = useSWR(
        runId ? `/runs/${runId}` : null,
        () => getRun(runId),
        { revalidateOnFocus: false }
    );

    const isNotFound = (statusData === null && !isStatusLoading) && (runSummaryData === null && !isRunSummaryLoading);
    const isPending = isStatusLoading || isRunSummaryLoading || statusData?.status === "QUEUED" || statusData?.status === "RUNNING";
    const status = statusData?.status || runSummaryData?.status || "QUEUED";
    const isSucceeded = status === "SUCCEEDED";
    const isFailed = status === "FAILED";

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

    const runData: Partial<RunData> = {
        ...(runSummaryData || {}),
        id: runId,
        status: status,
        metrics: metricsData?.metrics || runSummaryData?.metrics || [],
        costs: metricsData?.costs || runSummaryData?.costs,
        equity: equityDataList || runSummaryData?.equity || [],
        error_code: statusData?.error_code || runSummaryData?.error_code,
        error_message_public: statusData?.error_message_public || runSummaryData?.error_message_public,
        error_retryable: statusData?.error_retryable ?? runSummaryData?.error_retryable ?? true,
        error_id: statusData?.error_id || runSummaryData?.error_id,
        effective_start_date: equityDataList?.[0]?.date || runSummaryData?.effective_start_date,
        effective_end_date: equityDataList?.[equityDataList?.length - 1]?.date || runSummaryData?.effective_end_date,
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

    if (isNotFound) {
        return (
            <div className="text-center py-12 animate-in fade-in duration-500">
                <h1 className="text-2xl font-bold">Run Not Found</h1>
                <p className="text-muted-foreground mt-2">Could not fetch data for run: {runId}</p>
                <p className="text-xs text-muted-foreground mt-2">The simulation may have crashed or was purged by the backend engine.</p>
            </div>
        )
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {isPending && (
                <div className="flex items-center gap-2 p-4 bg-primary/10 text-primary border border-primary/20 rounded-lg">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Simulation is {status.toLowerCase()}...</span>
                </div>
            )}

            {isFailed && (
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
                    {runData.error_retryable !== false && runData.config_snapshot && (
                        <RunRetryButton config={runData.config_snapshot} />
                    )}
                </div>
            )}

            {isPending ? (
                <Skeleton className="w-full h-[150px] rounded-lg" />
            ) : (
                <RunHeader
                    runId={runData.id as string}
                    title={runData.title as string}
                    date={runData.date as string}
                    tags={runData.tags as string[]}
                    requestedStart={runData.requested_start_date}
                    requestedEnd={runData.requested_end_date}
                    effectiveStart={runData.effective_start_date}
                    effectiveEnd={runData.effective_end_date}
                    configSnapshot={runData.config_snapshot}
                    equity={runData.equity}
                />
            )}

            {isPending ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-24 w-full rounded-lg" />)}
                </div>
            ) : (
                <KPIGrid metrics={runData.metrics || []} />
            )}

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-[500px] pb-10">
                <div className="lg:col-span-3 space-y-4">
                <Tabs defaultValue="performance" className="w-full">
                    <div className="flex items-center justify-between mb-4">
                        <TabsList>
                            <TabsTrigger value="performance">Performance</TabsTrigger>
                            <TabsTrigger value="risk" disabled={isPending || isFailed}>Risk</TabsTrigger>
                            <TabsTrigger value="costs" disabled={isPending || isFailed}>Costs</TabsTrigger>
                            <TabsTrigger value="portfolio" disabled={isPending || isFailed}>Portfolio</TabsTrigger>
                            <TabsTrigger value="fills" disabled={isPending || isFailed}>Fills</TabsTrigger>
                            <TabsTrigger value="configuration" disabled={isPending}>Configuration</TabsTrigger>
                        </TabsList>
                    </div>

                    <TabsContent value="performance" className="mt-0 min-h-[450px]">
                        {isPending ? (
                            <Skeleton className="w-full h-[450px] rounded-lg" />
                        ) : (
                            <PerformanceChart
                                data={runData.equity}
                                baseCurrency={runData.baseCurrency || "USD"}
                                onHover={setHoveredPoint}
                            />
                        )}
                    </TabsContent>
                    <TabsContent value="risk" className="mt-0 min-h-[450px]">
                        <RiskTab equity={runData.equity} />
                    </TabsContent>
                    <TabsContent value="costs" className="mt-0 min-h-[450px]">
                        <CostsTab data={runData as RunData} status={status} />
                    </TabsContent>
                    <TabsContent value="portfolio" className="mt-0 min-h-[450px]">
                        <PortfolioTab runId={runData.id as string} equity={runData.equity} baseCurrency={runData.baseCurrency || "USD"} status={status} />
                    </TabsContent>
                    <TabsContent value="fills" className="mt-0 min-h-[450px]">
                        <FillsTab runId={runData.id as string} baseCurrency={runData.baseCurrency || "USD"} status={status} />
                    </TabsContent>
                    <TabsContent value="configuration" className="mt-0 min-h-[450px]">
                        <ConfigTab data={runData as RunData} />
                    </TabsContent>
                </Tabs>
            </div>

            <div className="hidden lg:block lg:col-span-1 h-full">
                {isPending ? (
                     <Skeleton className="w-full h-full min-h-[500px] rounded-lg" />
                ) : (
                    <InspectorPanel
                        runId={runData.id as string}
                        date={inspectorDate}
                        equity={inspectorEquity}
                        baseCurrency={runData.baseCurrency || "USD"}
                        status={status}
                    />
                )}
            </div>
        </div>
        </div>
    )
}
