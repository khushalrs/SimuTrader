import { getRuns } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { PageIntro } from "@/components/help/PageIntro"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { ChevronRight, Database, Clock, PlayCircle, AlertCircle, Calendar } from "lucide-react"

export const dynamic = "force-dynamic"

export default async function RunsPage() {
    const runs = await getRuns()

    const sortedRuns = [...runs].reverse()

    return (
        <div className="container mx-auto py-10 max-w-6xl space-y-6 animate-in fade-in duration-500">
            <PageIntro slug="runs" />
            <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4" data-tour="run-history">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Run History</h1>
                    <p className="text-muted-foreground mt-1 text-sm">
                        Browse and jump back into your historical backtest simulations.
                    </p>
                </div>
                <Link 
                    href="/build_page"
                    className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 shadow h-9 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90"
                >
                    <PlayCircle className="w-4 h-4 mr-2" />
                    New Backtest
                </Link>
            </div>

            {runs.length === 0 ? (
                <div className="p-8 border rounded-xl bg-card shadow-sm space-y-6 text-center max-w-2xl mx-auto">
                    <div className="p-3 bg-primary/10 text-primary w-12 h-12 rounded-full mx-auto flex items-center justify-center">
                        <Database className="w-6 h-6" />
                    </div>
                    <div className="space-y-2">
                        <h3 className="font-bold text-lg text-foreground">No Backtest Runs Recorded Yet</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Simulations record full portfolio equity curves, execution fills, cost waterfalls, and trade decision traces. Launch a pre-configured demo in the Playground or configure your own strategy in the Builder.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left pt-2">
                        <div className="p-3 rounded-lg bg-muted/40 border border-border/50 text-xs space-y-1">
                            <span className="font-bold text-foreground block">Option 1: Quick Demo</span>
                            <span className="text-[11px] text-muted-foreground block">Launch pre-built preset strategies with one click in the Playground.</span>
                            <Link href="/playground" className="text-[11px] font-bold text-primary hover:underline inline-block pt-1">
                                Launch Playground →
                            </Link>
                        </div>

                        <div className="p-3 rounded-lg bg-muted/40 border border-border/50 text-xs space-y-1">
                            <span className="font-bold text-foreground block">Option 2: Custom Builder</span>
                            <span className="text-[11px] text-muted-foreground block">Define asset universes, factor signals, slippage, and tax regimes step-by-step.</span>
                            <Link href="/build_page" className="text-[11px] font-bold text-primary hover:underline inline-block pt-1">
                                Open Builder Studio →
                            </Link>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="rounded-lg border bg-card shadow-sm">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[180px]">Run ID</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">CAGR</TableHead>
                                <TableHead className="text-right">Sharpe</TableHead>
                                <TableHead className="text-right">Max DD</TableHead>
                                <TableHead className="text-right">Final Equity</TableHead>
                                <TableHead className="w-[50px]"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {sortedRuns.map((run) => {
                                const metricsMap: Record<string, any> = {}
                                if (Array.isArray(run.metrics)) {
                                    run.metrics.forEach((m: any) => {
                                        if (m && m.name) metricsMap[m.name] = m.value
                                    })
                                }
                                const cagr = metricsMap.cagr ?? (run as any).cagr
                                const sharpe = metricsMap.sharpe ?? (run as any).sharpe
                                const maxDd = metricsMap.max_drawdown ?? (run as any).max_drawdown

                                const finalEquity = Array.isArray(run.equity) && run.equity.length > 0
                                    ? run.equity[run.equity.length - 1].value
                                    : undefined

                                return (
                                    <TableRow key={run.id} className="group">
                                        <TableCell className="font-mono font-medium">
                                            <Link href={`/runs/${run.id}`} className="hover:underline flex items-center gap-1.5">
                                                {run.title || run.id.substring(0, 8)}
                                            </Link>
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant={
                                                    run.status === "SUCCEEDED" ? "default" :
                                                    run.status === "FAILED" ? "destructive" : "secondary"
                                                }
                                                className="capitalize"
                                            >
                                                {run.status?.toLowerCase() || "unknown"}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-right font-mono">
                                            {cagr !== undefined && cagr !== null
                                                ? `${(cagr * 100).toFixed(1)}%`
                                                : "—"}
                                        </TableCell>
                                        <TableCell className="text-right font-mono">
                                            {sharpe !== undefined && sharpe !== null
                                                ? Number(sharpe).toFixed(2)
                                                : "—"}
                                        </TableCell>
                                        <TableCell className="text-right font-mono text-rose-500">
                                            {maxDd !== undefined && maxDd !== null
                                                ? `${(maxDd * 100).toFixed(1)}%`
                                                : "—"}
                                        </TableCell>
                                        <TableCell className="text-right font-mono font-semibold">
                                            {finalEquity !== undefined
                                                ? formatCurrency(finalEquity, run.baseCurrency || "USD")
                                                : "—"}
                                        </TableCell>
                                        <TableCell>
                                            <Link href={`/runs/${run.id}`} aria-label={`View details for run ${run.id}`}>
                                                <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                                            </Link>
                                        </TableCell>
                                    </TableRow>
                                )
                            })}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    )
}
