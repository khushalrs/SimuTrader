import { Hero } from "@/components/landing/Hero"
import { MarketStories } from "@/components/landing/MarketStories"
import { Timeline } from "@/components/landing/Timeline"
import { CredibilityStrip } from "@/components/landing/CredibilityStrip"
import { PageIntro } from "@/components/help/PageIntro"

export default function Home() {
    return (
        <main className="flex min-h-screen flex-col">
            <div className="container max-w-7xl pt-4">
                <PageIntro slug="home" />
            </div>
            <Hero />
            <MarketStories />
            <Timeline />
            <CredibilityStrip />
        </main>
    );
}
