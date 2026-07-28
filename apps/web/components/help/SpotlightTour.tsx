"use client"

import { useState, useEffect, useCallback } from "react"
import { usePathname, useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Sparkles, ChevronRight, ChevronLeft, X, FlaskConical, Layers, Activity } from "lucide-react"

const TOUR_STEPS = [
    {
        step: 1,
        title: "Welcome to SimuTrader",
        description: "Portfolio-grade quantitative backtesting, market data diagnostics, and execution analytics engine.",
        route: "/",
        target: '[data-tour="home-overview"]',
        icon: Sparkles,
        highlights: [
            "Explore strategy presets in the Playground",
            "Build custom quantitative models in the Builder",
            "Audit trade fills and decision traces in real time"
        ]
    },
    {
        step: 2,
        title: "Strategy Builder & Friction Modeling",
        description: "Design custom factor signals, universe filters, risk engine clamps, and tax lot accounting rules.",
        route: "/build_page",
        target: '[data-tour="strategy-builder"]',
        icon: Layers,
        highlights: [
            "Step-by-step 4-stage wizard",
            "Slippage drag & commission modeling",
            "Preflight data validation checks"
        ]
    },
    {
        step: 3,
        title: "Run Inspector & Decision Chain",
        description: "Deep dive into backtest runs with performance curves, monthly heatmaps, and trade trace inspectors.",
        route: "/runs",
        target: '[data-tour="run-history"]',
        icon: Activity,
        highlights: [
            "Click any fill row to open 'Why This Trade?'",
            "Inspect tax lot consumption & capital gain realization",
            "Animate portfolio state day-by-day in Replay Scrubber"
        ]
    },
    {
        step: 4,
        title: "Research Lab & Robustness Studio",
        description: "Execute 2D parameter grid sweeps, in-sample vs out-of-sample split tests, and Monte Carlo resampling.",
        route: "/research",
        target: '[data-tour="research-lab"]',
        icon: FlaskConical,
        highlights: [
            "2D parameter heatmaps for plateau identification",
            "Monte Carlo 500-run bootstrap fan charts",
            "Composite 0-100 robustness score"
        ]
    }
]

interface SpotlightRect {
    top: number
    left: number
    width: number
    height: number
}

