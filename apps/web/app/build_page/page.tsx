import { Suspense } from "react"
import { StrategyBuilder } from "@/components/builder/StrategyBuilder"

export const metadata = {
    title: "Build Page - SimuTrader",
    description: "Build logic for simulating your historical trading models.",
}

export default function BuildPage() {
    return (
        <main className="container py-8">
            <Suspense fallback={<div>Loading builder...</div>}>
                <StrategyBuilder />
            </Suspense>
        </main>
    )
}
