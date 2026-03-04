import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { AlertCircle, Share, Download } from "lucide-react"

interface RunHeaderProps {
    runId: string
    title: string
    tags: string[]
    date: string
    requestedStart?: string
    requestedEnd?: string
    effectiveStart?: string
    effectiveEnd?: string
}

export function RunHeader({ runId, title, tags, date, requestedStart, requestedEnd, effectiveStart, effectiveEnd }: RunHeaderProps) {
    const isShifted = requestedStart && effectiveStart && (requestedStart !== effectiveStart || requestedEnd !== effectiveEnd);

    return (
        <div className="space-y-4">
            {isShifted && (
                <div className="flex items-center gap-3 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-3 text-sm text-yellow-600 dark:text-yellow-500">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <p>
                        <strong>Date Range Adjusted: </strong>
                        Requested <code>{requestedStart}</code> to <code>{requestedEnd}</code>;
                        executed on <code>{effectiveStart}</code> to <code>{effectiveEnd}</code>.
                    </p>
                </div>
            )}
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
                        <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">{runId}</Badge>
                        {isShifted && <Badge variant="secondary" className="bg-yellow-500/10 text-yellow-600 hover:bg-yellow-500/20 border-yellow-500/20">Dates Shifted</Badge>}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>{date}</span>
                        <span>•</span>
                        <div className="flex gap-1">
                            {tags.map(tag => (
                                <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                        <Share className="mr-2 h-4 w-4" />
                        Share
                    </Button>
                    <Button variant="outline" size="sm">
                        <Download className="mr-2 h-4 w-4" />
                        Export
                    </Button>
                </div>
            </div>
            <Separator />
        </div>
    )
}
