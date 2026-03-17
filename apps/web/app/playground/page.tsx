"use client"

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import { TrendingUp, BarChart2, Zap, ArrowRight, Layers, Activity } from "lucide-react"
import Link from "next/link"

import { presets, PresetConfig } from "@/config/presets"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { createRunFromSnapshot } from "@/lib/api"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Loader2, Copy, Check } from "lucide-react"

export default function PlaygroundPage() {
    const router = useRouter()
    const [pendingRunId, setPendingRunId] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [viewConfig, setViewConfig] = useState<PresetConfig | null>(null)
    const [copied, setCopied] = useState(false)

    const handleRunPreset = async (preset: PresetConfig) => {
        try {
            setError(null)
            setPendingRunId(preset.id)
            const runId = await createRunFromSnapshot(preset.config_snapshot)
            router.push(`/runs/${runId}`)
        } catch (err: any) {
            setError(err.message || "Failed to create run")
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
                <h1 className="text-3xl font-bold tracking-tight">Playground</h1>
                <p className="text-muted-foreground mt-2">
                    Select a preset strategy to run a simulation instantly. No configuration required.
                </p>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {presets.map((preset, index) => (
                    <motion.div
                        key={preset.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: index * 0.1 }}
                    >
                        <Card className="h-full flex flex-col hover:border-primary/50 transition-colors">
                            <CardHeader>
                                <div className={`mb-2 w-10 h-10 rounded-lg bg-muted flex items-center justify-center ${preset.color}`}>
                                    <preset.icon className="w-6 h-6" />
                                </div>
                                <CardTitle>{preset.title}</CardTitle>
                                <CardDescription>{preset.universe}</CardDescription>
                            </CardHeader>
                            <CardContent className="flex-1">
                                <p className="text-sm text-muted-foreground">{preset.behavior}</p>
                            </CardContent>
                            <CardFooter className="flex justify-between gap-2">
                                <Button
                                    variant="outline"
                                    className="w-full"
                                    onClick={() => setViewConfig(preset)}
                                >
                                    View Config
                                </Button>
                                <Button
                                    className="w-full"
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
                                            Run <ArrowRight className="ml-2 h-4 w-4" />
                                        </>
                                    )}
                                </Button>
                            </CardFooter>
                        </Card>
                    </motion.div>
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
