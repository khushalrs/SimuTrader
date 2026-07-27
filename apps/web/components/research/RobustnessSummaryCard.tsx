"use client"

import { useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { ShieldCheck, ShieldAlert, AlertTriangle, Award, CheckCircle2 } from "lucide-react"

interface RobustnessSummaryCardProps {
    plateauVariance?: number // 0 (flat plateau) to 1 (high variance/spikes)
    degradationRatio?: number // 0 (no decay) to 1 (full decay)
    mcProbPositive?: number // 0 to 1
    mcTailDrawdown?: number // e.g. -0.15 for 15%
}

export function RobustnessSummaryCard({
    plateauVariance = 0.18,
    degradationRatio = 0.22,
    mcProbPositive = 0.88,
    mcTailDrawdown = -0.16
}: RobustnessSummaryCardProps) {
    // Sub-scores (0 to 100)
    const plateauScore = Math.max(0, Math.min(100, Math.round((1.0 - plateauVariance) * 100)))
    const oosScore = Math.max(0, Math.min(100, Math.round((1.0 - degradationRatio) * 100)))
    const mcScore = Math.max(0, Math.min(100, Math.round(mcProbPositive * 100 * (1.0 + mcTailDrawdown))))

    const compositeScore = Math.round(plateauScore * 0.35 + oosScore * 0.40 + mcScore * 0.25)

    const verdict = useMemo(() => {
        if (compositeScore >= 75) {
            return {
                title: "ROBUST STRATEGY",
                status: "ROBUST",
                badgeVariant: "default" as const,
                colorClass: "border-emerald-500/40 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400",
                icon: ShieldCheck,
                description: "Strategy demonstrates smooth parameter plateaus, low out-of-sample degradation, and strong Monte Carlo tail safety."
            }
        } else if (compositeScore >= 50) {
            return {
                title: "MODERATE SENSITIVITY",
                status: "MODERATE",
                badgeVariant: "secondary" as const,
                colorClass: "border-amber-500/40 bg-amber-500/5 text-amber-600 dark:text-amber-400",
                icon: AlertTriangle,
                description: "Strategy shows acceptable performance but displays moderate parameter sensitivity or mild out-of-sample decay."
            }
        } else {
            return {
                title: "LIKELY OVERFIT / FRAGILE",
                status: "FRAGILE",
                badgeVariant: "destructive" as const,
                colorClass: "border-rose-500/40 bg-rose-500/5 text-rose-500",
                icon: ShieldAlert,
                description: "Strategy displays sharp isolated parameter spikes, severe out-of-sample degradation, or high tail drawdown risk."
            }
        }
    }, [compositeScore])

    const VerdictIcon = verdict.icon

    return (
        <Card className={`border ${verdict.colorClass} shadow-sm overflow-hidden`}>
            <CardHeader className="pb-3 border-b border-border/30">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <VerdictIcon className="w-6 h-6" />
                        <div>
                            <CardTitle className="text-lg font-extrabold tracking-tight">{verdict.title}</CardTitle>
                            <CardDescription className="text-xs text-foreground/80">{verdict.description}</CardDescription>
                        </div>
                    </div>

                    <div className="text-right">
                        <div className="text-2xl font-mono font-extrabold">{compositeScore} / 100</div>
                        <Badge variant={verdict.badgeVariant} className="text-[10px] mt-0.5">Composite Score</Badge>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="pt-4">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-muted/30 text-xs">
                            <TableHead className="font-semibold">Robustness Dimension</TableHead>
                            <TableHead className="font-semibold">Empirical Metric</TableHead>
                            <TableHead className="text-right font-semibold">Sub-Score</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody className="text-xs">
                        <TableRow>
                            <TableCell className="font-medium">Parameter Plateau Stability</TableCell>
                            <TableCell className="font-mono text-muted-foreground">Variance: {(plateauVariance * 100).toFixed(1)}%</TableCell>
                            <TableCell className="text-right font-mono font-bold text-foreground">{plateauScore} / 100</TableCell>
                        </TableRow>

                        <TableRow>
                            <TableCell className="font-medium">IS / OOS Degradation Efficiency</TableCell>
                            <TableCell className="font-mono text-muted-foreground">Decay: {(degradationRatio * 100).toFixed(1)}%</TableCell>
                            <TableCell className="text-right font-mono font-bold text-foreground">{oosScore} / 100</TableCell>
                        </TableRow>

                        <TableRow>
                            <TableCell className="font-medium">Monte Carlo Resampling Tail Safety</TableCell>
                            <TableCell className="font-mono text-muted-foreground">Prob(Win): {(mcProbPositive * 100).toFixed(0)}% | 95% DD: {(mcTailDrawdown * 100).toFixed(1)}%</TableCell>
                            <TableCell className="text-right font-mono font-bold text-foreground">{mcScore} / 100</TableCell>
                        </TableRow>
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    )
}
