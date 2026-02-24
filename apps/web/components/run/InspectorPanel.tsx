import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface InspectorPanelProps {
    date?: string;
    equity?: number;
}

export function InspectorPanel({ date, equity }: InspectorPanelProps) {
    return (
        <Card className="col-span-1 h-full border-l-4 border-l-primary/20">
            <CardHeader>
                <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">Inspector</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-6">
                    <div className="space-y-1">
                        <span className="text-xs text-muted-foreground">Date</span>
                        <div className="font-mono text-lg font-medium">{date || "N/A"}</div>
                    </div>

                    <div className="space-y-1">
                        <span className="text-xs text-muted-foreground">Equity</span>
                        <div className="text-2xl font-bold">
                            {equity !== undefined ? `$${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "N/A"}
                        </div>
                    </div>

                    <div className="space-y-2 pt-4 border-t">
                        <span className="text-xs text-muted-foreground block">Top Holdings</span>
                        <div className="space-y-2 text-sm text-muted-foreground italic">
                            Holdings data not available in this summary.
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
