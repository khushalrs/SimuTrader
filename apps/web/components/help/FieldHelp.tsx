"use client"

import { useState, useRef, useEffect } from "react"
import Link from "next/link"
import { FIELDS, GLOSSARY, FieldHelpContent, GlossaryTerm } from "@/lib/help/content"
import { HelpCircle, ExternalLink, X, Lightbulb } from "lucide-react"

interface FieldHelpProps {
    fieldKey?: string
    termKey?: string
    title?: string
    description?: string
    example?: string
    className?: string
}

export function FieldHelp({
    fieldKey,
    termKey,
    title: customTitle,
    description: customDesc,
    example: customExample,
    className = ""
}: FieldHelpProps) {
    const [isOpen, setIsOpen] = useState(false)
    const popoverRef = useRef<HTMLDivElement>(null)

    // Lookup metadata from FIELDS or GLOSSARY
    const fieldHelp: FieldHelpContent | undefined = fieldKey
        ? FIELDS.find(f => f.fieldKey === fieldKey)
        : undefined

    const glossaryHelp: GlossaryTerm | undefined = termKey
        ? GLOSSARY.find(g => g.key === termKey)
        : undefined

    const displayTitle = customTitle || fieldHelp?.label || glossaryHelp?.term || fieldKey || termKey || "Field Help"
    const displayDesc = customDesc || fieldHelp?.description || glossaryHelp?.definition || ""
    const displayExample = customExample || fieldHelp?.example || ""
    const guideUrl = glossaryHelp ? `/guide#${glossaryHelp.key}` : fieldHelp ? `/${fieldHelp.relatedPageSlug}` : "/guide"

    // Close popover on outside click or Escape key
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") setIsOpen(false)
        }

        if (isOpen) {
            document.addEventListener("mousedown", handleClickOutside)
            document.addEventListener("keydown", handleKeyDown)
        }
        return () => {
            document.removeEventListener("mousedown", handleClickOutside)
            document.removeEventListener("keydown", handleKeyDown)
        }
    }, [isOpen])

    return (
        <span className={`inline-flex items-center relative ${className}`} ref={popoverRef}>
            <button
                type="button"
                aria-label={`Help information for ${displayTitle}`}
                tabIndex={0}
                onClick={() => setIsOpen(prev => !prev)}
                className="p-0.5 text-muted-foreground/60 hover:text-primary transition-colors focus:outline-none focus:ring-1 focus:ring-primary rounded-full ml-1"
            >
                <HelpCircle className="w-3.5 h-3.5" />
            </button>

            {isOpen && (
                <div
                    role="dialog"
                    aria-modal="true"
                    className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-card border border-border rounded-lg shadow-xl z-50 text-xs space-y-2 animate-in fade-in zoom-in-95 duration-150 motion-reduce:animate-none"
                >
                    <div className="flex items-center justify-between pb-1 border-b border-border/40">
                        <span className="font-bold text-foreground flex items-center gap-1.5">
                            <Lightbulb className="w-3.5 h-3.5 text-primary" /> {displayTitle}
                        </span>
                        <button
                            type="button"
                            onClick={() => setIsOpen(false)}
                            className="text-muted-foreground hover:text-foreground"
                        >
                            <X className="w-3.5 h-3.5" />
                        </button>
                    </div>

                    <p className="text-muted-foreground text-[11px] leading-relaxed">{displayDesc}</p>

                    {displayExample && (
                        <div className="p-1.5 rounded bg-muted/40 font-mono text-[10px] text-foreground border border-border/40">
                            <span className="text-muted-foreground font-sans block text-[9px] uppercase font-semibold">Example</span>
                            {displayExample}
                        </div>
                    )}

                    <div className="pt-1 flex justify-end">
                        <Link
                            href={guideUrl}
                            onClick={() => setIsOpen(false)}
                            className="text-[10px] text-primary font-semibold hover:underline flex items-center gap-1"
                        >
                            Learn more in Guide <ExternalLink className="w-2.5 h-2.5" />
                        </Link>
                    </div>
                </div>
            )}
        </span>
    )
}
