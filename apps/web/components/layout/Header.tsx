"use client"

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getMarketSnapshot } from '@/lib/market';
import { Menu, X } from 'lucide-react';

const navItems = [
    { name: 'Playground', href: '/playground' },
    { name: 'Build', href: '/build_page' },
    { name: 'Explore', href: '/explore' },
    { name: 'Compare', href: '/compare' },
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

    return (
        <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-14 items-center">
                <div className="mr-4 flex">
                    <Link href="/" aria-label="SimuTrader home" className="mr-6 flex items-center space-x-2">
                        <span className="hidden font-bold sm:inline-block">SimuTrader</span>
                    </Link>
                    {/* Desktop nav */}
                    <nav className="hidden md:flex items-center space-x-6 text-sm font-medium">
                        {navItems.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                onMouseEnter={() => handleMouseEnter(item.name)}
                                className={cn(
                                    "transition-colors hover:text-foreground/80",
                                    pathname === item.href ? "text-foreground" : "text-foreground/60"
                                )}
                            >
                                {item.name}
                            </Link>
                        ))}
                    </nav>
                </div>

                <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
                    <div className="w-full flex-1 md:w-auto md:flex-none">
                        {/* Command menu placeholder */}
                    </div>
                    <nav className="flex items-center">
                        {/* GitHub link or other actions */}
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
                                pathname === item.href ? "text-foreground bg-muted" : "text-foreground/60"
                            )}
                        >
                            {item.name}
                        </Link>
                    ))}
                </nav>
            )}
        </header>
    );
}
