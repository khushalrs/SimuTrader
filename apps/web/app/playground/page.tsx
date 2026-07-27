"use client"

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { TrendingUp, Zap, ArrowRight, Layers, Activity, Loader2, Copy, Check } from "lucide-react"
import { Badge } from "@/components/ui/badge"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
    getOrCreatePlaygroundPresetRun,
    getPlaygroundPresets,
    getRun,
    PlaygroundPreset,
} from "@/lib/api"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"

type DisplayPreset = PlaygroundPreset & {
    title: string
    universe: string
    behavior: string
    icon: any
    color: string
    whatItDemonstrates: string
    universeDetails: string
    strategyType: string
    realismSettings: string
    expectedInsight: string
}

const strategyPresentation: Record<string, { icon: any; color: string }> = {
    BUY_AND_HOLD: { icon: TrendingUp, color: "text-blue-500" },
    FIXED_WEIGHT_REBALANCE: { icon: Layers, color: "text-orange-500" },
    MOMENTUM: { icon: Zap, color: "text-yellow-500" },
    MEAN_REVERSION: { icon: Activity, color: "text-green-500" },
    DCA: { icon: TrendingUp, color: "text-indigo-500" },
}

function toDisplayPreset(preset: PlaygroundPreset): DisplayPreset {
    const presentation =
        strategyPresentation[preset.strategy_type] || strategyPresentation.BUY_AND_HOLD
    const commission = preset.config_snapshot?.commission?.bps ?? 0
    const slippage = preset.config_snapshot?.slippage?.bps ?? 0
    return {
        ...preset,
        title: preset.name,
        universe: preset.asset_classes.join(" + ").replaceAll("_", " "),
        behavior: preset.description,
        icon: presentation.icon,
        color: presentation.color,
        whatItDemonstrates: preset.description,
        universeDetails: preset.symbols.join(", "),
        strategyType: preset.strategy_type.replaceAll("_", " "),
        realismSettings: `${preset.base_currency} base, ${commission}bps commission, ${slippage}bps slippage`,
        expectedInsight: "Inspect returns, risk, exposures, costs, taxes, and execution details.",
    }
}

