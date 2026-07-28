"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    ConfigPathCapability,
    RunData,
    createResearchJob,
    getConfigPaths,
    getRuns,
} from "@/lib/api"
import { FieldHelp } from "@/components/help/FieldHelp"
import { FlaskConical, Layers, Plus, Trash2, ArrowRight, Loader2, CheckCircle2, ShieldAlert } from "lucide-react"

export const VALID_SWEEP_PATHS = [
    { path: "universe.top_n", label: "Top N Assets Selected", example: "5, 10, 20" },
    { path: "strategy.lookback_days", label: "Lookback Window Days", example: "10, 21, 63, 126" },
    { path: "strategy.weights.max_position_size", label: "Max Position Weight Cap", example: "0.1, 0.2, 0.5" },
    { path: "execution.slippage_bps", label: "Slippage Friction (bps)", example: "1, 5, 10, 25" },
    { path: "execution.commission_bps", label: "Commission Fee (bps)", example: "0, 2, 5" },
    { path: "execution.borrow_rate_bps", label: "Short Borrow Rate (bps)", example: "10, 50, 100" },
    { path: "rebalance.frequency_days", label: "Rebalance Period (days)", example: "1, 5, 21" }
]

interface GridDimInput {
    id: string
    path: string
    mode: "list" | "range"
    listValues: string
    minVal: string
    maxVal: string
    stepVal: string
}

interface ResearchJobWizardProps {
    onJobCreated: (jobId: string) => void
}

