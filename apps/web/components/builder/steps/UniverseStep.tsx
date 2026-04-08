"use client"

import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { searchAssets, AssetOut } from "@/lib/api"
import { Loader2, Search, AlertCircle } from "lucide-react"

export function UniverseStep({ config, updateConfig, nextStep }: any) {
    const [symbolInput, setSymbolInput] = useState("")
    const [debouncedInput, setDebouncedInput] = useState("")
    const [results, setResults] = useState<AssetOut[]>([])
    const [isSearching, setIsSearching] = useState(false)
    const [showDropdown, setShowDropdown] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [conflictAsset, setConflictAsset] = useState<AssetOut | null>(null)

    // Debounce manual input
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedInput(symbolInput)
        }, 300)
        return () => clearTimeout(timer)
    }, [symbolInput])

    // Search Assets
    useEffect(() => {
        if (!debouncedInput.trim()) {
            setResults([])
            setIsSearching(false)
            return
        }
        let active = true
        setIsSearching(true)
        searchAssets(debouncedInput.trim()).then(res => {
            if (active) {
                setResults(res)
                setIsSearching(false)
            }
        }).catch(() => {
            if (active) setIsSearching(false)
        })

        return () => { active = false }
    }, [debouncedInput])

    const handleAddPreset = (type: string) => {
        setError(null);
        setConflictAsset(null);
        const newAssetClass = type === "US" ? "US_EQUITY" : "IN_EQUITY";

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

    const validateAndAddAsset = (asset: AssetOut) => {
        setError(null);
        setConflictAsset(null);

        executeAddAsset(asset);
    }

    const executeAddAsset = (asset: AssetOut, clearExisting: boolean = false) => {
        updateConfig((prev: any) => {
            const currentInstruments = clearExisting ? [] : prev.universe.instruments;
            return {
                ...prev,
                universe: {
                    ...prev.universe,
                    instruments: [...currentInstruments, { symbol: asset.symbol, asset_class: asset.asset_class }]
                }
            }
        })
        setSymbolInput("")
        setShowDropdown(false)
        setConflictAsset(null)
    }

    const handleClearAndSwitch = () => {
        if (conflictAsset) {
            executeAddAsset(conflictAsset, true)
        }
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

    // Free text add
    const handleAddSymbolObj = (e: React.FormEvent) => {
        e.preventDefault()
        if (!symbolInput.trim()) return;
        // Check if there's an exact match in results
        const exactMatch = results.find(r => r.symbol.toUpperCase() === symbolInput.trim().toUpperCase())
        if (exactMatch) {
            validateAndAddAsset(exactMatch)
        } else {
            // Unrecognized text. We need backend confirmation.
            setError(`Unknown symbol: ${symbolInput.toUpperCase()}. Please select an instrument from the search results to ensure validity.`)
        }
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
                    <div className="flex items-center justify-between">
                        <label className="text-sm font-medium">Instruments</label>
                    </div>

                    <div className="relative">
                        <form onSubmit={handleAddSymbolObj} className="flex space-x-2">
                            <div className="relative w-full">
                                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                                <input
                                    type="text"
                                    placeholder="Search instruments (e.g. AAPL, Reliance...)"
                                    className="flex h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                    value={symbolInput}
                                    onChange={e => {
                                        setSymbolInput(e.target.value)
                                        setShowDropdown(true)
                                        setError(null)
                                        setConflictAsset(null)
                                    }}
                                    onFocus={() => setShowDropdown(true)}
                                />
                            </div>
                            <Button type="submit" variant="secondary">Add</Button>
                        </form>

                        {showDropdown && symbolInput.trim() && (
                            <div className="absolute top-12 left-0 w-[calc(100%-4rem)] bg-background border border-border shadow-lg z-50 rounded-md max-h-60 overflow-y-auto">
                                {isSearching ? (
                                    <div className="p-4 flex items-center justify-center text-muted-foreground text-sm">
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Searching...
                                    </div>
                                ) : results.length > 0 ? (
                                    <ul className="py-1 text-sm">
                                        {results.map((r, i) => (
                                            <li
                                                key={i}
                                                className="px-4 py-2 hover:bg-muted cursor-pointer flex justify-between items-center"
                                                onClick={() => validateAndAddAsset(r)}
                                            >
                                                <span>
                                                    <span className="font-semibold text-foreground mr-2">{r.symbol}</span>
                                                    <span className="text-muted-foreground">{r.name}</span>
                                                </span>
                                                <span className="text-xs bg-muted-foreground/20 text-muted-foreground px-1.5 py-0.5 rounded">
                                                    {r.asset_class}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <div className="p-4 text-muted-foreground text-sm text-center">
                                        No matches found for "{debouncedInput}"
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Conflict check removed */}

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
        </div >
    )
}
