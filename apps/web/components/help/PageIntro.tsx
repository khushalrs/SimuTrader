"use client"

import { useState, useEffect } from "react"
import { PAGES, PageHelpContent } from "@/lib/help/content"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Lightbulb, ChevronDown, ChevronUp, X, BookOpen, HelpCircle } from "lucide-react"

interface PageIntroProps {
    slug: string
    className?: string
}

export function PageIntro({ slug, className = "" }: PageIntroProps) {
    const pageHelp: PageHelpContent | undefined = PAGES[slug]
    const [isExpanded, setIsExpanded] = useState(false)
    const [isDismissed, setIsDismissed] = useState(false)

    useEffect(() => {
        if (!pageHelp) return
        const key = `pageIntro:dismissed:${slug}:v${pageHelp.version}`
        try {
            const dismissed = localStorage.getItem(key) === "true"
            setIsDismissed(dismissed)
        } catch (e) {
            setIsDismissed(false)
        }
    }, [slug, pageHelp])

    if (!pageHelp || isDismissed) return null

    const handleDismiss = () => {
        setIsDismissed(true)
        try {
            const key = `pageIntro:dismissed:${slug}:v${pageHelp.version}`
            localStorage.setItem(key, "true")
        } catch (e) {}
    }

    return (
        <Card className={`border border-primary/20 bg-primary/5 dark:bg-primary/10 shadow-sm relative transition-all ${className}`}>
            <CardContent className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-2.5">
                        <div className="p-1.5 rounded-md bg-primary/10 text-primary shrink-0">
                            <Lightbulb className="w-4 h-4" />
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <h3 className="text-sm font-bold text-foreground">{pageHelp.title}</h3>
                                <Badge variant="outline" className="text-[10px] py-0 font-mono">Guide</Badge>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5 font-medium">{pageHelp.oneLiner}</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                        {pageHelp.howItWorksSteps.length > 0 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs gap-1 text-primary hover:text-primary hover:bg-primary/10"
                                onClick={() => setIsExpanded(prev => !prev)}
                            >
                                <BookOpen className="w-3.5 h-3.5" />
                                {isExpanded ? "Hide Steps" : "How it works"}
                                {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                            onClick={handleDismiss}
                            title="Dismiss intro banner"
                        >
                            <X className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </div>

                {isExpanded && pageHelp.howItWorksSteps.length > 0 && (
                    <div className="pt-3 border-t border-primary/15 space-y-2 animate-in fade-in duration-200">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Step-by-step Execution Overview
                        </span>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                            {pageHelp.howItWorksSteps.map((step, idx) => (
                                <div key={idx} className="p-2.5 rounded bg-background/80 border border-border/50 text-xs flex items-start gap-2">
                                    <span className="font-mono font-bold text-primary shrink-0 bg-primary/10 w-5 h-5 rounded-full flex items-center justify-center text-[11px]">
                                        {idx + 1}
                                    </span>
                                    <span className="text-foreground/90 text-[11px] leading-relaxed">{step}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
