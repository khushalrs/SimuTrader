"use client"

import { useState } from "react"
import useSWR from "swr";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PerformanceChart } from "@/components/run/PerformanceChart"
import { ExplainTab } from "@/components/run/ExplainTab"
import { RiskTab } from "@/components/run/RiskTab"
import { CostsTab } from "@/components/run/CostsTab"
import { PortfolioTab } from "@/components/run/PortfolioTab"
import { FillsTab } from "@/components/run/FillsTab"
import { ConfigTab } from "@/components/run/ConfigTab"
import { TaxesTab } from "@/components/run/TaxesTab"
import { ExposureTab } from "@/components/run/ExposureTab"
import { TradeAnalyticsTab } from "@/components/run/TradeAnalyticsTab"
import { InspectorPanel } from "@/components/run/InspectorPanel"
import { RunHeader } from "@/components/run/RunHeader"
import { KPIGrid } from "@/components/run/KPIGrid"
import { RunRetryButton } from "@/components/run/RunRetryButton"
import { MonthlyReturnsTab } from "@/components/run/MonthlyReturnsTab"
import { RollingMetricsTab } from "@/components/run/RollingMetricsTab"
import { PortfolioReplayTab } from "@/components/run/PortfolioReplayTab"
import { SignalPipelineTimeline } from "@/components/run/SignalPipelineTimeline"
import { PageIntro } from "@/components/help/PageIntro"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, Loader2, Lightbulb, ArrowRight } from "lucide-react"
import { RunData, RunFillOut, getRun, getRunMetrics, getRunEquity, getRunStatus, getRunExplain, getRunBenchmark } from "@/lib/api"

