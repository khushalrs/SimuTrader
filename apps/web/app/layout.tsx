import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { PageShell } from '@/components/layout/PageShell';
import { cn } from '@/lib/utils';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

export const metadata: Metadata = {
    title: 'SimuTrader',
    description: 'Portfolio-grade backtesting and simulation',
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className={cn(
                "min-h-screen bg-background font-sans antialiased",
                inter.variable
            )}>
                <PageShell>{children}</PageShell>
            </body>
        </html>
    );
}
