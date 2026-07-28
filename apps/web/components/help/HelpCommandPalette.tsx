"use client"

import { useState, useEffect, useMemo } from "react"
import { useRouter } from "next/navigation"
import { PAGES, GLOSSARY, FIELDS } from "@/lib/help/content"
import { Search, Command, BookOpen, HelpCircle, ArrowRight, X, Sparkles } from "lucide-react"

export function HelpCommandPalette() {
    const router = useRouter()
    const [isOpen, setIsOpen] = useState(false)
    const [query, setQuery] = useState("")
    const [selectedIndex, setSelectedIndex] = useState(0)

    // Keyboard listener for ⌘K / Ctrl+K & custom trigger event
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault()
                setIsOpen(prev => !prev)
            } else if (e.key === "Escape" && isOpen) {
                setIsOpen(false)
            }
        }

        const handleCustomOpen = () => setIsOpen(true)

        window.addEventListener("keydown", handleKeyDown)
        window.addEventListener("open-help-palette", handleCustomOpen)
        return () => {
            window.removeEventListener("keydown", handleKeyDown)
            window.removeEventListener("open-help-palette", handleCustomOpen)
        }
    }, [isOpen])

    // Search filtering logic across PAGES, GLOSSARY, and FIELDS
    const searchResults = useMemo(() => {
        const q = query.trim().toLowerCase()

        // Page matches
        const matchedPages = Object.values(PAGES).filter(p =>
            !q || p.title.toLowerCase().includes(q) || p.oneLiner.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q)
        ).map(p => ({
            type: "page" as const,
            id: `page-${p.slug}`,
            title: p.title,
            description: p.oneLiner,
            url: p.slug === "home" ? "/" : `/${p.slug}`
        }))

        // Glossary matches
        const matchedTerms = GLOSSARY.filter(t =>
            !q || t.term.toLowerCase().includes(q) || t.definition.toLowerCase().includes(q) || t.category.toLowerCase().includes(q)
        ).map(t => ({
            type: "glossary" as const,
            id: `term-${t.key}`,
            title: t.term,
            description: `${t.category}: ${t.definition}`,
            url: `/guide#${t.key}`
        }))

        // Field matches
        const matchedFields = FIELDS.filter(f =>
            !q || f.label.toLowerCase().includes(q) || f.description.toLowerCase().includes(q) || f.fieldKey.toLowerCase().includes(q)
        ).map(f => ({
            type: "field" as const,
            id: `field-${f.fieldKey}`,
            title: f.label,
            description: f.description,
            url: `/${f.relatedPageSlug}`
        }))

        return [...matchedPages, ...matchedTerms, ...matchedFields]
    }, [query])

    // Handle arrow keys & enter selection
    useEffect(() => {
        setSelectedIndex(0)
    }, [query])

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (searchResults.length === 0) return
        if (e.key === "ArrowDown") {
            e.preventDefault()
            setSelectedIndex(prev => (prev + 1) % searchResults.length)
        } else if (e.key === "ArrowUp") {
            e.preventDefault()
            setSelectedIndex(prev => (prev - 1 + searchResults.length) % searchResults.length)
        } else if (e.key === "Enter") {
            e.preventDefault()
            const item = searchResults[selectedIndex]
            if (item) {
                setIsOpen(false)
                router.push(item.url)
            }
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-start justify-center pt-20 px-4 animate-in fade-in duration-200">
            <div
                className="w-full max-w-2xl bg-card border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]"
                onKeyDown={handleKeyDown}
            >
                {/* Search Input Bar */}
                <div className="p-4 border-b border-border/50 flex items-center gap-3">
                    <Search className="w-5 h-5 text-muted-foreground shrink-0" />
                    <input
                        type="text"
                        autoFocus
                        placeholder="Search page guides, formulas, Sharpe, Monte Carlo, or 'how do I...' (⌘K)"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        className="w-full bg-transparent border-none text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                    />
                    <button
                        onClick={() => setIsOpen(false)}
                        className="p-1 text-muted-foreground hover:text-foreground rounded-md"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* Results List */}
                <div className="overflow-y-auto p-2 space-y-1 divide-y divide-border/20">
                    {searchResults.length === 0 ? (
                        <div className="p-8 text-center text-xs text-muted-foreground">
                            No matching pages, formulas, or glossary terms found.
                        </div>
                    ) : (
                        searchResults.map((item, idx) => {
                            const isSelected = idx === selectedIndex
                            return (
                                <div
                                    key={item.id}
                                    className={`p-3 rounded-lg cursor-pointer transition-colors flex items-center justify-between gap-3 text-xs ${isSelected ? "bg-primary/10 text-primary font-medium" : "hover:bg-muted/40 text-foreground"}`}
                                    onClick={() => {
                                        setIsOpen(false)
                                        router.push(item.url)
                                    }}
                                >
                                    <div className="space-y-0.5 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold">{item.title}</span>
                                            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-muted/60 text-muted-foreground">
                                                {item.type}
                                            </span>
                                        </div>
                                        <p className="text-[11px] text-muted-foreground truncate">{item.description}</p>
                                    </div>
                                    <ArrowRight className="w-3.5 h-3.5 shrink-0 opacity-60" />
                                </div>
                            )
                        })
                    )}
                </div>

                {/* Modal Footer */}
                <div className="p-3 bg-muted/30 border-t border-border/40 text-[11px] text-muted-foreground flex justify-between items-center font-mono">
                    <span className="flex items-center gap-1.5">
                        <Command className="w-3 h-3" /> Navigation: <b>↑↓</b> to move, <b>↵</b> to select, <b>ESC</b> to close
                    </span>
                    <span>{searchResults.length} results</span>
                </div>
            </div>
        </div>
    )
}
