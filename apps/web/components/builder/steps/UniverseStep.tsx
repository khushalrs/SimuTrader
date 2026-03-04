"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"

export function UniverseStep({ config, updateConfig, nextStep }: any) {
    const [symbolInput, setSymbolInput] = useState("")
    const [error, setError] = useState<string | null>(null)

    const handleAddPreset = (type: string) => {
        setError(null);
        const newAssetClass = type === "US" ? "US_EQUITY" : "IN_EQUITY";
        const existingAssetClass = config.universe.instruments.length > 0 ? config.universe.instruments[0].asset_class : null;

        if (existingAssetClass && existingAssetClass !== newAssetClass) {
            setError(`Cannot mix different asset classes. Your universe already contains ${existingAssetClass} instruments.`);
            return;
        }

        let instruments: any[] = [];
        if (type === "US") {
            instruments = [
                { symbol: "AAPL", asset_class: "US_EQUITY" },
                { symbol: "MSFT", asset_class: "US_EQUITY" },
                { symbol: "GOOGL", asset_class: "US_EQUITY" }
            ]
        } else if (type === "IN") {
            instruments = [
                { symbol: "ALKEM", asset_class: "IN_EQUITY" },
                { symbol: "MRPL", asset_class: "IN_EQUITY" }
            ]
        }
        updateConfig((prev: any) => ({
            ...prev,
            universe: { ...prev.universe, instruments: [...prev.universe.instruments, ...instruments] }
        }))
    }

    const handleAddSymbol = (e: React.FormEvent) => {
        e.preventDefault()
        setError(null);
        if (!symbolInput.trim()) return;

        const symbol = symbolInput.trim().toUpperCase()
        const assetClass = symbol.endsWith(".NS") ? "IN_EQUITY" : (symbol.length === 6 && !symbol.includes(".") ? "FX" : "US_EQUITY")

        const existingAssetClass = config.universe.instruments.length > 0 ? config.universe.instruments[0].asset_class : null;
        if (existingAssetClass && existingAssetClass !== assetClass) {
            setError(`Cannot mix different asset classes. Your universe already contains ${existingAssetClass} instruments.`);
            return;
        }

        updateConfig((prev: any) => ({
            ...prev,
            universe: {
                ...prev.universe,
                instruments: [...prev.universe.instruments, { symbol, asset_class: assetClass }]
            }
        }))
        setSymbolInput("")
    }

    const handleRemoveSymbol = (index: number) => {
        updateConfig((prev: any) => {
            const newInst = [...prev.universe.instruments];
            newInst.splice(index, 1);
            return {
                ...prev,
                universe: { ...prev.universe, instruments: newInst }
            }
        });
    }

    return (
        <div className="p-6 flex flex-col h-full">
            <h2 className="text-xl font-semibold mb-4">Define Universe & Timeframe</h2>
            <div className="space-y-6 flex-1">

                <div className="space-y-2">
                    <label className="text-sm font-medium">Base Currency</label>
                    <select
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={config.universe.base_currency}
                        onChange={e => updateConfig((prev: any) => ({ ...prev, universe: { ...prev.universe, base_currency: e.target.value } }))}
                    >
                        <option value="USD">USD</option>
                        <option value="INR">INR</option>
                    </select>
                </div>

                <div className="space-y-2">
                    <label className="text-sm font-medium">Instruments</label>
                    <form onSubmit={handleAddSymbol} className="flex space-x-2">
                        <input
                            type="text"
                            placeholder="e.g. AAPL, RELIANCE.NS, USDINR"
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                            value={symbolInput}
                            onChange={e => setSymbolInput(e.target.value)}
                        />
                        <Button type="submit" variant="secondary">Add</Button>
                    </form>

                    <div className="flex space-x-2 mt-2">
                        <Button type="button" variant="outline" size="sm" onClick={() => handleAddPreset("US")}>+ US Mega Cap</Button>
                        <Button type="button" variant="outline" size="sm" onClick={() => handleAddPreset("IN")}>+ India Top</Button>
                    </div>

                    {error && (
                        <div className="text-sm text-destructive font-medium mt-2">
                            {error}
                        </div>
                    )}

                    <div className="mt-4 border border-border rounded-md p-4 min-h-[120px] bg-muted/30">
                        {config.universe.instruments.length === 0 ? (
                            <p className="text-sm text-muted-foreground text-center pt-8">No instruments added yet.</p>
                        ) : (
                            <div className="flex flex-wrap gap-2">
                                {config.universe.instruments.map((inst: any, idx: number) => (
                                    <div key={idx} className="bg-background border border-border rounded-full px-3 py-1 flex items-center text-sm space-x-2 shadow-sm">
                                        <span className="font-medium">{inst.symbol}</span>
                                        <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{inst.asset_class}</span>
                                        <button type="button" className="text-muted-foreground hover:text-destructive pl-1" onClick={() => handleRemoveSymbol(idx)}>×</button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Timeframe & Capital section */}
                <div className="space-y-4 pt-4 border-t border-border mt-6">
                    <h3 className="text-sm font-medium">Timeframe & Capital</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Start Date</label>
                            <input
                                type="date"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.backtest.start_date}
                                onChange={e => updateConfig((prev: any) => ({ ...prev, backtest: { ...prev.backtest, start_date: e.target.value } }))}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">End Date</label>
                            <input
                                type="date"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.backtest.end_date}
                                onChange={e => updateConfig((prev: any) => ({ ...prev, backtest: { ...prev.backtest, end_date: e.target.value } }))}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Initial Cash</label>
                            <input
                                type="number"
                                min="1"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.backtest.initial_cash}
                                onChange={e => updateConfig((prev: any) => ({ ...prev, backtest: { ...prev.backtest, initial_cash: e.target.value } }))}
                            />
                        </div>
                    </div>
                </div>

            </div>

            <div className="mt-8 flex justify-end pt-4 border-t border-border">
                <Button onClick={nextStep} disabled={config.universe.instruments.length === 0}>Next Step</Button>
            </div>
        </div>
    )
}
