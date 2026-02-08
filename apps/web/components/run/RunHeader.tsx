import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Share, Download } from "lucide-react"

interface RunHeaderProps {
    runId: string
    title: string
    tags: string[]
    date: string
}

export function RunHeader({ runId, title, tags, date }: RunHeaderProps) {
    return (
        <div className="space-y-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
                        <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">{runId}</Badge>
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
