import { RunDashboardClient } from "@/components/run/RunDashboardClient"
import { getRun } from "@/lib/api"

export default async function RunDashboardPage({ params }: { params: { runId: string } }) {
    const runData = await getRun(params.runId);

    if (!runData) {
        // Fallback UI or 404
        return (
            <main className="container py-8">
                <div className="text-center">
                    <h1 className="text-2xl font-bold">Run Not Found</h1>
                    <p className="text-muted-foreground">Could not fetch data for run: {params.runId}</p>
                    <p className="text-xs text-muted-foreground mt-2">Ensure backend is running on http://localhost:8000</p>
                </div>
            </main>
        );
    }

    return (
        <main className="container py-8 space-y-8">
            <RunDashboardClient initialData={runData} />
        </main>
    )
}
