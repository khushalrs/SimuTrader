import { Suspense } from "react"
import { StrategyBuilder } from "@/components/builder/StrategyBuilder"
import { PageIntro } from "@/components/help/PageIntro"

export const metadata = {
    title: "Build Page - SimuTrader",
    description: "Build logic for simulating your historical trading models.",
}

export default function BuildPage() {
    return (
        <main className="container py-8 space-y-6">
            <PageIntro slug="build_page" />
            <Suspense fallback={<div>Loading builder...</div>}>
                <StrategyBuilder />
            </Suspense>
        </main>
    )
}
