import { Hero } from "@/components/landing/Hero"
import { MarketStories } from "@/components/landing/MarketStories"
import { Timeline } from "@/components/landing/Timeline"
import { CredibilityStrip } from "@/components/landing/CredibilityStrip"

export default function Home() {
    return (
        <main className="flex min-h-screen flex-col">
            <Hero />
            <MarketStories />
            <Timeline />
            <CredibilityStrip />
        </main>
    );
}
