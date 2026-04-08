import { getRuns } from "@/lib/api"
import { formatCurrency } from "@/lib/utils"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
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

    // Assuming backend sorts properly, but we can reverse just in case newest are first 
    // or sort it manually if we had timestamps. We'll reverse for now.
    const sortedRuns = [...runs].reverse()

    return (
        <div className="container mx-auto py-10 max-w-6xl animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
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

            <div className="rounded-xl border bg-card/60 backdrop-blur-sm overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader className="bg-secondary/40">
                            <TableRow>
                                <TableHead className="w-[110px]">ID</TableHead>
                                <TableHead>Strategy</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Date Range</TableHead>
                                <TableHead className="text-right">Ending Equity</TableHead>
                                <TableHead className="w-[50px]"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {sortedRuns.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={6} className="h-48 text-center">
                                        <div className="flex flex-col items-center justify-center text-muted-foreground">
                                            <Database className="h-10 w-10 mb-4 opacity-20" />
                                            <p className="font-medium text-foreground/70">No runs found</p>
                                            <p className="text-xs max-w-sm mt-1">You haven't executed any backtests yet. Go to the Builder to create your first simulation.</p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            )}
                            {sortedRuns.map((run) => (
                                <TableRow 
                                    key={run.id as string} 
                                    className="group hover:bg-secondary/20 cursor-pointer transition-colors"
                
                                >
                                    <TableCell className="font-mono text-xs font-medium text-muted-foreground">
                                        <Link href={`/runs/${run.id}`} className="absolute inset-0" aria-label="View run"></Link>
                                        #{String(run.id).split("-")[0]}
                                    </TableCell>
                                    <TableCell>
                                        <div className="font-medium text-foreground/90 group-hover:text-primary transition-colors">
                                            {run.title || "Untitled Strategy Run"}
                                        </div>
                                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                                            {((run.tags as string[]) || []).slice(0, 3).map(tag => (
                                                <span key={tag} className="text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded-sm bg-primary/10 text-primary/70">
                                                    {tag}
                                                </span>
                                            ))}
                                            {((run.tags as string[]) || []).length === 0 && (
                                                <span className="text-[10px] text-muted-foreground/60 italic">Custom Base</span>
                                            )}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <Badge 
                                            variant={
                                                run.status === "SUCCEEDED" ? "default" : 
                                                run.status === "FAILED" ? "destructive" : "secondary"
                                            }
                                            className={
                                                run.status === "SUCCEEDED" ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/25 border-emerald-500/20" : 
                                                run.status === "FAILED" ? "bg-destructive/15 text-destructive hover:bg-destructive/25 border-destructive/20" : 
                                                ""
                                            }
                                        >
                                            {run.status === "RUNNING" && <Clock className="w-3 h-3 mr-1.5 animate-pulse" />}
                                            {run.status === "FAILED" && <AlertCircle className="w-3 h-3 mr-1.5" />}
                                            {run.status}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        {run.effective_start_date ? (
                                             <div className="flex items-center text-xs text-muted-foreground font-mono">
                                                <Calendar className="w-3 h-3 mr-1.5 opacity-50" />
                                                <span>{run.effective_start_date.split("T")[0]}</span>
                                                <span className="mx-1.5 opacity-50">→</span>
                                                <span>{run.effective_end_date ? run.effective_end_date.split("T")[0] : "Active"}</span>
                                            </div>
                                        ) : (
                                            <span className="text-xs text-muted-foreground italic opacity-50">N/A</span>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right font-medium">
                                        {run.status === "SUCCEEDED" && run.equity && run.equity.length > 0 ? (
                                            <span className="font-mono">{formatCurrency(run.equity[run.equity.length - 1].value, run.baseCurrency || "USD")}</span>
                                        ) : (
                                            <span className="text-muted-foreground/40 font-mono">-</span>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <ChevronRight className="w-4 h-4 text-muted-foreground/40 group-hover:text-primary transition-colors ml-auto" />
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </div>
        </div>
    )
}
