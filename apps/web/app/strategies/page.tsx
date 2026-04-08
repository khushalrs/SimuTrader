import { getStrategies } from "@/lib/api"
import Link from "next/link"
import { PlayCircle, Library, Calendar, ArrowRight } from "lucide-react"
import { Badge } from "@/components/ui/badge"

export const dynamic = "force-dynamic"

export default async function StrategiesPage() {
    const strategies = await getStrategies()

    return (
        <div className="container mx-auto py-10 max-w-6xl animate-in fade-in duration-500">
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
                <div className="flex flex-col items-center justify-center p-12 text-center bg-card border rounded-xl shadow-sm min-h-[400px]">
                    <Library className="h-12 w-12 text-muted-foreground/30 mb-4" />
                    <p className="text-lg font-semibold">No saved strategies found.</p>
                    <p className="text-muted-foreground mt-2 max-w-sm">Create a custom configuration in the Builder and save it to your library to easily restart tests later.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {strategies.map((strategy) => (
                        <Link href={`/build_page?strategy_id=${strategy.strategy_id}`} key={strategy.strategy_id} className="group">
                            <div className="bg-card border rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all h-full flex flex-col hover:border-primary/50 relative group">
                                <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <ArrowRight className="w-5 h-5 text-primary" />
                                </div>
                                <div className="p-6 flex-1">
                                    <Badge variant="secondary" className="mb-3 text-[10px] space-x-1 uppercase tracking-wider font-mono">
                                        <Calendar className="w-3 h-3 mr-1 inline" />
                                        {strategy.created_at.split("T")[0]}
                                    </Badge>
                                    <h3 className="text-xl font-bold mb-2 group-hover:text-primary transition-colors pr-6">
                                        {strategy.name}
                                    </h3>
                                    <p className="text-sm text-muted-foreground line-clamp-3 mb-4">
                                        {strategy.description || "No description provided."}
                                    </p>
                                    <div className="flex flex-wrap gap-2 mt-auto">
                                        {strategy.config?.universe?.instruments?.length > 0 && (
                                            <Badge variant="outline" className="text-[10px] bg-secondary/10">
                                                {strategy.config.universe.instruments.length} Asset(s)
                                            </Badge>
                                        )}
                                        {strategy.config?.financing?.margin_rate !== undefined && (
                                            <Badge variant="outline" className="text-[10px] bg-secondary/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800">
                                                Levered
                                            </Badge>
                                        )}
                                    </div>
                                </div>
                                <div className="px-6 py-3 bg-secondary/10 border-t text-xs font-mono text-muted-foreground flex items-center justify-between">
                                    <span className="truncate max-w-[200px]">ID: {strategy.strategy_id.split("-")[0]}...</span>
                                    <span className="flex text-primary font-medium group-hover:-translate-x-1 transition-transform">
                                        Open
                                    </span>
                                </div>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    )
}
