
export function CredibilityStrip() {
    return (
        <section className="border-t bg-muted/50 py-12">
            <div className="container flex flex-wrap justify-center gap-8 text-center sm:gap-16">
                <div className="flex flex-col gap-2">
                    <span className="text-4xl font-bold tracking-tighter">DuckDB</span>
                    <span className="text-sm text-muted-foreground font-medium uppercase tracking-wider">Fast Data Layer</span>
                </div>
                <div className="flex flex-col gap-2">
                    <span className="text-4xl font-bold tracking-tighter">Deterministic</span>
                    <span className="text-sm text-muted-foreground font-medium uppercase tracking-wider">Reproducible Runs</span>
                </div>
                <div className="flex flex-col gap-2">
                    <span className="text-4xl font-bold tracking-tighter">Multi-Asset</span>
                    <span className="text-sm text-muted-foreground font-medium uppercase tracking-wider">US • India • FX</span>
                </div>
                <div className="flex flex-col gap-2">
                    <span className="text-4xl font-bold tracking-tighter">Realistic</span>
                    <span className="text-sm text-muted-foreground font-medium uppercase tracking-wider">Costs & Taxes</span>
                </div>
            </div>
        </section>
    )
}
