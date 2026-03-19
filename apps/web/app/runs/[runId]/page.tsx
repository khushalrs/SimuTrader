import { RunDashboardClient } from "@/components/run/RunDashboardClient"

export default function RunDashboardPage({ params }: { params: { runId: string } }) {
    return (
        <main className="container py-8 space-y-8">
            <RunDashboardClient runId={params.runId} />
        </main>
    )
}