export default function PlaygroundPage() {
    const router = useRouter()
    const [presets, setPresets] = useState<DisplayPreset[]>([])
    const [isLoadingPresets, setIsLoadingPresets] = useState(true)
    const [pendingRunId, setPendingRunId] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [viewConfig, setViewConfig] = useState<DisplayPreset | null>(null)
    const [copied, setCopied] = useState(false)
    const presetRunStorageKey = "playground_preset_runs_v1"

    useEffect(() => {
        let active = true
        getPlaygroundPresets()
            .then((items) => {
                if (active) setPresets(items.map(toDisplayPreset))
            })
            .catch((err: any) => {
                if (active) setError(err.message || "Failed to load presets")
            })
            .finally(() => {
                if (active) setIsLoadingPresets(false)
            })
        return () => {
            active = false
        }
    }, [])

    const readPresetRunMap = (): Record<string, string> => {
        if (typeof window === "undefined") return {}
        try {
            const raw = window.localStorage.getItem(presetRunStorageKey)
            if (!raw) return {}
            const parsed = JSON.parse(raw)
            if (parsed && typeof parsed === "object") return parsed
        } catch {
            // ignore malformed cache
        }
        return {}
    }

    const writePresetRun = (presetId: string, runId: string) => {
        if (typeof window === "undefined") return
        const current = readPresetRunMap()
        current[presetId] = runId
        window.localStorage.setItem(presetRunStorageKey, JSON.stringify(current))
    }

    const handleRunPreset = async (preset: DisplayPreset) => {
        try {
            setError(null)
            setPendingRunId(preset.id)
            const existingRunId = readPresetRunMap()[preset.id]
            if (existingRunId) {
                try {
                    const existingRun = await getRun(existingRunId)
                    if (existingRun && existingRun.status === "SUCCEEDED") {
                        router.push(`/runs/${existingRunId}`)
                        return
                    }
                } catch (e) {
                    // Stale cache hit! Remove the entry so we don't try it again
                    if (typeof window !== "undefined") {
                        const current = readPresetRunMap()
                        delete current[preset.id]
                        window.localStorage.setItem(presetRunStorageKey, JSON.stringify(current))
                    }
                }
            }
            const runId = await getOrCreatePlaygroundPresetRun(preset.id)
            writePresetRun(preset.id, runId)
            router.push(`/runs/${runId}`)
        } catch (err: any) {
            setError(err.message || "Failed to create run")
        } finally {
            setPendingRunId(null)
        }
    }

    const handleCopyConfig = async () => {
        if (!viewConfig) return
        await navigator.clipboard.writeText(JSON.stringify(viewConfig.config_snapshot, null, 2))
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    return (
        <main className="container py-12">
            <div className="mb-8">
                <h1 className="text-3xl font-bold tracking-tight">Simulation Playground</h1>
                <p className="text-muted-foreground mt-2">
                    Quickly launch pre-configured strategy demos. Investigate capital constraints, fees, and cross-border taxes.
                </p>
            </div>

            {isLoadingPresets && (
                <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading presets...
                </div>
            )}

            {!isLoadingPresets && presets.length === 0 && !error && (
                <div className="py-12 text-sm text-muted-foreground">No presets are available.</div>
            )}

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-2">
                {presets.map((preset, index) => (
                    <div
                        key={preset.id}
                        className="anim-fade-slide"
                        style={{ animationDelay: `${index * 100}ms` }}
                    >
                        <Card className="h-full flex flex-col hover:border-primary/50 border-border bg-card shadow-sm transition-all hover:shadow-md">
                            <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                    <div className={`w-9 h-9 rounded-lg bg-muted flex items-center justify-center ${preset.color}`}>
                                        <preset.icon className="w-5 h-5" />
                                    </div>
                                    <Badge variant="secondary" className="text-[10px] px-2.5 py-0.5">{preset.universe}</Badge>
                                </div>
                                <CardTitle className="text-base font-bold mt-3 leading-tight">{preset.title}</CardTitle>
                                <p className="text-xs text-muted-foreground pt-1">{preset.behavior}</p>
                            </CardHeader>
                            
                            <CardContent className="flex-1 space-y-4 text-xs border-t pt-4">
                                <div className="space-y-1">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">What it demonstrates</span>
                                    <span className="text-foreground leading-relaxed font-medium">{preset.whatItDemonstrates}</span>
                                </div>
                                <div className="grid grid-cols-2 gap-3 bg-muted/30 p-2.5 rounded border">
                                    <div>
                                        <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground block">Asset Universe</span>
                                        <span className="text-[11px] font-medium text-foreground truncate block" title={preset.universeDetails}>{preset.universeDetails}</span>
                                    </div>
                                    <div>
                                        <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground block">Realism Settings</span>
                                        <span className="text-[11px] font-medium text-foreground truncate block" title={preset.realismSettings}>{preset.realismSettings}</span>
                                    </div>
                                </div>
                                <div className="space-y-1 bg-primary/[0.02] border border-primary/10 p-2.5 rounded">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-primary block">Expected Insight</span>
                                    <span className="text-foreground/90 font-semibold leading-relaxed block">{preset.expectedInsight}</span>
                                </div>
                            </CardContent>

                            <CardFooter className="flex justify-between gap-2 border-t pt-4 bg-muted/10">
                                <Button
                                    variant="outline"
                                    className="w-full text-xs"
                                    onClick={() => setViewConfig(preset)}
                                >
                                    View Config
                                </Button>
                                <Button
                                    className="w-full text-xs"
                                    disabled={pendingRunId === preset.id}
                                    onClick={() => handleRunPreset(preset)}
                                >
                                    {pendingRunId === preset.id ? (
                                        <>
                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            Running...
                                        </>
                                    ) : (
                                        <>
                                            Run Strategy <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                                        </>
                                    )}
                                </Button>
                            </CardFooter>
                        </Card>
                    </div>
                ))}
            </div>

            {error && (
                <div className="mt-8 p-4 bg-destructive/10 text-destructive rounded-md">
                    {error}
                </div>
            )}

            <Dialog open={!!viewConfig} onOpenChange={(open) => !open && setViewConfig(null)}>
                <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
                    <DialogHeader>
                        <DialogTitle>{viewConfig?.title} Configuration</DialogTitle>
                        <DialogDescription>
                            JSON snapshot of the strategy config that will be sent to the run engine.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex-1 overflow-auto bg-muted p-4 rounded-md relative text-sm font-mono mt-4">
                        <Button
                            size="icon"
                            variant="ghost"
                            className="absolute top-2 right-2 bg-background/50 hover:bg-background"
                            onClick={handleCopyConfig}
                        >
                            {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                        </Button>
                        <pre>
                            {viewConfig ? JSON.stringify(viewConfig.config_snapshot, null, 2) : ""}
                        </pre>
                    </div>
                </DialogContent>
            </Dialog>
        </main>
    )
}
