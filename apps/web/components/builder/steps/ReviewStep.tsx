"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { createRun, buildValidConfig } from "@/lib/api"

export function ReviewStep({ config, prevStep }: any) {
    const router = useRouter()
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleRun = async () => {
        try {
            setIsSubmitting(true)
            setError(null)
            const runId = await createRun(config)
            router.push(`/runs/${runId}`)
        } catch (err: any) {
            console.error("Run error:", err)
            setError(err.message || "Failed to start run.")
        } finally {
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

                <div className="bg-muted p-4 rounded-md text-xs font-mono overflow-auto max-h-[400px] border border-border">
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
                    <Button onClick={handleRun} disabled={isSubmitting}>
                        {isSubmitting ? "Running..." : "Run Strategy"}
                    </Button>
                </div>
            </div>
        </div>
    )
}
