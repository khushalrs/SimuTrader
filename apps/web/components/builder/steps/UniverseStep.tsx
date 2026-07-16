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

    const [allocationMode, setAllocationMode] = useState<string>("equal_weight")
    const shortingEnabled = config.financing?.shorting?.enabled;

    // Determine initial allocationMode from instruments when step loads
    useEffect(() => {
        const instruments = config.universe.instruments;
        if (instruments.length > 0) {
            if (instruments.some((i: any) => i.amount !== undefined)) {
                setAllocationMode("custom_amount");
            } else if (instruments.some((i: any) => i.weight !== undefined)) {
                // If it is custom weights, they might not sum perfectly to 1 or have variations.
                // Let's assume custom if they already have weights.
                setAllocationMode("custom_weight");
            } else {
                setAllocationMode("equal_weight");
            }
        }
    }, [config.universe.instruments]);

    const handleAllocationModeChange = (mode: string) => {
        setAllocationMode(mode);
        updateConfig((prev: any) => {
            const count = prev.universe.instruments.length;
            const newInst = prev.universe.instruments.map((inst: any) => {
                const cleaned = { symbol: inst.symbol, asset_class: inst.asset_class } as any;
                if (mode === "custom_weight" || mode === "equal_weight") {
                    cleaned.weight = count > 0 ? (1 / count).toFixed(4) : "1.0000";
                } else if (mode === "custom_amount") {
                    cleaned.amount = count > 0 ? Math.floor(parseFloat(prev.backtest.initial_cash) / count) : prev.backtest.initial_cash;
                }
                return cleaned;
            });
            return {
                ...prev,
                universe: { ...prev.universe, instruments: newInst }
            };
        });
    }

    const handleValChange = (index: number, field: "weight" | "amount", val: string) => {
        let parsed = parseFloat(val);
        if (!isNaN(parsed)) {
            if (!shortingEnabled && parsed < 0) {
                parsed = 0;
            }
        }
        updateConfig((prev: any) => {
            const newInst = [...prev.universe.instruments];
            newInst[index] = {
                ...newInst[index],
                [field]: isNaN(parsed) ? "" : parsed
            };
            return {
                ...prev,
                universe: { ...prev.universe, instruments: newInst }
            };
        });
    };

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

        let newInstruments: any[] = [];
        if (type === "US") {
            newInstruments = [
                { symbol: "AAPL", asset_class: "US_EQUITY" },
                { symbol: "MSFT", asset_class: "US_EQUITY" },
                { symbol: "GOOGL", asset_class: "US_EQUITY" }
            ]
        } else if (type === "IN") {
            newInstruments = [
                { symbol: "ALKEM", asset_class: "IN_EQUITY" },
                { symbol: "MRPL", asset_class: "IN_EQUITY" }
            ]
        }

        updateConfig((prev: any) => {
            const nextInstruments = [...prev.universe.instruments, ...newInstruments];
            const formatted = nextInstruments.map((inst: any) => {
                const cleaned = { symbol: inst.symbol, asset_class: inst.asset_class } as any;
                if (allocationMode === "custom_weight") {
                    cleaned.weight = inst.weight !== undefined ? inst.weight : (1 / nextInstruments.length).toFixed(4);
                } else if (allocationMode === "custom_amount") {
                    cleaned.amount = inst.amount !== undefined ? inst.amount : Math.floor(parseFloat(prev.backtest.initial_cash) / nextInstruments.length);
                } else if (allocationMode === "equal_weight") {
                    cleaned.weight = (1 / nextInstruments.length).toFixed(4);
                }
                return cleaned;
            });
            return {
                ...prev,
                universe: { ...prev.universe, instruments: formatted }
            }
        });
    }

    const validateAndAddAsset = (asset: AssetOut) => {
        setError(null);
        setConflictAsset(null);

        executeAddAsset(asset);
    }

    const executeAddAsset = (asset: AssetOut, clearExisting: boolean = false) => {
        updateConfig((prev: any) => {
            const currentInstruments = clearExisting ? [] : prev.universe.instruments;
            const newInstItem = { symbol: asset.symbol, asset_class: asset.asset_class } as any;
            const nextInstruments = [...currentInstruments, newInstItem];
            
            const formattedInstruments = nextInstruments.map((inst: any) => {
                const cleaned = { symbol: inst.symbol, asset_class: inst.asset_class } as any;
                if (allocationMode === "custom_weight") {
                    cleaned.weight = inst.weight !== undefined ? inst.weight : (1 / nextInstruments.length).toFixed(4);
                } else if (allocationMode === "custom_amount") {
                    cleaned.amount = inst.amount !== undefined ? inst.amount : Math.floor(parseFloat(prev.backtest.initial_cash) / nextInstruments.length);
                } else if (allocationMode === "equal_weight") {
                    cleaned.weight = (1 / nextInstruments.length).toFixed(4);
                }
                return cleaned;
            });

            return {
                ...prev,
                universe: {
                    ...prev.universe,
                    instruments: formattedInstruments
                }
            }
        })
        setSymbolInput("")
        setShowDropdown(false)
        setConflictAsset(null)
    }

    const handleRemoveSymbol = (index: number) => {
        updateConfig((prev: any) => {
            const nextInstruments = [...prev.universe.instruments];
            nextInstruments.splice(index, 1);
            
            const formatted = nextInstruments.map((inst: any) => {
                const cleaned = { ...inst } as any;
                if (allocationMode === "equal_weight") {
                    cleaned.weight = nextInstruments.length > 0 ? (1 / nextInstruments.length).toFixed(4) : "1.0000";
                }
                return cleaned;
            });
            
            return {
                ...prev,
                universe: { ...prev.universe, instruments: formatted }
            }
        });
    }

    const handleAddSymbolObj = (e: React.FormEvent) => {
        e.preventDefault()
        if (!symbolInput.trim()) return;
        const exactMatch = results.find(r => r.symbol.toUpperCase() === symbolInput.trim().toUpperCase())
        if (exactMatch) {
            validateAndAddAsset(exactMatch)
        } else {
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

                    <div className="flex space-x-2 mt-2">
                        <Button type="button" variant="outline" size="sm" onClick={() => handleAddPreset("US")}>+ US Mega Cap</Button>
                        <Button type="button" variant="outline" size="sm" onClick={() => handleAddPreset("IN")}>+ India Top</Button>
                    </div>

                    {error && (
                        <div className="text-sm text-destructive font-medium mt-2">
                            {error}
                        </div>
                    )}
                </div>

                <div className="space-y-4 pt-4 border-t border-border mt-4">
                    <div className="flex items-center justify-between">
                        <label className="text-sm font-medium">Allocation Mode</label>
                        <select
                            className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            value={allocationMode}
                            onChange={(e) => handleAllocationModeChange(e.target.value)}
                        >
                            <option value="equal_weight">Equal Weight</option>
                            <option value="custom_weight">Custom Weight</option>
                            <option value="custom_amount">Custom Amount</option>
                        </select>
                    </div>

                    <div className="border border-border rounded-md overflow-hidden bg-muted/10 min-h-[120px]">
                        {config.universe.instruments.length === 0 ? (
                            <p className="text-sm text-muted-foreground text-center py-12">No instruments added yet.</p>
                        ) : (
                            <div className="divide-y divide-border">
                                {config.universe.instruments.map((inst: any, idx: number) => (
                                    <div key={idx} className="flex items-center justify-between p-3 hover:bg-muted/30 transition-colors text-sm">
                                        <div className="flex items-center space-x-3">
                                            <span className="font-semibold text-foreground">{inst.symbol}</span>
                                            <span className="text-xs text-muted-foreground bg-secondary/80 px-2 py-0.5 rounded-full">{inst.asset_class}</span>
                                        </div>
                                        
                                        <div className="flex items-center space-x-3">
                                            {allocationMode === "equal_weight" && (
                                                <span className="text-xs font-mono bg-secondary px-2.5 py-1 rounded">
                                                    {(100 / config.universe.instruments.length).toFixed(1)}%
                                                </span>
                                            )}
                                            {allocationMode === "custom_weight" && (
                                                <div className="flex items-center space-x-1.5">
                                                    <input
                                                        type="number"
                                                        step="0.01"
                                                        placeholder="Weight"
                                                        className="w-20 h-8 rounded border bg-background px-2 text-center text-xs focus:ring-1 focus:ring-primary focus:outline-none"
                                                        value={inst.weight ?? ""}
                                                        onChange={(e) => handleValChange(idx, "weight", e.target.value)}
                                                    />
                                                    <span className="text-xs text-muted-foreground">weight</span>
                                                </div>
                                            )}
                                            {allocationMode === "custom_amount" && (
                                                <div className="flex items-center space-x-1.5">
                                                    <span className="text-xs text-muted-foreground">$</span>
                                                    <input
                                                        type="number"
                                                        placeholder="Amount"
                                                        className="w-24 h-8 rounded border bg-background px-2 text-center text-xs focus:ring-1 focus:ring-primary focus:outline-none"
                                                        value={inst.amount ?? ""}
                                                        onChange={(e) => handleValChange(idx, "amount", e.target.value)}
                                                    />
                                                </div>
                                            )}
                                            <button 
                                                type="button" 
                                                className="text-muted-foreground hover:text-destructive p-1 transition-colors ml-2" 
                                                onClick={() => handleRemoveSymbol(idx)}
                                            >
                                                ×
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                    {!shortingEnabled && config.universe.instruments.some((i: any) => parseFloat(i.weight || i.amount || 0) < 0) && (
                        <div className="flex items-center space-x-2 text-xs text-amber-600 bg-amber-50 border border-amber-200 p-2.5 rounded-md">
                            <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
                            <span>Negative allocations require shorting enabled in Step 3 (Realism).</span>
                        </div>
                    )}
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
