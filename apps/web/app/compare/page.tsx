import { getRuns } from "@/lib/api"
import { CompareDashboardClient } from "@/components/compare/CompareDashboardClient"
import { BarChart3 } from "lucide-react"

export const dynamic = "force-dynamic"

export default async function ComparePage() {
    const runs = await getRuns()

    return (
        <div className="container mx-auto py-10 max-w-6xl animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Run Comparison</h1>
                    <p className="text-muted-foreground mt-1 text-sm">
                        Analyze multiple backtest simulations side-by-side to understand performance deltas.
                    </p>
                </div>
                <div className="p-2 bg-primary/10 rounded-full">
                    <BarChart3 className="w-5 h-5 text-primary" />
                </div>
            </div>
            
            <CompareDashboardClient availableRuns={runs} />
        </div>
    )
}