export function ResearchJobWizard({ onJobCreated }: ResearchJobWizardProps) {
    const [jobType, setJobType] = useState<"SWEEP" | "IS_OOS" | "WALK_FORWARD">("SWEEP")
    const [selectedRunId, setSelectedRunId] = useState<string>("")
    const [runs, setRuns] = useState<RunData[]>([])
    const [isLoadingRuns, setIsLoadingRuns] = useState(true)
    const [configPaths, setConfigPaths] = useState<ConfigPathCapability[]>([])
    const [isLoadingPaths, setIsLoadingPaths] = useState(false)

    const [gridDims, setGridDims] = useState<GridDimInput[]>([
        {
            id: "dim-1",
            path: "commission.bps",
            mode: "list",
            listValues: "0, 5, 10",
            minVal: "0",
            maxVal: "10",
            stepVal: "5"
        }
    ])

    const [isSubmitting, setIsSubmitting] = useState(false)
    const [errorMsg, setErrorMsg] = useState<string | null>(null)

    useEffect(() => {
        setIsLoadingRuns(true)
        getRuns()
            .then(res => {
                const succeeded = (res || []).filter(r => r.status === "SUCCEEDED" || r.equity?.length)
                setRuns(succeeded)
                if (succeeded.length > 0) {
                    setSelectedRunId(succeeded[0].id)
                }
            })
            .catch(() => setRuns([]))
            .finally(() => setIsLoadingRuns(false))
    }, [])

    useEffect(() => {
        const selectedRun = runs.find(run => run.id === selectedRunId)
        const rawStrategy = selectedRun?.config_snapshot?.strategy
        const strategy = typeof rawStrategy === "string"
            ? rawStrategy
            : rawStrategy?.type || "BUY_AND_HOLD"
        let active = true
        setIsLoadingPaths(true)
        getConfigPaths(strategy, true)
            .then(paths => {
                if (!active) return
                const concretePaths = paths.filter(path => !path.path.endsWith(".*"))
                setConfigPaths(concretePaths)
                setGridDims(previous => previous.map((dimension, index) => {
                    if (concretePaths.some(path => path.path === dimension.path)) {
                        return dimension
                    }
                    const preferred = concretePaths.find(path => path.path === "commission.bps")
                        || concretePaths[index % Math.max(concretePaths.length, 1)]
                    return preferred ? { ...dimension, path: preferred.path } : dimension
                }))
            })
            .catch(() => {
                if (active) setConfigPaths([])
            })
            .finally(() => {
                if (active) setIsLoadingPaths(false)
            })
        return () => { active = false }
    }, [runs, selectedRunId])

    const addDimension = () => {
        const usedPaths = new Set(gridDims.map(dimension => dimension.path))
        const nextPath = configPaths.find(path => !usedPaths.has(path.path))
            || configPaths[0]
        setGridDims(prev => [
            ...prev,
            {
                id: `dim-${Date.now()}`,
                path: nextPath?.path || "slippage.bps",
                mode: "list",
                listValues: "0, 5, 10",
                minVal: "0",
                maxVal: "10",
                stepVal: "5"
            }
        ])
    }

    const removeDimension = (id: string) => {
        if (gridDims.length <= 1) return
        setGridDims(prev => prev.filter(d => d.id !== id))
    }

    const updateDimension = (id: string, updates: Partial<GridDimInput>) => {
        setGridDims(prev => prev.map(d => d.id === id ? { ...d, ...updates } : d))
    }

    const handleSubmit = async () => {
        if (!selectedRunId) {
            setErrorMsg("Please select a base run.")
            return
        }

        setErrorMsg(null)
        setIsSubmitting(true)

        try {
            const formattedGrid = gridDims.map(dim => {
                if (dim.mode === "range") {
                    return {
                        path: dim.path.trim(),
                        values: {
                            min: parseFloat(dim.minVal) || 0,
                            max: parseFloat(dim.maxVal) || 1,
                            step: parseFloat(dim.stepVal) || 0.1
                        }
                    }
                } else {
                    const parsedValues = dim.listValues
                        .split(",")
                        .map(v => v.trim())
                        .filter(Boolean)
                        .map(v => {
                            const num = Number(v)
                            return isNaN(num) ? v : num
                        })

                    return {
                        path: dim.path.trim(),
                        values: parsedValues
                    }
                }
            })

            const payload = {
                type: jobType,
                job_type: jobType,
                base_run_id: selectedRunId,
                grid: formattedGrid,
                spec: { grid: formattedGrid }
            }

            const res = await createResearchJob(payload)
            if (res && res.job_id) {
                onJobCreated(res.job_id)
            } else {
                setErrorMsg("Failed to create research job. Unexpected response.")
            }
        } catch (err: any) {
            setErrorMsg(err.message || "Failed to create research job.")
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <Card className="border border-border shadow-sm">
            <CardHeader className="pb-3 border-b border-border/40">
                <CardTitle className="text-base font-bold flex items-center gap-2">
                    <FlaskConical className="w-4 h-4 text-primary" /> Scaffold Research Optimization Job
                </CardTitle>
                <CardDescription className="text-xs">
                    Define hyperparameter grid sweep dimensions, split validation windows, or walk-forward windows.
                </CardDescription>
            </CardHeader>

            <CardContent className="pt-6 space-y-6">
                {/* Step 1: Job Type */}
                <div className="space-y-2">
                    <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center">
                        1. Select Job Type <FieldHelp termKey="robustness" />
                    </Label>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div
                            className={`p-3 rounded-lg border cursor-pointer transition-all ${jobType === "SWEEP" ? "border-primary bg-primary/5 ring-1 ring-primary/30" : "border-border hover:bg-muted/30"}`}
                            onClick={() => setJobType("SWEEP")}
                        >
                            <div className="flex items-center justify-between">
                                <span className="font-semibold text-xs text-foreground">Grid Sweep</span>
                                <Badge variant={jobType === "SWEEP" ? "default" : "outline"} className="text-[10px]">Matrix</Badge>
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-1">Multi-parameter grid evaluation for heatmap visualization.</p>
                        </div>

                        <div
                            className={`p-3 rounded-lg border cursor-pointer transition-all ${jobType === "IS_OOS" ? "border-primary bg-primary/5 ring-1 ring-primary/30" : "border-border hover:bg-muted/30"}`}
                            onClick={() => setJobType("IS_OOS")}
                        >
                            <div className="flex items-center justify-between">
                                <span className="font-semibold text-xs text-foreground">IS / OOS Split</span>
                                <Badge variant={jobType === "IS_OOS" ? "default" : "outline"} className="text-[10px]">Validation</Badge>
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-1">In-sample training vs out-of-sample degradation testing.</p>
                        </div>

                        <div
                            className={`p-3 rounded-lg border cursor-pointer transition-all ${jobType === "WALK_FORWARD" ? "border-primary bg-primary/5 ring-1 ring-primary/30" : "border-border hover:bg-muted/30"}`}
                            onClick={() => setJobType("WALK_FORWARD")}
                        >
                            <div className="flex items-center justify-between">
                                <span className="font-semibold text-xs text-foreground">Walk-Forward Window</span>
                                <Badge variant={jobType === "WALK_FORWARD" ? "default" : "outline"} className="text-[10px]">Rolling</Badge>
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-1">Rolling window re-calibration across historical periods.</p>
                        </div>
                    </div>
                </div>

                {/* Step 2: Base Run Selector */}
                <div className="space-y-2">
                    <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        2. Select Base Simulation Run
                    </Label>
                    {isLoadingRuns ? (
                        <div className="h-10 w-full bg-muted/40 animate-pulse rounded-md" />
                    ) : (
                        <Select value={selectedRunId} onValueChange={setSelectedRunId}>
                            <SelectTrigger className="w-full text-xs font-mono">
                                <SelectValue placeholder="Choose a base simulation run..." />
                            </SelectTrigger>
                            <SelectContent>
                                {runs.map(r => (
                                    <SelectItem key={r.id} value={r.id} className="text-xs font-mono">
                                        {r.title || r.id} ({r.date ? new Date(r.date).toLocaleDateString() : r.id.substring(0, 8)})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}
                </div>

                {/* Step 3: Parameter Grid Definition */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            3. Define Parameter Dimensions Grid
                        </Label>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs gap-1"
                            onClick={addDimension}
                        >
                            <Plus className="w-3.5 h-3.5" /> Add Dimension
                        </Button>
                    </div>

                    <div className="space-y-3">
                        {gridDims.map((dim, idx) => (
                            <div key={dim.id} className="p-3 bg-muted/20 border border-border/60 rounded-lg space-y-3">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-bold text-foreground font-mono flex items-center">
                                        Dimension #{idx + 1} <FieldHelp fieldKey={dim.path} />
                                    </span>
                                    <div className="flex items-center gap-2">
                                        <Select
                                            value={dim.mode}
                                            onValueChange={(val: string) => updateDimension(dim.id, { mode: val as "list" | "range" })}
                                        >
                                            <SelectTrigger className="h-7 text-xs w-28">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="list" className="text-xs">Explicit List</SelectItem>
                                                <SelectItem
                                                    value="range"
                                                    className="text-xs"
                                                    disabled={!configPaths.find(item => item.path === dim.path)?.range_supported}
                                                >
                                                    Min/Max Range
                                                </SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                                            disabled={gridDims.length <= 1}
                                            onClick={() => removeDimension(dim.id)}
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </Button>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div>
                                        <Label className="text-[11px] text-muted-foreground">Select Schema Parameter Path</Label>
                                        <Select
                                            value={dim.path}
                                            onValueChange={pathVal => {
                                                const match = VALID_SWEEP_PATHS.find(p => p.path === pathVal)
                                                updateDimension(dim.id, {
                                                    path: pathVal,
                                                    listValues: match?.example || dim.listValues
                                                })
                                            }}
                                        >
                                            <SelectTrigger className="h-8 text-xs font-mono mt-1">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {VALID_SWEEP_PATHS.map(p => (
                                                    <SelectItem key={p.path} value={p.path} className="text-xs font-mono">
                                                        {p.path} ({p.label})
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {dim.mode === "list" ? (
                                        <div>
                                            <Label className="text-[11px] text-muted-foreground">Comma-separated Values</Label>
                                            <Input
                                                value={dim.listValues}
                                                onChange={e => updateDimension(dim.id, { listValues: e.target.value })}
                                                placeholder="e.g. 5, 10, 20"
                                                className="h-8 text-xs font-mono mt-1"
                                            />
                                        </div>
                                    ) : (
                                        <div className="grid grid-cols-3 gap-2">
                                            <div>
                                                <Label className="text-[11px] text-muted-foreground">Min</Label>
                                                <Input
                                                    value={dim.minVal}
                                                    onChange={e => updateDimension(dim.id, { minVal: e.target.value })}
                                                    className="h-8 text-xs font-mono mt-1"
                                                />
                                            </div>
                                            <div>
                                                <Label className="text-[11px] text-muted-foreground">Max</Label>
                                                <Input
                                                    value={dim.maxVal}
                                                    onChange={e => updateDimension(dim.id, { maxVal: e.target.value })}
                                                    className="h-8 text-xs font-mono mt-1"
                                                />
                                            </div>
                                            <div>
                                                <Label className="text-[11px] text-muted-foreground">Step</Label>
                                                <Input
                                                    value={dim.stepVal}
                                                    onChange={e => updateDimension(dim.id, { stepVal: e.target.value })}
                                                    className="h-8 text-xs font-mono mt-1"
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {errorMsg && (
                    <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
                        <ShieldAlert className="w-4 h-4 shrink-0" />
                        <span>{errorMsg}</span>
                    </div>
                )}
            </CardContent>

            <CardFooter className="pt-3 border-t border-border/40 flex justify-end">
                <Button
                    onClick={handleSubmit}
                    disabled={isSubmitting || !selectedRunId}
                    className="font-bold text-xs gap-1.5"
                >
                    {isSubmitting ? (
                        <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Submitting Job...
                        </>
                    ) : (
                        <>
                            Launch Research Job <ArrowRight className="w-3.5 h-3.5" />
                        </>
                    )}
                </Button>
            </CardFooter>
        </Card>
    )
}
