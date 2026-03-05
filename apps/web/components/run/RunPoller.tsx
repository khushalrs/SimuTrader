"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

interface RunPollerProps {
    status?: string
    intervalMs?: number
}

export function RunPoller({ status, intervalMs = 3000 }: RunPollerProps) {
    const router = useRouter()

    useEffect(() => {
        if (status === "QUEUED" || status === "RUNNING") {
            const interval = setInterval(() => {
                router.refresh()
            }, intervalMs)
            return () => clearInterval(interval)
        }
    }, [status, router, intervalMs])

    return null
}
