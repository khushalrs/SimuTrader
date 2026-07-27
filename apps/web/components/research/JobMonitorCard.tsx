"use client"

import { useState } from "react"
import useSWR from "swr"
import { getResearchJob, cancelResearchJob, ResearchJobOut } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Activity, Loader2, CheckCircle2, AlertTriangle, XCircle, Ban, ChevronDown, ChevronUp } from "lucide-react"

interface JobMonitorCardProps {
    jobId: string
    onSelectJob?: (jobId: string) => void
}

export function JobMonitorCard({ jobId, onSelectJob }: JobMonitorCardProps) {
    const [showFailures, setShowFailures] = useState(false)
    const [isCancelling, setIsCancelling] = useState(false)

    const { data: job, mutate } = useSWR<ResearchJobOut | null>(
        jobId ? `/research/jobs/${jobId}` : null,
        () => getResearchJob(jobId),
        {
            refreshInterval: (data) => {
                if (!data) return 1500
                if (data.status === "QUEUED" || data.status === "RUNNING") return 1500
                return 0
            },
            keepPreviousData: true
        }
    )

    if (!job) {
        return (
            <Card className="p-6 text-center text-muted-foreground animate-pulse">
                <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
                Fetching research job status...
            </Card>
        )
    }

    const { progress } = job
    const nTotal = progress.n_total || 1
    const nDone = progress.n_done || 0
    const pct = Math.min(100, Math.round((nDone / nTotal) * 100))

    const isRunning = job.status === "RUNNING" || job.status === "QUEUED"
    const isCompleted = job.status === "SUCCEEDED" || job.status === "COMPLETE" || job.status === "FINISHED"
    const isFailed = job.status === "FAILED"
    const isCancelled = job.status === "CANCELLED"

    const handleCancel = async () => {
        setIsCancelling(true)
        try {
            await cancelResearchJob(jobId)
            mutate()
        } finally {
            setIsCancelling(false)
        }
    }

    return (
        <Card className="border border-border shadow-sm overflow-hidden">
            <CardHeader className="pb-3 border-b border-border/40 flex flex-row items-center justify-between space-y-0">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <CardTitle className="text-sm font-bold font-mono">Job {job.job_id.substring(0, 8)}</CardTitle>
                        <Badge
                            variant={isCompleted ? "default" : isFailed ? "destructive" : isRunning ? "secondary" : "outline"}
                            className="text-[10px] font-semibold"
                        >
                            {isRunning && <Loader2 className="w-3 h-3 animate-spin mr-1 inline" />}
                            {job.status}
                        </Badge>
                        <Badge variant="outline" className="text-[10px]">{job.type}</Badge>
                    </div>
                    <CardDescription className="text-xs">
                        Created {new Date(job.created_at).toLocaleTimeString()} · Base Run: {job.base_run_id.substring(0, 8)}
                    </CardDescription>
                </div>

                {isRunning && (
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs text-destructive border-destructive/30 hover:bg-destructive/10 gap-1"
                        disabled={isCancelling}
                        onClick={handleCancel}
                    >
                        <Ban className="w-3.5 h-3.5" />
                        {isCancelling ? "Cancelling..." : "Cancel Job"}
                    </Button>
                )}
            </CardHeader>

            <CardContent className="pt-4 space-y-4">
                {/* Progress bar */}
                <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-mono font-semibold">
                        <span>Progress: {nDone} / {nTotal} Tasks</span>
                        <span>{pct}%</span>
                    </div>
                    <div className="h-2.5 w-full bg-muted rounded-full overflow-hidden flex">
                        <div
                            className={`h-full transition-all duration-500 ${isFailed ? "bg-rose-500" : isCompleted ? "bg-emerald-500" : "bg-primary animate-pulse"}`}
                            style={{ width: `${pct}%` }}
                        />
                    </div>
                </div>

                {/* Progress Statistics Grid */}
                <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    <div className="p-2 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                        <span className="text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400 block">Succeeded</span>
                        <span className="font-bold font-mono text-sm">{progress.n_succeeded}</span>
                    </div>
                    <div className="p-2 rounded-md bg-rose-500/10 border border-rose-500/20">
                        <span className="text-[10px] uppercase font-bold text-rose-600 dark:text-rose-400 block">Failed</span>
                        <span className="font-bold font-mono text-sm">{progress.n_failed}</span>
                    </div>
                    <div className="p-2 rounded-md bg-primary/10 border border-primary/20">
                        <span className="text-[10px] uppercase font-bold text-primary block">Active</span>
                        <span className="font-bold font-mono text-sm">{progress.n_active}</span>
                    </div>
                    <div className="p-2 rounded-md bg-muted border border-border/50">
                        <span className="text-[10px] uppercase font-bold text-muted-foreground block">Planned</span>
                        <span className="font-bold font-mono text-sm">{progress.n_planned}</span>
                    </div>
                </div>

                {/* Failure Log Toggle */}
                {progress.failures && progress.failures.length > 0 && (
                    <div className="pt-2 border-t border-border/30">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="w-full text-xs justify-between h-7 text-rose-500 hover:text-rose-600 hover:bg-rose-500/10"
                            onClick={() => setShowFailures(prev => !prev)}
                        >
                            <span className="flex items-center gap-1.5 font-semibold">
                                <AlertTriangle className="w-3.5 h-3.5" />
                                {progress.failures.length} Task Failure(s) Recorded
                            </span>
                            {showFailures ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </Button>

                        {showFailures && (
                            <div className="mt-2 space-y-1.5 text-[11px] font-mono max-h-40 overflow-y-auto p-2 bg-muted/40 rounded border border-border/50">
                                {progress.failures.map((f, idx) => (
                                    <div key={idx} className="p-1.5 bg-background rounded border border-rose-500/20 text-rose-600 dark:text-rose-400">
                                        <div>Run: {f.run_id || "Unassigned"}</div>
                                        <div className="text-[10px] opacity-80">{f.error_code || "E_TASK_FAILED"}: {f.error_message_public || "Execution error"}</div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
