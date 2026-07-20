import React from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

interface ChartFrameProps {
    title: string
    description?: string
    action?: React.ReactNode
    children: React.ReactNode
    className?: string
}

export function ChartFrame({ title, description, action, children, className }: ChartFrameProps) {
    return (
        <Card className={className}>
            <CardHeader className="pb-4 border-b border-border/50 flex flex-row items-center justify-between space-y-0 gap-4">
                <div className="space-y-1">
                    <CardTitle className="text-base font-semibold">{title}</CardTitle>
                    {description && <CardDescription className="text-xs">{description}</CardDescription>}
                </div>
                {action && <div className="shrink-0">{action}</div>}
            </CardHeader>
            <CardContent className="pt-6">
                {children}
            </CardContent>
        </Card>
    )
}

export const CHART_THEME = {
    axis: {
        stroke: "hsl(var(--muted-foreground))",
        fontSize: 11,
        tickLine: false,
        axisLine: false,
    },
    grid: {
        strokeDasharray: "3 3",
        vertical: false,
        stroke: "hsl(var(--border))",
    },
    tooltip: {
        contentStyle: {
            backgroundColor: "hsl(var(--popover))",
            borderColor: "hsl(var(--border))",
            borderRadius: "var(--radius)",
            fontSize: "12px",
            color: "hsl(var(--popover-foreground))",
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)"
        },
        itemStyle: {
            color: "hsl(var(--popover-foreground))",
        },
    }
}