export function RunDashboardClient({ runId }: { runId: string }) {
    const [activeTab, setActiveTab] = useState<string>("performance")

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

    const { data: benchmarkDataList } = useSWR(
        isSucceeded ? `/runs/${runId}/benchmark` : null,
        () => getRunBenchmark(runId),
        { revalidateOnFocus: false }
    );

    const { data: explainData } = useSWR(
        isSucceeded ? `/runs/${runId}/explain` : null,
        () => getRunExplain(runId),
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
    const [selectedFill, setSelectedFill] = useState<RunFillOut | null>(null);

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
        <div className="space-y-6 animate-in fade-in duration-500">
            <PageIntro slug="run_detail" />
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
                    {/* Compact "Why this result?" card linking to the Explain tab */}
                    {isSucceeded && (
                        <Card className="border border-primary/20 bg-gradient-to-r from-primary/5 via-card to-card shadow-sm overflow-hidden animate-in fade-in slide-in-from-bottom duration-300">
                            <CardContent className="pt-4 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <div className="flex items-start sm:items-center gap-3">
                                    <div className="p-2 bg-primary/10 rounded-lg text-primary shrink-0">
                                        <Lightbulb className="w-5 h-5" />
                                    </div>
                                    <div>
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Why this result?</h4>
                                        <p className="text-sm font-medium text-foreground mt-0.5 line-clamp-2 sm:line-clamp-1">
                                            {explainData?.headline || explainData?.summary || "Gross return degraded by transaction fees & drag factors. View full analysis."}
                                        </p>
                                    </div>
                                </div>
                                <Button 
                                    variant="outline" 
                                    size="sm" 
                                    className="shrink-0 gap-1.5 text-xs border-primary/30 hover:bg-primary/10"
                                    onClick={() => setActiveTab("explain")}
                                >
                                    View Full Explanation <ArrowRight className="w-3.5 h-3.5" />
                                </Button>
                            </CardContent>
                        </Card>
                    )}

                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                        <div className="flex items-center justify-between mb-4">
                            <TabsList className="flex flex-wrap h-auto gap-1">
                                <TabsTrigger value="performance">Performance</TabsTrigger>
                                <TabsTrigger value="replay" disabled={isPending || isFailed}>Replay Scrubber</TabsTrigger>
                                <TabsTrigger value="timeline" disabled={isPending || isFailed}>Pipeline Timeline</TabsTrigger>
                                <TabsTrigger value="monthly" disabled={isPending || isFailed}>Monthly Heatmap</TabsTrigger>
                                <TabsTrigger value="rolling" disabled={isPending || isFailed}>Rolling Metrics</TabsTrigger>
                                <TabsTrigger value="explain" disabled={isPending || isFailed}>Explain</TabsTrigger>
                                <TabsTrigger value="risk" disabled={isPending || isFailed}>Risk</TabsTrigger>
                                <TabsTrigger value="exposure" disabled={isPending || isFailed}>Exposure</TabsTrigger>
                                <TabsTrigger value="trades" disabled={isPending || isFailed}>Trade Analytics</TabsTrigger>
                                <TabsTrigger value="costs" disabled={isPending || isFailed}>Costs</TabsTrigger>
                                <TabsTrigger value="portfolio" disabled={isPending || isFailed}>Portfolio</TabsTrigger>
                                <TabsTrigger value="fills" disabled={isPending || isFailed}>Fills</TabsTrigger>
                                <TabsTrigger value="taxes" disabled={isPending || isFailed}>Taxes</TabsTrigger>
                                <TabsTrigger value="configuration" disabled={isPending}>Configuration</TabsTrigger>
                            </TabsList>
                        </div>

                        <TabsContent value="performance" className="mt-0 min-h-[450px]">
                            {isPending ? (
                                <Skeleton className="w-full h-[450px] rounded-lg" />
                            ) : (
                                <PerformanceChart
                                    data={runData.equity}
                                    benchmarkData={benchmarkDataList || undefined}
                                    baseCurrency={runData.baseCurrency || "USD"}
                                    onHover={setHoveredPoint}
                                />
                            )}
                        </TabsContent>
                        <TabsContent value="replay" className="mt-0 min-h-[450px]">
                            <PortfolioReplayTab
                                runId={runData.id as string}
                                equity={runData.equity}
                                baseCurrency={runData.baseCurrency || "USD"}
                                status={status}
                            />
                        </TabsContent>
                        <TabsContent value="timeline" className="mt-0 min-h-[450px]">
                            <SignalPipelineTimeline
                                runId={runData.id as string}
                                baseCurrency={runData.baseCurrency || "USD"}
                            />
                        </TabsContent>
                        <TabsContent value="monthly" className="mt-0 min-h-[450px]">
                            <MonthlyReturnsTab
                                equity={runData.equity}
                                benchmarkEquity={benchmarkDataList || undefined}
                            />
                        </TabsContent>
                        <TabsContent value="rolling" className="mt-0 min-h-[450px]">
                            <RollingMetricsTab
                                equity={runData.equity}
                                benchmarkEquity={benchmarkDataList || undefined}
                            />
                        </TabsContent>
                        <TabsContent value="explain" className="mt-0 min-h-[450px]">
                            <ExplainTab runId={runData.id as string} />
                        </TabsContent>
                        <TabsContent value="risk" className="mt-0 min-h-[450px]">
                            <RiskTab equity={runData.equity} />
                        </TabsContent>
                        <TabsContent value="exposure" className="mt-0 min-h-[450px]">
                            <ExposureTab runId={runData.id as string} />
                        </TabsContent>
                        <TabsContent value="trades" className="mt-0 min-h-[450px]">
                            <TradeAnalyticsTab runId={runData.id as string} baseCurrency={runData.baseCurrency || "USD"} />
                        </TabsContent>
                        <TabsContent value="costs" className="mt-0 min-h-[450px]">
                            <CostsTab data={runData as RunData} status={status} />
                        </TabsContent>
                        <TabsContent value="portfolio" className="mt-0 min-h-[450px]">
                            <PortfolioTab runId={runData.id as string} equity={runData.equity} baseCurrency={runData.baseCurrency || "USD"} status={status} />
                        </TabsContent>
                        <TabsContent value="fills" className="mt-0 min-h-[450px]">
                            <FillsTab
                                runId={runData.id as string}
                                baseCurrency={runData.baseCurrency || "USD"}
                                status={status}
                                onSelectFill={setSelectedFill}
                                selectedFillId={selectedFill?.id || (selectedFill ? `${selectedFill.symbol}-${selectedFill.date}` : undefined)}
                            />
                        </TabsContent>
                        <TabsContent value="taxes" className="mt-0 min-h-[450px]">
                            <TaxesTab runId={runData.id as string} baseCurrency={runData.baseCurrency || "USD"} status={status} />
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
                            selectedFill={selectedFill}
                            onClearSelectedFill={() => setSelectedFill(null)}
                        />
                    )}
                </div>
            </div>
        </div>
    )
}
