"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { createRun, buildValidConfig, preflightBacktest } from "@/lib/api"
import { AlertCircle } from "lucide-react"

export function ReviewStep({ config, prevStep }: any) {
    const router = useRouter()
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [idempotencyKey, setIdempotencyKey] = useState<string>("")

    const [preflightRes, setPreflightRes] = useState<any>(null);
    const [isPreflighting, setIsPreflighting] = useState(true);

    useEffect(() => {
        setIdempotencyKey(crypto.randomUUID())
    }, [config])

    useEffect(() => {
        let active = true;
        setIsPreflighting(true);
        preflightBacktest(config).then(res => {
            if (active) {
                setPreflightRes(res);
                setIsPreflighting(false);
            }
        }).catch((err) => {
            if (active) {
                setPreflightRes({
                    status: "red",
                    errors: [err.message || "Preflight request failed."],
                    warnings: []
                });
                setIsPreflighting(false);
            }
        });
        return () => { active = false; };
    }, [config]);

    const handleRun = async () => {
        try {
            setIsSubmitting(true)
            setError(null)
            const runId = await createRun(config, idempotencyKey)
            router.push(`/runs/${runId}`)
        } catch (err: any) {
            console.error("Run error:", err)
            setError(err.message || "Failed to start run.")
        } finally {
            setIdempotencyKey(crypto.randomUUID())
            setIsSubmitting(false)
        }
    }

    return (
        <div className="p-6 flex flex-col h-full">
            <h2 className="text-xl font-semibold mb-6">Review & Run</h2>

            <div className="flex-1 space-y-4">
                <p className="text-sm text-muted-foreground">
                    Your strategy is ready. Review the generated configuration JSON below before submitting to the simulation engine.
                </p>

                {/* Preflight Panel */}
                <div className="space-y-3 p-4 border rounded-lg bg-card shadow-sm">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Engine Preflight Check</h3>
                    {isPreflighting ? (
                        <div className="flex items-center space-x-2 text-sm text-muted-foreground py-2">
                            <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
                            <span>Analyzing configuration rules...</span>
                        </div>
                    ) : preflightRes ? (
                        <div className="space-y-2">
                            {preflightRes.status === "green" && (
                                <div className="flex items-start space-x-3 p-3 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 text-sm">
                                    <div className="w-3 h-3 rounded-full bg-emerald-500 mt-1 shrink-0"></div>
                                    <div>
                                        <span className="font-semibold block">Ready to Run</span>
                                        <span className="text-xs opacity-90">Your strategy configuration passed all validation rules successfully.</span>
                                    </div>
                                </div>
                            )}
                            {preflightRes.status === "yellow" && (
                                <div className="flex items-start space-x-3 p-3 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-600 text-sm">
                                    <div className="w-3 h-3 rounded-full bg-amber-500 mt-1 shrink-0 animate-pulse"></div>
                                    <div>
                                        <span className="font-semibold block">Ready with Warnings</span>
                                        <ul className="list-disc pl-4 mt-1 space-y-1 text-xs opacity-90">
                                            {preflightRes.warnings.map((w: string, i: number) => (
                                                <li key={i}>{w}</li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            )}
                            {preflightRes.status === "red" && (
                                <div className="flex items-start space-x-3 p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-600 text-sm">
                                    <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                                    <div>
                                        <span className="font-semibold block">Cannot Run Simulation</span>
                                        <ul className="list-disc pl-4 mt-1 space-y-1 text-xs opacity-90">
                                            {preflightRes.errors.map((e: string, i: number) => (
                                                <li key={i}>{e}</li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : null}
                </div>

                <div className="bg-muted p-4 rounded-md text-xs font-mono overflow-auto max-h-[300px] border border-border">
                    <pre>{JSON.stringify(buildValidConfig(config), null, 2)}</pre>
                </div>

                {error && (
                    <div className="p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-md">
                        {error}
                    </div>
                )}
            </div>

            <div className="mt-8 flex items-center justify-between pt-4 border-t border-border">
                <Button variant="outline" onClick={prevStep} disabled={isSubmitting}>Back</Button>
                <div className="flex items-center space-x-4">
                    {isSubmitting && <span className="text-sm text-muted-foreground animate-pulse">Running simulation...</span>}
                    <Button onClick={handleRun} disabled={isSubmitting || isPreflighting || preflightRes?.status === "red"}>
                        {isSubmitting ? "Running..." : "Run Strategy"}
                    </Button>
                </div>
            </div>
        </div>
    )
}

function Loader2({ className }: { className?: string }) {
    return (
        <svg className={`animate-spin ${className}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
    )
}
