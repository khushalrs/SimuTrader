"use client"

import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import Link from "next/link"

const steps = [
    {
        step: 1,
        title: "Pick assets",
        description: "Multi-asset universe: US, India, and FX.",
    },
    {
        step: 2,
        title: "Pick strategy",
        description: "Choose from presets or build custom logic.",
    },
    {
        step: 3,
        title: "Simulate realism",
        description: "Apply fees, taxes, and liquidity constraints.",
    },
    {
        step: 4,
        title: "Inspect attribution",
        description: "Understand exactly where returns come from.",
    },
]

export function Timeline() {
    return (
        <section className="container py-24 bg-muted/30">
            <div className="mb-12 text-center">
                <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">Turn stories into strategies</h2>
                <p className="mt-4 text-lg text-muted-foreground">The journey from insight to execution.</p>
            </div>

            <div className="relative mx-auto max-w-4xl">
                {/* Vertical line for mobile, horizontal for desktop could be tricky, keeping it simple stack/grid for now */}
                <div className="grid gap-8 md:grid-cols-4 relative">
                    {/* Connecting line (desktop only) */}
                    <div className="hidden md:block absolute top-[24px] left-0 w-full h-0.5 bg-muted-foreground/20 -z-10" />

                    {steps.map((item, index) => (
                        <motion.div
                            key={item.step}
                            className="flex flex-col items-center text-center space-y-4"
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.5, delay: index * 0.1 }}
                            viewport={{ once: true }}
                        >
                            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-background border-2 border-primary text-xl font-bold text-primary shadow-sm z-10">
                                {item.step}
                            </div>
                            <h3 className="text-xl font-bold">{item.title}</h3>
                            <p className="text-sm text-muted-foreground">{item.description}</p>
                        </motion.div>
                    ))}
                </div>

                <div className="mt-16 flex justify-center gap-4">
                    <Button size="lg" asChild>
                        <Link href="/playground">Go to Playground</Link>
                    </Button>
                    <Button size="lg" variant="outline" asChild>
                        <Link href="/build">Build Strategy</Link>
                    </Button>
                </div>
            </div>
        </section>
    )
}
