import { getStrategies } from "@/lib/api"
import Link from "next/link"
import { PlayCircle, Library, Calendar, ArrowRight } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { PageIntro } from "@/components/help/PageIntro"

export const dynamic = "force-dynamic"

export default async function StrategiesPage() {
    const strategies = await getStrategies()

    return (
        <div className="container mx-auto py-10 max-w-6xl space-y-6 animate-in fade-in duration-500">
            <PageIntro slug="strategies" />
            <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Strategy Library</h1>
                    <p className="text-muted-foreground mt-1 text-sm">
                        Manage your saved custom configurations and deploy them to the engine.
                    </p>
                </div>
                <Link 
                    href="/build_page"
                    className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium h-9 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow transition-colors"
                >
                    <PlayCircle className="w-4 h-4 mr-2" />
                    New Builder
                </Link>
            </div>

            {strategies.length === 0 ? (
                <div className="p-8 border rounded-xl bg-card shadow-sm space-y-6 text-center max-w-2xl mx-auto">
                    <div className="p-3 bg-primary/10 text-primary w-12 h-12 rounded-full mx-auto flex items-center justify-center">
                        <Library className="w-6 h-6" />
                    </div>
                    <div className="space-y-2">
                        <h3 className="font-bold text-lg text-foreground">No Saved Strategy Templates Yet</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Saved strategy templates allow you to preserve factor weighting, rebalance frequency, friction parameters, and asset universe rules for quick re-use and parameter sweeps.
                        </p>
                    </div>

                    <div className="p-4 rounded-lg bg-muted/40 border border-border/50 text-xs space-y-2 text-left">
                        <span className="font-bold text-foreground block">How Strategy Templates Work:</span>
                        <ul className="space-y-1 text-muted-foreground list-disc list-inside text-[11px]">
                            <li>Configure asset selection rules, factor signals, and risk limits in the Builder Studio.</li>
                            <li>Save the configuration template to your personal library.</li>
                            <li>Launch backtest runs or optimization grid sweeps directly from any template.</li>
                        </ul>
                    </div>

                    <div className="pt-2">
                        <Link
                            href="/build_page"
                            className="inline-flex items-center justify-center rounded-md text-xs font-bold h-9 px-4 bg-primary text-primary-foreground hover:bg-primary/90 shadow transition-colors"
                        >
                            Build & Save Your First Strategy Template →
                        </Link>
                    </div>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {strategies.map((strategy) => (
                        <Link href={`/build_page?strategy_id=${strategy.strategy_id}`} key={strategy.strategy_id} className="group">
                            <div className="bg-card border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all h-full flex flex-col hover:border-primary/50 relative group">
                                <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <ArrowRight className="h-5 w-5 text-primary" />
                                </div>
                                <div className="p-6 flex-1 flex flex-col justify-between">
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <h3 className="font-semibold text-lg group-hover:text-primary transition-colors">
                                                {strategy.name || "Untitled Strategy"}
                                            </h3>
                                        </div>
                                        <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                                            {strategy.description || "No description provided."}
                                        </p>
                                    </div>
                                    
                                    <div className="pt-4 border-t flex items-center justify-between text-xs text-muted-foreground">
                                        <div className="flex items-center gap-1">
                                            <Calendar className="h-3.5 w-3.5" />
                                            <span>
                                                {strategy.created_at ? new Date(strategy.created_at).toLocaleDateString() : "Saved"}
                                            </span>
                                        </div>
                                        <Badge variant="secondary" className="font-mono text-[10px]">
                                            ID: {strategy.strategy_id.substring(0, 8)}
                                        </Badge>
                                    </div>
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    )
}
