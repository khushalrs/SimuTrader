"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { RefreshCw } from "lucide-react"
import { createRunFromSnapshot } from "@/lib/api"

interface RunRetryButtonProps {
    config: any
}

export function RunRetryButton({ config }: RunRetryButtonProps) {
    const router = useRouter()
    const [isRetrying, setIsRetrying] = useState(false)

    const handleRetry = async () => {
        if (!config) return
        setIsRetrying(true)
        try {
            const newRunId = await createRunFromSnapshot(config)
            router.push(`/runs/${newRunId}`)
        } catch (err) {
            console.error("Failed to retry run:", err)
            setIsRetrying(false)
        }
    }

    return (
        <Button onClick={handleRetry} disabled={isRetrying} variant="destructive">
            <RefreshCw className={`mr-2 h-4 w-4 ${isRetrying ? "animate-spin" : ""}`} />
            {isRetrying ? "Retrying..." : "Retry Run"}
        </Button>
    )
}
