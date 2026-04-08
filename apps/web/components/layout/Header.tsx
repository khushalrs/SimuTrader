"use client"

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { getMarketSnapshot } from '@/lib/market';

const navItems = [
    { name: 'Playground', href: '/playground' },
    { name: 'Build', href: '/build_page' },
    { name: 'Explore', href: '/explore' },
    { name: 'Compare', href: '/compare' },
];

export function Header() {
    const pathname = usePathname();

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
                <div className="mr-4 hidden md:flex">
                    <Link href="/" className="mr-6 flex items-center space-x-2">
                        <span className="hidden font-bold sm:inline-block">SimuTrader</span>
                    </Link>
                    <nav className="flex items-center space-x-6 text-sm font-medium">
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
                        {/* Command menu place holder */}
                    </div>
                    <nav className="flex items-center">
                        {/* Github link or other actions */}
                    </nav>
                </div>
            </div>
        </header>
    );
}
