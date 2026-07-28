"use client"

import { useState } from "react"
import { PAGES, GLOSSARY, FIELDS } from "@/lib/help/content"
import { PageIntro } from "@/components/help/PageIntro"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { BookOpen, Search, HelpCircle, ArrowRight, ExternalLink, Sparkles, Layers } from "lucide-react"

export default function GuidePage() {
    const [searchTerm, setSearchTerm] = useState("")

    const filteredGlossary = GLOSSARY.filter(t =>
        !searchTerm.trim() ||
        t.term.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.definition.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.category.toLowerCase().includes(searchTerm.toLowerCase())
    )

    return (
        <div className="container max-w-6xl py-8 space-y-8 animate-in fade-in duration-500">
            {/* Page Header */}
            <div className="space-y-2 border-b border-border/40 pb-6">
                <div className="flex items-center gap-2">
                    <div className="p-2 bg-primary/10 text-primary rounded-lg">
                        <BookOpen className="w-6 h-6" />
                    </div>
                    <h1 className="text-2xl font-bold tracking-tight">Technical Guide & Quantitative Glossary</h1>
                </div>
                <p className="text-sm text-muted-foreground">
                    Comprehensive platform documentation, feature area sitemap, and mathematical formulas for quantitative metrics.
                </p>
            </div>

            {/* Page Intro Banner */}
            <PageIntro slug="guide" />

            {/* Feature Area Walkthroughs */}
            <div className="space-y-4">
                <h2 className="text-lg font-bold flex items-center gap-2">
                    <Layers className="w-5 h-5 text-primary" /> Feature Area Guides
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Object.values(PAGES).filter(p => p.slug !== "guide").map(page => (
                        <Card key={page.slug} className="border border-border shadow-sm hover:border-primary/40 transition-colors">
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-base font-bold text-foreground">{page.title}</CardTitle>
                                    <Badge variant="outline" className="font-mono text-[10px]">{page.slug}</Badge>
                                </div>
                                <CardDescription className="text-xs">{page.oneLiner}</CardDescription>
                            </CardHeader>
                            <CardContent className="pt-2 space-y-2">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                                    Workflow Steps
                                </span>
                                <ul className="space-y-1 text-xs list-disc list-inside text-muted-foreground">
                                    {page.howItWorksSteps.map((step, idx) => (
                                        <li key={idx} className="leading-relaxed">{step}</li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>

            {/* Quantitative Glossary Section */}
            <div className="space-y-4 pt-6 border-t border-border/40">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h2 className="text-lg font-bold flex items-center gap-2">
                            <HelpCircle className="w-5 h-5 text-primary" /> Quantitative Glossary & Formula Reference
                        </h2>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            Formal mathematical definitions for performance metrics, risk models, and execution policy.
                        </p>
                    </div>

                    <div className="relative w-64">
                        <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
                        <Input
                            placeholder="Filter glossary terms..."
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            className="h-8 pl-8 text-xs font-mono"
                        />
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredGlossary.map(term => (
                        <Card key={term.key} id={term.key} className="border border-border/70 shadow-sm scroll-mt-20">
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-sm font-bold text-foreground font-mono">{term.term}</CardTitle>
                                    <Badge variant="secondary" className="text-[10px]">{term.category}</Badge>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3 text-xs">
                                <p className="text-muted-foreground leading-relaxed">{term.definition}</p>
                                {term.formula && (
                                    <div className="p-2 rounded bg-muted/40 font-mono text-[11px] border border-border/40 text-primary">
                                        {term.formula}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    )
}
