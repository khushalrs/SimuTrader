"use client"

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getMarketSnapshot } from '@/lib/market';
import { Menu, X, HelpCircle, Search } from 'lucide-react';
import { HelpCommandPalette } from '@/components/help/HelpCommandPalette';
import { SpotlightTour } from '@/components/help/SpotlightTour';
import { Button } from '@/components/ui/button';

const navItems = [
    { name: 'Playground', href: '/playground' },
    { name: 'Build', href: '/build_page' },
    { name: 'Explore', href: '/explore' },
    { name: 'Research Lab', href: '/research' },
    { name: 'Compare', href: '/compare' },
    { name: 'Runs', href: '/runs' },
    { name: 'Strategies', href: '/strategies' },
    { name: 'Guide & Help', href: '/guide' },
];

export function Header() {
    const pathname = usePathname();
    const [mobileOpen, setMobileOpen] = useState(false);

    const handleMouseEnter = (name: string) => {
        if (name === 'Explore') {
            getMarketSnapshot(["SPY", "QQQ", "IWM", "TLT", "GLD", "BTC"])
                .then(snap => {
                    try {
                        localStorage.setItem("marketSnapshot:last", JSON.stringify(snap));
                    } catch (e) {}
                })
                .catch(() => {});
        }
    };

    const triggerHelpPalette = () => {
        if (typeof window !== "undefined") {
            window.dispatchEvent(new Event("open-help-palette"))
        }
    }

    return (
        <>
            <SpotlightTour />
            <HelpCommandPalette />
            <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="container flex h-14 items-center">
                    <div className="mr-4 flex">
                        <Link href="/" aria-label="SimuTrader home" className="mr-6 flex items-center space-x-2">
                            <span className="hidden font-bold sm:inline-block">SimuTrader</span>
                        </Link>
                        {/* Desktop nav */}
                        <nav className="hidden md:flex items-center space-x-5 text-sm font-medium">
                            {navItems.map((item) => (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    onMouseEnter={() => handleMouseEnter(item.name)}
                                    className={cn(
                                        "transition-colors hover:text-foreground/80 text-xs font-semibold",
                                        pathname === item.href ? "text-foreground font-bold" : "text-foreground/60"
                                    )}
                                >
                                    {item.name}
                                </Link>
                            ))}
                        </nav>
                    </div>

                    <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
                        <div className="w-full flex-1 md:w-auto md:flex-none">
                            <Button
                                variant="outline"
                                size="sm"
                                className="h-8 text-xs font-mono text-muted-foreground hover:text-foreground gap-2 w-full md:w-auto justify-between md:justify-start"
                                onClick={triggerHelpPalette}
                            >
                                <span className="flex items-center gap-1.5">
                                    <Search className="w-3.5 h-3.5 text-primary" /> Search Help...
                                </span>
                                <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100">
                                    <span className="text-[10px]">⌘</span>K
                                </kbd>
                            </Button>
                        </div>
                        <nav className="flex items-center">
                            {/* Actions */}
                        </nav>
                        {/* Mobile hamburger */}
                        <button
                            className="md:hidden p-2 rounded-md hover:bg-muted"
                            aria-label={mobileOpen ? "Close menu" : "Open menu"}
                            onClick={() => setMobileOpen(prev => !prev)}
                        >
                            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                        </button>
                    </div>
                </div>

                {/* Mobile nav drawer */}
                {mobileOpen && (
                    <nav className="md:hidden border-t bg-background px-4 py-3 flex flex-col gap-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                onMouseEnter={() => handleMouseEnter(item.name)}
                                onClick={() => setMobileOpen(false)}
                                className={cn(
                                    "block px-3 py-2 rounded-md text-sm font-medium transition-colors hover:bg-muted",
                                    pathname === item.href ? "text-foreground bg-muted font-bold" : "text-foreground/60"
                                )}
                            >
                                {item.name}
                            </Link>
                        ))}
                    </nav>
                )}
            </header>
        </>
    );
}