export function SpotlightTour() {
    const router = useRouter()
    const pathname = usePathname()
    const [isOpen, setIsOpen] = useState(false)
    const [currentStepIndex, setCurrentStepIndex] = useState(0)
    const [targetRect, setTargetRect] = useState<SpotlightRect | null>(null)

    useEffect(() => {
        try {
            const completed = localStorage.getItem("simutrader:tour:v1") === "completed"
            if (!completed) {
                // Short delay before showing tour on first visit
                const timer = setTimeout(() => {
                    setIsOpen(true)
                    router.push(TOUR_STEPS[0].route)
                }, 1200)
                return () => clearTimeout(timer)
            }
        } catch (e) {}
    }, [router])

    const measureTarget = useCallback(() => {
        if (!isOpen) return
        const target = document.querySelector<HTMLElement>(TOUR_STEPS[currentStepIndex].target)
        if (!target) {
            setTargetRect(null)
            return
        }
        const rect = target.getBoundingClientRect()
        const padding = 8
        setTargetRect({
            top: Math.max(8, rect.top - padding),
            left: Math.max(8, rect.left - padding),
            width: Math.min(window.innerWidth - 16, rect.width + padding * 2),
            height: Math.min(window.innerHeight - 16, rect.height + padding * 2),
        })
    }, [currentStepIndex, isOpen])

    useEffect(() => {
        if (!isOpen) return
        setTargetRect(null)
        const timers = [50, 200, 500].map(delay => window.setTimeout(measureTarget, delay))
        window.addEventListener("resize", measureTarget)
        window.addEventListener("scroll", measureTarget, true)
        return () => {
            timers.forEach(window.clearTimeout)
            window.removeEventListener("resize", measureTarget)
            window.removeEventListener("scroll", measureTarget, true)
        }
    }, [isOpen, pathname, currentStepIndex, measureTarget])

    if (!isOpen) return null

    const currentStep = TOUR_STEPS[currentStepIndex]
    const StepIcon = currentStep.icon

    const handleFinish = () => {
        setIsOpen(false)
        try {
            localStorage.setItem("simutrader:tour:v1", "completed")
        } catch (e) {}
    }

    const handleNext = () => {
        if (currentStepIndex < TOUR_STEPS.length - 1) {
            const nextStep = TOUR_STEPS[currentStepIndex + 1]
            setCurrentStepIndex(prev => prev + 1)
            router.push(nextStep.route)
        } else {
            handleFinish()
        }
    }

    const handleBack = () => {
        if (currentStepIndex > 0) {
            const prevStep = TOUR_STEPS[currentStepIndex - 1]
            setCurrentStepIndex(prev => prev - 1)
            router.push(prevStep.route)
        }
    }

    const cardTop = targetRect && targetRect.top + targetRect.height + 390 < window.innerHeight
        ? targetRect.top + targetRect.height + 16
        : 24

    return (
        <div className="fixed inset-0 z-50 pointer-events-none animate-in fade-in duration-300 motion-reduce:animate-none">
            {targetRect ? (
                <div
                    aria-hidden="true"
                    className="fixed rounded-xl ring-4 ring-primary shadow-[0_0_0_9999px_hsl(var(--background)/0.82)] transition-all duration-300"
                    style={targetRect}
                />
            ) : (
                <div className="fixed inset-0 bg-background/85" aria-hidden="true" />
            )}

            <Card
                role="dialog"
                aria-modal="true"
                aria-label="SimuTrader spotlight tour"
                className="fixed left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-lg max-h-[calc(100vh-3rem)] border-2 border-primary/30 shadow-2xl bg-card overflow-y-auto pointer-events-auto"
                style={{ top: cardTop }}
            >
                <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-primary via-emerald-500 to-indigo-500" />
                
                <CardHeader className="pt-6 pb-3">
                    <div className="flex items-center justify-between">
                        <Badge variant="outline" className="text-[10px] font-mono uppercase font-bold text-primary border-primary/30">
                            Spotlight Tour ({currentStep.step} of {TOUR_STEPS.length})
                        </Badge>
                        <button
                            onClick={handleFinish}
                            className="text-muted-foreground hover:text-foreground p-1 rounded-md"
                            title="Skip Spotlight Tour"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>

                    <div className="flex items-center gap-3 pt-2">
                        <div className="p-2.5 rounded-lg bg-primary/10 text-primary shrink-0">
                            <StepIcon className="w-6 h-6" />
                        </div>
                        <div>
                            <CardTitle className="text-base font-bold text-foreground">{currentStep.title}</CardTitle>
                            <CardDescription className="text-xs text-muted-foreground mt-0.5">{currentStep.description}</CardDescription>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="space-y-3 pt-2 text-xs">
                    <div className="p-3 rounded-lg bg-muted/40 border border-border/50 space-y-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                            Key Capabilities Highlight
                        </span>
                        <ul className="space-y-1.5 font-medium">
                            {currentStep.highlights.map((h, idx) => (
                                <li key={idx} className="flex items-center gap-2 text-foreground/90">
                                    <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                                    {h}
                                </li>
                            ))}
                        </ul>
                    </div>
                </CardContent>

                <CardFooter className="pt-3 border-t border-border/40 flex items-center justify-between">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs text-muted-foreground hover:text-foreground"
                        onClick={handleFinish}
                    >
                        Skip Tour
                    </Button>

                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 text-xs gap-1"
                            disabled={currentStepIndex === 0}
                            onClick={handleBack}
                        >
                            <ChevronLeft className="w-3.5 h-3.5" /> Back
                        </Button>
                        <Button
                            variant="default"
                            size="sm"
                            className="h-8 text-xs gap-1 font-bold"
                            onClick={handleNext}
                        >
                            {currentStepIndex === TOUR_STEPS.length - 1 ? "Finish Tour" : "Next Step"}
                            <ChevronRight className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </CardFooter>
            </Card>
        </div>
    )
}
