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
    ResearchGridDimension,
    ResearchJobCreate,
    ResearchJobType,
    RunData,
    createResearchJob,
    getConfigPaths,
    getRuns,
} from "@/lib/api"
import { FieldHelp } from "@/components/help/FieldHelp"
import { FlaskConical, Plus, Trash2, ArrowRight, Loader2, ShieldAlert, RefreshCw } from "lucide-react"

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
    const [jobType, setJobType] = useState<ResearchJobType>("SWEEP")
    const [selectedRunId, setSelectedRunId] = useState<string>("")
    const [runs, setRuns] = useState<RunData[]>([])
    const [isLoadingRuns, setIsLoadingRuns] = useState(true)
    const [configPaths, setConfigPaths] = useState<ConfigPathCapability[]>([])
    const [isLoadingPaths, setIsLoadingPaths] = useState(false)
    const [pathsError, setPathsError] = useState<string | null>(null)
    const [pathsRequest, setPathsRequest] = useState(0)
    const [splitPct, setSplitPct] = useState("0.7")
    const [trainLen, setTrainLen] = useState("252")
    const [testLen, setTestLen] = useState("63")
    const [walkForwardMode, setWalkForwardMode] = useState<"anchored" | "rolling">("rolling")

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
        setPathsError(null)
        getConfigPaths(strategy, true)
            .then(paths => {
                if (!active) return
                const concretePaths = paths.filter(path => !path.path.endsWith(".*"))
                if (concretePaths.length === 0) {
                    setConfigPaths([])
                    setPathsError("No sweepable parameters were returned for this run's strategy.")
                    return
                }
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
            .catch((error: unknown) => {
                if (!active) return
                setConfigPaths([])
                setPathsError(error instanceof Error
                    ? error.message
                    : "Parameter capabilities are unavailable.")
            })
            .finally(() => {
                if (active) setIsLoadingPaths(false)
            })
        return () => { active = false }
    }, [runs, selectedRunId, pathsRequest])

    const suggestedValues = (capability?: ConfigPathCapability) => {
        if (!capability) return undefined
        if (capability.enum?.length) return capability.enum.slice(0, 5).join(", ")
        const values = [capability.minimum, capability.default, capability.maximum]
            .filter((value, index, all) => value != null && all.indexOf(value) === index)
        return values.length ? values.join(", ") : undefined
    }

    const addDimension = () => {
        const usedPaths = new Set(gridDims.map(dimension => dimension.path))
        const nextPath = configPaths.find(path => !usedPaths.has(path.path))
        if (!nextPath) return
        setGridDims(prev => [
            ...prev,
            {
                id: `dim-${Date.now()}`,
                path: nextPath.path,
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
            if (pathsError || configPaths.length === 0) {
                throw new Error("Parameter capabilities must load before a research job can be created.")
            }

            const formattedGrid: ResearchGridDimension[] = gridDims.map(dim => {
                if (!configPaths.some(path => path.path === dim.path)) {
                    throw new Error(`"${dim.path}" is not a supported parameter for the selected run.`)
                }
                if (dim.mode === "range") {
                    const min = Number(dim.minVal)
                    const max = Number(dim.maxVal)
                    const step = Number(dim.stepVal)
                    if (![min, max, step].every(Number.isFinite) || max < min || step <= 0) {
                        throw new Error(`Dimension "${dim.path}" requires numeric min/max values and a positive step.`)
                    }
                    return {
                        path: dim.path.trim(),
                        values: { min, max, step }
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
                    if (parsedValues.length === 0) {
                        throw new Error(`Dimension "${dim.path}" needs at least one value.`)
                    }

                    return {
                        path: dim.path.trim(),
                        values: parsedValues
                    }
                }
            })

            let payload: ResearchJobCreate
            if (jobType === "IS_OOS") {
                const parsedSplitPct = Number(splitPct)
                if (!Number.isFinite(parsedSplitPct) || parsedSplitPct <= 0 || parsedSplitPct >= 1) {
                    throw new Error("IS / OOS split must be greater than 0 and less than 1.")
                }
                payload = {
                    type: "IS_OOS",
                    base_run_id: selectedRunId,
                    spec: { split_pct: parsedSplitPct, grid: formattedGrid }
                }
            } else if (jobType === "WALK_FORWARD") {
                const parsedTrainLen = Number(trainLen)
                const parsedTestLen = Number(testLen)
                if (!Number.isInteger(parsedTrainLen) || parsedTrainLen <= 0
                    || !Number.isInteger(parsedTestLen) || parsedTestLen <= 0) {
                    throw new Error("Walk-forward train and test lengths must be positive whole numbers.")
                }
                payload = {
                    type: "WALK_FORWARD",
                    base_run_id: selectedRunId,
                    spec: {
                        train_len: parsedTrainLen,
                        test_len: parsedTestLen,
                        step: parsedTestLen,
                        mode: walkForwardMode,
                        grid: formattedGrid
                    }
                }
            } else {
                payload = {
                    type: "SWEEP",
                    base_run_id: selectedRunId,
                    spec: { grid: formattedGrid }
                }
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

                {jobType === "IS_OOS" && (
                    <div className="space-y-2">
                        <Label htmlFor="research-split-pct" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            3. Configure Validation Split
                        </Label>
                        <div className="max-w-xs">
                            <Label htmlFor="research-split-pct" className="text-[11px] text-muted-foreground">
                                In-sample fraction (0–1)
                            </Label>
                            <Input
                                id="research-split-pct"
                                type="number"
                                min="0.01"
                                max="0.99"
                                step="0.01"
                                value={splitPct}
                                onChange={event => setSplitPct(event.target.value)}
                                className="h-8 text-xs font-mono mt-1"
                            />
                            <p className="mt-1 text-[10px] text-muted-foreground">
                                The remaining observations form the out-of-sample validation period.
                            </p>
                        </div>
                    </div>
                )}

                {jobType === "WALK_FORWARD" && (
                    <div className="space-y-3">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            3. Configure Walk-Forward Windows
                        </Label>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <div>
                                <Label htmlFor="research-train-len" className="text-[11px] text-muted-foreground">Training observations</Label>
                                <Input
                                    id="research-train-len"
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={trainLen}
                                    onChange={event => setTrainLen(event.target.value)}
                                    className="h-8 text-xs font-mono mt-1"
                                />
                            </div>
                            <div>
                                <Label htmlFor="research-test-len" className="text-[11px] text-muted-foreground">Test observations</Label>
                                <Input
                                    id="research-test-len"
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={testLen}
                                    onChange={event => setTestLen(event.target.value)}
                                    className="h-8 text-xs font-mono mt-1"
                                />
                            </div>
                            <div>
                                <Label className="text-[11px] text-muted-foreground">Window mode</Label>
                                <Select
                                    value={walkForwardMode}
                                    onValueChange={value => setWalkForwardMode(value as "anchored" | "rolling")}
                                >
                                    <SelectTrigger className="h-8 text-xs mt-1">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="rolling" className="text-xs">Rolling</SelectItem>
                                        <SelectItem value="anchored" className="text-xs">Anchored</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <p className="text-[10px] text-muted-foreground">
                            Test windows are contiguous; the submitted step automatically matches the test length.
                        </p>
                    </div>
                )}

                {/* Step 3: Parameter Grid Definition */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {jobType === "SWEEP" ? "3" : "4"}. Define Parameter Dimensions Grid
                        </Label>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs gap-1"
                            onClick={addDimension}
                            disabled={isLoadingPaths || configPaths.length === 0 || gridDims.length >= configPaths.length}
                        >
                            <Plus className="w-3.5 h-3.5" /> Add Dimension
                        </Button>
                    </div>

                    {isLoadingPaths && (
                        <div className="h-16 w-full bg-muted/40 animate-pulse rounded-md" />
                    )}

                    {pathsError && !isLoadingPaths && (
                        <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300 text-xs flex items-center gap-2">
                            <ShieldAlert className="w-4 h-4 shrink-0" />
                            <span className="flex-1">
                                Parameter choices could not be loaded: {pathsError} Research job creation is disabled to prevent invalid submissions.
                            </span>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs gap-1"
                                onClick={() => setPathsRequest(request => request + 1)}
                            >
                                <RefreshCw className="w-3 h-3" /> Retry
                            </Button>
                        </div>
                    )}

                    <div className="space-y-3">
                        {gridDims.map((dim, idx) => (
                            <div key={dim.id} className="p-3 bg-muted/20 border border-border/60 rounded-lg space-y-3">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-bold text-foreground font-mono flex items-center">
                                        Dimension #{idx + 1} <FieldHelp
                                            fieldKey={dim.path}
                                            title={configPaths.find(path => path.path === dim.path)?.path}
                                            description={configPaths.find(path => path.path === dim.path)?.description}
                                            example={suggestedValues(configPaths.find(path => path.path === dim.path))}
                                        />
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
                                                const capability = configPaths.find(path => path.path === pathVal)
                                                updateDimension(dim.id, {
                                                    path: pathVal,
                                                    mode: dim.mode === "range" && !capability?.range_supported ? "list" : dim.mode,
                                                    listValues: suggestedValues(capability) || dim.listValues
                                                })
                                            }}
                                            disabled={isLoadingPaths || configPaths.length === 0}
                                        >
                                            <SelectTrigger className="h-8 text-xs font-mono mt-1">
                                                <SelectValue placeholder={isLoadingPaths ? "Loading parameters..." : "No parameters available"} />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {configPaths.map(capability => (
                                                    <SelectItem
                                                        key={capability.path}
                                                        value={capability.path}
                                                        className="text-xs font-mono"
                                                        disabled={gridDims.some(other => other.id !== dim.id && other.path === capability.path)}
                                                    >
                                                        {capability.path}{capability.unit ? ` (${capability.unit})` : ""}
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
                    disabled={isSubmitting || !selectedRunId || isLoadingPaths || configPaths.length === 0 || Boolean(pathsError)}
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
