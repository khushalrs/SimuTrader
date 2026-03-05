import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowUp, ArrowDown } from "lucide-react"

interface KPI {
    label: string
    value: string
    change?: string
    trend?: 'up' | 'down' | 'neutral'
}

interface KPIGridProps {
    metrics: KPI[]
}

export function KPIGrid({ metrics }: KPIGridProps) {
    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {metrics.map((metric) => (
                <Card key={metric.label}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">
                            {metric.label}
                        </CardTitle>
                        {metric.trend === 'up' && <ArrowUp className="h-4 w-4 text-green-500" />}
                        {metric.trend === 'down' && <ArrowDown className="h-4 w-4 text-red-500" />}
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{metric.value}</div>
                        {metric.change && (
                            <p className="text-xs text-muted-foreground">
                                {metric.change}
                            </p>
                        )}
                    </CardContent>
                </Card>
            ))}
        </div>
    )
}
