"use client"

import { useState } from "react"
import useSWR from "swr"
import { useRouter } from "next/navigation"
import { listResearchJobs, ResearchJobOut } from "@/lib/api"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ResearchJobWizard } from "@/components/research/ResearchJobWizard"
import { JobMonitorCard } from "@/components/research/JobMonitorCard"
import { SweepResultsTable } from "@/components/research/SweepResultsTable"
import { SweepScatterPlot } from "@/components/research/SweepScatterPlot"
import { FlaskConical, Plus, Activity, ArrowRight, Loader2, RefreshCw } from "lucide-react"

export default function ResearchPage() {
    const router = useRouter()
    const [activeTab, setActiveTab] = useState<string>("jobs")
    const [selectedJobId, setSelectedJobId] = useState<string | null>(null)

    const { data: jobs, isLoading, mutate } = useSWR<ResearchJobOut[]>(
        "/research/jobs",
        () => listResearchJobs(),
        { refreshInterval: 5000 }
    )

    const handleJobCreated = (jobId: string) => {
        setSelectedJobId(jobId)
        mutate()
        setActiveTab("results")
    }

    const handleSelectJob = (jobId: string) => {
        setSelectedJobId(jobId)
        setActiveTab("results")
    }

    const activeJob = selectedJobId
        ? jobs?.find(j => j.job_id === selectedJobId)
        : (jobs && jobs.length > 0 ? jobs[0] : null)

    const currentJobId = activeJob?.job_id || selectedJobId

    return (
        <div className="container max-w-7xl py-8 space-y-8 animate-in fade-in duration-500">
            {/* Page Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/40 pb-6">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-primary/10 text-primary rounded-lg">
                            <FlaskConical className="w-6 h-6" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight">Research Lab & Optimization Studio</h1>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Execute hyperparameter grid sweeps, in-sample/out-of-sample validation, and walk-forward calibrations.
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <Button
                        variant="outline"
                        size="sm"
                        className="gap-1.5 text-xs"
                        onClick={() => mutate()}
                    >
                        <RefreshCw className="w-3.5 h-3.5" /> Refresh Jobs
                    </Button>

                    <Button
                        size="sm"
                        className="gap-1.5 text-xs font-semibold"
                        onClick={() => setActiveTab("wizard")}
                    >
                        <Plus className="w-4 h-4" /> New Research Job
                    </Button>
                </div>
            </div>

            {/* Navigation Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="mb-6">
                    <TabsTrigger value="jobs" className="gap-1.5">
                        <Activity className="w-3.5 h-3.5" /> Research Jobs ({jobs?.length || 0})
                    </TabsTrigger>
                    <TabsTrigger value="wizard" className="gap-1.5">
                        <Plus className="w-3.5 h-3.5" /> Launch Wizard
                    </TabsTrigger>
                    <TabsTrigger value="results" className="gap-1.5" disabled={!currentJobId}>
                        <FlaskConical className="w-3.5 h-3.5" /> Results Explorer {currentJobId ? `(${currentJobId.substring(0, 6)})` : ""}
                    </TabsTrigger>
                </TabsList>

                {/* Tab 1: Research Jobs List */}
                <TabsContent value="jobs" className="space-y-6">
                    {isLoading ? (
                        <Card className="p-6 space-y-4">
                            <Skeleton className="h-8 w-48" />
                            <Skeleton className="h-48 w-full" />
                        </Card>
                    ) : !jobs || jobs.length === 0 ? (
                        <Card className="min-h-[300px] flex flex-col items-center justify-center p-8 text-center border-dashed">
                            <FlaskConical className="w-12 h-12 text-muted-foreground/30 mb-3" />
                            <h3 className="font-semibold text-base">No Research Jobs Found</h3>
                            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                                Create your first hyperparameter grid sweep or cross-validation research job.
                            </p>
                            <Button
                                size="sm"
                                className="mt-4 gap-2 text-xs"
                                onClick={() => setActiveTab("wizard")}
                            >
                                <Plus className="w-3.5 h-3.5" /> Launch Research Wizard
                            </Button>
                        </Card>
                    ) : (
                        <Card className="border border-border shadow-sm">
                            <CardHeader className="pb-3 border-b border-border/40">
                                <CardTitle className="text-base font-bold">Research Jobs History</CardTitle>
                                <CardDescription className="text-xs">Overview of all active and completed optimization jobs.</CardDescription>
                            </CardHeader>
                            <CardContent className="p-0 overflow-x-auto">
                                <Table>
                                    <TableHeader>
                                        <TableRow className="bg-muted/40 text-xs">
                                            <TableHead className="w-28 font-semibold">Job ID</TableHead>
                                            <TableHead className="w-24 font-semibold">Type</TableHead>
                                            <TableHead className="w-28 font-semibold">Base Run</TableHead>
                                            <TableHead className="w-28 font-semibold">Status</TableHead>
                                            <TableHead className="w-40 font-semibold">Progress</TableHead>
                                            <TableHead className="w-36 font-semibold">Created At</TableHead>
                                            <TableHead className="text-right font-semibold">Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody className="text-xs">
                                        {jobs.map(j => {
                                            const nDone = j.progress?.n_done || 0
                                            const nTotal = j.progress?.n_total || 1
                                            const pct = Math.min(100, Math.round((nDone / nTotal) * 100))

                                            return (
                                                <TableRow
                                                    key={j.job_id}
                                                    className="hover:bg-muted/20 cursor-pointer"
                                                    onClick={() => handleSelectJob(j.job_id)}
                                                >
                                                    <TableCell className="font-mono font-bold">{j.job_id.substring(0, 8)}</TableCell>
                                                    <TableCell><Badge variant="outline" className="text-[10px]">{j.type}</Badge></TableCell>
                                                    <TableCell className="font-mono text-muted-foreground">{j.base_run_id.substring(0, 8)}</TableCell>
                                                    <TableCell>
                                                        <Badge
                                                            variant={j.status === "SUCCEEDED" || j.status === "FINISHED" || j.status === "COMPLETE" ? "default" : j.status === "FAILED" ? "destructive" : "secondary"}
                                                            className="text-[10px]"
                                                        >
                                                            {j.status}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="space-y-1">
                                                            <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                                                                <span>{nDone}/{nTotal}</span>
                                                                <span>{pct}%</span>
                                                            </div>
                                                            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                                                                <div
                                                                    className="h-full bg-primary transition-all"
                                                                    style={{ width: `${pct}%` }}
                                                                />
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="text-muted-foreground font-mono">
                                                        {new Date(j.created_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}
                                                    </TableCell>
                                                    <TableCell className="text-right">
                                                        <Button variant="ghost" size="sm" className="h-7 text-xs gap-1">
                                                            Explore <ArrowRight className="w-3.5 h-3.5" />
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            )
                                        })}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* Tab 2: Launch Wizard */}
                <TabsContent value="wizard">
                    <ResearchJobWizard onJobCreated={handleJobCreated} />
                </TabsContent>

                {/* Tab 3: Results Explorer */}
                <TabsContent value="results" className="space-y-6">
                    {currentJobId ? (
                        <>
                            <JobMonitorCard jobId={currentJobId} />
                            <SweepScatterPlot jobId={currentJobId} onSelectRun={(rid) => router.push(`/runs/${rid}`)} />
                            <SweepResultsTable jobId={currentJobId} onSelectRun={(rid) => router.push(`/runs/${rid}`)} />
                        </>
                    ) : (
                        <Card className="p-8 text-center text-muted-foreground">
                            Select a research job from the list or launch a new job to view results.
                        </Card>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    )
}
