
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function InspectorPanel() {
    return (
        <Card className="col-span-1 h-full border-l-4 border-l-primary/20">
            <CardHeader>
                <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">Inspector</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-6">
                    <div className="space-y-1">
                        <span className="text-xs text-muted-foreground">Date</span>
                        <div className="font-mono text-lg font-medium">Mar 05, 2024</div>
                    </div>

                    <div className="space-y-1">
                        <span className="text-xs text-muted-foreground">Equity</span>
                        <div className="text-2xl font-bold">$118.00</div>
                    </div>

                    <div className="space-y-1">
                        <span className="text-xs text-muted-foreground">Daily Return</span>
                        <div className="text-lg font-bold text-green-500">+3.51%</div>
                    </div>

                    <div className="space-y-2 pt-4 border-t">
                        <span className="text-xs text-muted-foreground block">Top Holdings</span>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <span>AAPL</span>
                                <span className="font-mono">15.2%</span>
                            </div>
                            <div className="flex justify-between">
                                <span>MSFT</span>
                                <span className="font-mono">12.5%</span>
                            </div>
                            <div className="flex justify-between">
                                <span>NVDA</span>
                                <span className="font-mono">8.3%</span>
                            </div>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
