"use client"

import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { searchAssets, getDataCoverage, type AssetOut } from "@/lib/api"
import { Loader2, Search, AlertCircle, ShieldAlert, Globe, Compass } from "lucide-react"
import { Badge } from "@/components/ui/badge"

export function UniverseStep({ config, updateConfig, nextStep }: any) {
    const [symbolInput, setSymbolInput] = useState("")
    const [debouncedInput, setDebouncedInput] = useState("")
    const [results, setResults] = useState<AssetOut[]>([])
    const [isSearching, setIsSearching] = useState(false)
    const [showDropdown, setShowDropdown] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [allocationMode, setAllocationMode] = useState<string>("equal_weight")
    const [coverageData, setCoverageData] = useState<any[]>([])
    const [isLoadingCoverage, setIsLoadingCoverage] = useState(false)

    const shortingEnabled = config.financing?.shorting?.enabled

    // Map asset class to currency & exchange
    const getAssetMetaData = (assetClass: string) => {
        if (assetClass?.startsWith("US_")) {
            return { currency: "USD", exchange: "NASDAQ" }
        } else if (assetClass?.startsWith("IN_")) {
            return { currency: "INR", exchange: "NSE" }
        } else {
            return { currency: "USD", exchange: "NYSE" }
        }
    }

    const handleBaseCurrencyChange = (baseCurrency: string) => {
        updateConfig((prev: any) => {
            const previousDefault = prev.universe.base_currency === "INR" ? "NIFTY" : "SPY"
            const nextDefault = baseCurrency === "INR" ? "NIFTY" : "SPY"
            return {
                ...prev,
                benchmark: prev.benchmark === previousDefault ? nextDefault : prev.benchmark,
                universe: { ...prev.universe, base_currency: baseCurrency },
            }
        })
    }

    // Determine initial allocationMode from instruments when step loads
    useEffect(() => {
        const instruments = config.universe.instruments
        if (instruments.length > 0) {
            if (instruments.some((i: any) => i.amount !== undefined)) {
                setAllocationMode("custom_amount")
            } else if (instruments.some((i: any) => i.weight !== undefined)) {
                setAllocationMode("custom_weight")
            } else {
                setAllocationMode("equal_weight")
            }
        }
    }, [config.universe.instruments])

    // Load coverage preview
    useEffect(() => {
        const symbols = config.universe.instruments.map((i: any) => i.symbol)
        if (symbols.length === 0) {
            setCoverageData([])
            return
        }
        setIsLoadingCoverage(true)
        getDataCoverage(symbols).then(res => {
            setCoverageData(res || [])
            setIsLoadingCoverage(false)
        }).catch(err => {
            console.error("Failed to load coverage preview:", err)
            setIsLoadingCoverage(false)
        })
    }, [config.universe.instruments])

    const handleAllocationModeChange = (mode: string) => {
        setAllocationMode(mode)
        updateConfig((prev: any) => {
            const count = prev.universe.instruments.length
            const newInst = prev.universe.instruments.map((inst: any) => {
                const cleaned = { symbol: inst.symbol, asset_class: inst.asset_class } as any
                const wasShort = (inst.weight ?? inst.amount ?? 1) < 0
                const sign = wasShort ? -1 : 1

                if (mode === "custom_weight" || mode === "equal_weight") {
                    cleaned.weight = count > 0 ? (sign * (1 / count)).toFixed(4) : (sign * 1.0).toFixed(4)
                } else if (mode === "custom_amount") {
                    cleaned.amount = count > 0 ? sign * Math.floor(parseFloat(prev.backtest.initial_cash) / count) : sign * prev.backtest.initial_cash
                }
                return cleaned
            })
            return {
                ...prev,
                universe: { ...prev.universe, instruments: newInst }
            }
        })
    }

    const handleValChange = (index: number, field: "weight" | "amount", val: string) => {
        let parsed = parseFloat(val)
        const isCurrentlyShort = (config.universe.instruments[index][field] ?? 1) < 0
        
        // Retain sign unless shorting is disabled
        if (!shortingEnabled && parsed < 0) {
            parsed = Math.abs(parsed)
        }
        
        // If parsed is positive but they are short, match sign
        if (isCurrentlyShort && parsed > 0) {
            parsed = -parsed
        }

        updateConfig((prev: any) => {
            const newInst = [...prev.universe.instruments]
            newInst[index] = {
                ...newInst[index],
                [field]: isNaN(parsed) ? "" : parsed
            }
            return {
                ...prev,
                universe: { ...prev.universe, instruments: newInst }
            }
        })
    }

    // Toggle Long/Short sign
    const handleToggleSide = (index: number) => {
        updateConfig((prev: any) => {
            const newInst = [...prev.universe.instruments]
            const inst = newInst[index]
            
            if (allocationMode === "custom_amount") {
                const amt = inst.amount ?? 0
                inst.amount = -amt
            } else {
                const wt = parseFloat(inst.weight ?? 0)
                inst.weight = (-wt).toFixed(4)
            }

            return {
                ...prev,
                universe: { ...prev.universe, instruments: newInst }
            }
        })
    }

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
        setError(null)
        let newInstruments: any[] = []
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
            const nextInstruments = [...prev.universe.instruments, ...newInstruments]
            const formatted = nextInstruments.map((inst: any) => {
                const cleaned = { symbol: inst.symbol, asset_class: inst.asset_class } as any
                if (allocationMode === "custom_weight") {
                    cleaned.weight = inst.weight !== undefined ? inst.weight : (1 / nextInstruments.length).toFixed(4)
                } else if (allocationMode === "custom_amount") {
                    cleaned.amount = inst.amount !== undefined ? inst.amount : Math.floor(parseFloat(prev.backtest.initial_cash) / nextInstruments.length)
                } else if (allocationMode === "equal_weight") {
                    cleaned.weight = (1 / nextInstruments.length).toFixed(4)
                }
                return cleaned
            })
            return {
                ...prev,
                universe: { ...prev.universe, instruments: formatted }
            }
        })
    }

    const validateAndAddAsset = (asset: AssetOut) => {
        setError(null)
        executeAddAsset(asset)
    }

    const executeAddAsset = (asset: AssetOut, clearExisting: boolean = false) => {
        updateConfig((prev: any) => {
            const currentInstruments = clearExisting ? [] : prev.universe.instruments
            const newInstItem = { symbol: asset.symbol, asset_class: asset.asset_class } as any
            const nextInstruments = [...currentInstruments, newInstItem]
            
            const formattedInstruments = nextInstruments.map((inst: any) => {
                const cleaned = { symbol: inst.symbol, asset_class: inst.asset_class } as any
                if (allocationMode === "custom_weight") {
                    cleaned.weight = inst.weight !== undefined ? inst.weight : (1 / nextInstruments.length).toFixed(4)
                } else if (allocationMode === "custom_amount") {
                    cleaned.amount = inst.amount !== undefined ? inst.amount : Math.floor(parseFloat(prev.backtest.initial_cash) / nextInstruments.length)
                } else if (allocationMode === "equal_weight") {
                    cleaned.weight = (1 / nextInstruments.length).toFixed(4)
                }
                return cleaned
            })

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
    }

    const handleRemoveSymbol = (index: number) => {
        updateConfig((prev: any) => {
            const nextInstruments = [...prev.universe.instruments]
            nextInstruments.splice(index, 1)
            
            const formatted = nextInstruments.map((inst: any) => {
                const cleaned = { ...inst } as any
                if (allocationMode === "equal_weight") {
                    cleaned.weight = nextInstruments.length > 0 ? (1 / nextInstruments.length).toFixed(4) : "1.0000"
                }
                return cleaned
            })
            
            return {
                ...prev,
                universe: { ...prev.universe, instruments: formatted }
            }
        })
    }

    const handleAddSymbolObj = (e: React.FormEvent) => {
        e.preventDefault()
        if (!symbolInput.trim()) return
        const exactMatch = results.find(r => r.symbol.toUpperCase() === symbolInput.trim().toUpperCase())
        if (exactMatch) {
            validateAndAddAsset(exactMatch)
        } else {
            setError(`Unknown symbol: ${symbolInput.toUpperCase()}. Please select an instrument from the search results to ensure validity.`)
        }
    }

    const hasShortPositions = config.universe.instruments.some((i: any) => {
        const val = i.weight ?? i.amount ?? 0
        return val < 0
    })

    return (
        <div className="p-6 flex flex-col h-full space-y-6">
            <div>
                <h2 className="text-xl font-bold tracking-tight">Define Asset Universe & Timeframe</h2>
                <p className="text-xs text-muted-foreground mt-1">
                    Assemble strategy target symbols, assign weights or initial cash allocations, configure base currency, and preview validation coverage.
                </p>
            </div>

            <div className="space-y-6 flex-1 text-sm">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <label className="text-xs font-semibold uppercase text-muted-foreground">Base Currency</label>
                        <select
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            value={config.universe.base_currency}
                            onChange={e => handleBaseCurrencyChange(e.target.value)}
                        >
                            <option value="USD">USD (United States Dollar)</option>
                            <option value="INR">INR (Indian Rupee)</option>
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label className="text-xs font-semibold uppercase text-muted-foreground">Benchmark Index</label>
                        <input
                            type="text"
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm uppercase focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            value={config.benchmark ?? ""}
                            placeholder={config.universe.base_currency === "INR" ? "NIFTY" : "SPY"}
                            onChange={e => updateConfig((prev: any) => ({
                                ...prev,
                                benchmark: e.target.value.toUpperCase(),
                            }))}
                        />
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase text-muted-foreground">Instruments Selector</label>
                    <div className="relative">
                        <form onSubmit={handleAddSymbolObj} className="flex space-x-2">
                            <div className="relative w-full">
                                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                                <input
                                    type="text"
                                    placeholder="Search equity asset symbols (e.g. AAPL, RELIANCE)..."
                                    className="flex h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={symbolInput}
                                    onChange={e => {
                                        setSymbolInput(e.target.value)
                                        setShowDropdown(true)
                                        setError(null)
                                    }}
                                    onFocus={() => setShowDropdown(true)}
                                />
                            </div>
                            <Button type="submit" variant="secondary">Add Asset</Button>
                        </form>

                        {showDropdown && symbolInput.trim() && (
                            <div className="absolute top-12 left-0 w-[calc(100%-4rem)] bg-background border border-border shadow-lg z-50 rounded-md max-h-60 overflow-y-auto">
                                {isSearching ? (
                                    <div className="p-4 flex items-center justify-center text-muted-foreground text-xs">
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Searching...
                                    </div>
                                ) : results.length > 0 ? (
                                    <ul className="py-1 text-xs">
                                        {results.map((r, i) => {
                                            const meta = getAssetMetaData(r.asset_class)
                                            return (
                                                <li
                                                    key={i}
                                                    className="px-4 py-2 hover:bg-muted cursor-pointer flex justify-between items-center"
                                                    onClick={() => validateAndAddAsset(r)}
                                                >
                                                    <span>
                                                        <span className="font-semibold text-foreground mr-2">{r.symbol}</span>
                                                        <span className="text-muted-foreground">{r.name}</span>
                                                    </span>
                                                    <div className="flex gap-1.5">
                                                        <Badge variant="outline" className="text-[10px] py-0">{meta.currency}</Badge>
                                                        <Badge variant="outline" className="text-[10px] py-0 bg-primary/5">{meta.exchange}</Badge>
                                                    </div>
                                                </li>
                                            )
                                        })}
                                    </ul>
                                ) : (
                                    <div className="p-4 text-muted-foreground text-xs text-center">
                                        No matches found for "{debouncedInput}"
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="flex space-x-2 mt-2">
                        <Button type="button" variant="outline" size="sm" className="text-xs" onClick={() => handleAddPreset("US")}>+ US Mega Cap</Button>
                        <Button type="button" variant="outline" size="sm" className="text-xs" onClick={() => handleAddPreset("IN")}>+ India Nifty</Button>
                    </div>

                    {error && (
                        <p className="text-xs text-rose-500 font-semibold mt-2">{error}</p>
                    )}
                </div>

                <div className="space-y-4 pt-4 border-t border-border mt-4">
                    <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold uppercase text-muted-foreground">Allocation Distribution Mode</label>
                        <select
                            className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            value={allocationMode}
                            onChange={(e) => handleAllocationModeChange(e.target.value)}
                        >
                            <option value="equal_weight">Equal Weight Allocation</option>
                            <option value="custom_weight">Custom Weight %</option>
                            <option value="custom_amount">Custom Base Cash Amount</option>
                        </select>
                    </div>

                    {/* Instruments List with currency, exchange, long/short toggler */}
                    <div className="border border-border rounded-xl overflow-hidden bg-muted/10 min-h-[120px]">
                        {config.universe.instruments.length === 0 ? (
                            <p className="text-xs text-muted-foreground text-center py-12">No instruments added. Search and add symbols above to define your universe.</p>
                        ) : (
                            <div className="divide-y divide-border">
                                {config.universe.instruments.map((inst: any, idx: number) => {
                                    const meta = getAssetMetaData(inst.asset_class)
                                    const val = inst.weight ?? inst.amount ?? 0
                                    const isShort = val < 0
                                    const absVal = Math.abs(val)

                                    return (
                                        <div key={idx} className="flex items-center justify-between p-3.5 hover:bg-muted/30 transition-colors text-xs">
                                            <div className="flex items-center space-x-3">
                                                <span className="font-bold text-foreground text-sm">{inst.symbol}</span>
                                                <div className="flex gap-1">
                                                    <Badge variant="outline" className="text-[9px] py-0 px-1">{meta.currency}</Badge>
                                                    <Badge variant="outline" className="text-[9px] py-0 px-1 bg-secondary">{meta.exchange}</Badge>
                                                </div>
                                            </div>
                                            
                                            <div className="flex items-center space-x-3.5">
                                                {/* Long/Short toggle */}
                                                <button
                                                    type="button"
                                                    onClick={() => handleToggleSide(idx)}
                                                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition-all duration-200 ${
                                                        isShort 
                                                        ? "bg-rose-500/10 text-rose-600 border border-rose-500/25 hover:bg-rose-500/20" 
                                                        : "bg-emerald-500/10 text-emerald-600 border border-emerald-500/25 hover:bg-emerald-500/20"
                                                    }`}
                                                >
                                                    {isShort ? "SHORT" : "LONG"}
                                                </button>

                                                {allocationMode === "equal_weight" && (
                                                    <span className="text-xs font-mono bg-secondary/80 px-2.5 py-1 rounded">
                                                        {isShort ? "-" : ""}{(100 / config.universe.instruments.length).toFixed(1)}%
                                                    </span>
                                                )}
                                                {allocationMode === "custom_weight" && (
                                                    <div className="flex items-center space-x-1">
                                                        <input
                                                            type="number"
                                                            step="0.01"
                                                            placeholder="Weight"
                                                            className="w-16 h-8 rounded border bg-background px-2 text-center text-xs focus:ring-1 focus:ring-primary focus:outline-none"
                                                            value={absVal || ""}
                                                            onChange={(e) => handleValChange(idx, "weight", e.target.value)}
                                                        />
                                                        <span className="text-muted-foreground">%</span>
                                                    </div>
                                                )}
                                                {allocationMode === "custom_amount" && (
                                                    <div className="flex items-center space-x-1">
                                                        <span className="text-muted-foreground">{meta.currency === "INR" ? "₹" : "$"}</span>
                                                        <input
                                                            type="number"
                                                            placeholder="Amount"
                                                            className="w-20 h-8 rounded border bg-background px-2 text-center text-xs focus:ring-1 focus:ring-primary focus:outline-none"
                                                            value={absVal || ""}
                                                            onChange={(e) => handleValChange(idx, "amount", e.target.value)}
                                                        />
                                                    </div>
                                                )}
                                                <button 
                                                    type="button" 
                                                    className="text-muted-foreground hover:text-rose-500 p-1 text-sm font-bold ml-1 transition-colors" 
                                                    onClick={() => handleRemoveSymbol(idx)}
                                                >
                                                    ×
                                                </button>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        )}
                    </div>

                    {/* Warning checks */}
                    {hasShortPositions && !shortingEnabled && (
                        <div className="flex items-center space-x-2 text-xs text-amber-600 bg-amber-50 border border-amber-200 dark:bg-amber-950/20 dark:border-amber-900 p-3 rounded-md">
                            <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
                            <span>Warning: Short positions require shorting to be enabled in step 3 (Realism Knobs) to pass validation.</span>
                        </div>
                    )}
                </div>

                {/* Coverage Preview Widget */}
                {config.universe.instruments.length > 0 && (
                    <div className="border border-border/80 rounded-xl p-4 bg-muted/5 shadow-sm space-y-3">
                        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                            <Globe className="w-3.5 h-3.5 text-blue-500" /> Historical Data Coverage Preview
                        </h4>
                        {isLoadingCoverage ? (
                            <div className="flex items-center space-x-2 text-xs text-muted-foreground py-2">
                                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                                <span>Loading historical data coverage ranges...</span>
                            </div>
                        ) : coverageData.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No historical data coverage details available for selected universe.</p>
                        ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                                {coverageData.map((cov: any, idx: number) => (
                                    <div key={idx} className="flex justify-between items-center p-2 rounded bg-background border border-border/40">
                                        <span className="font-bold text-foreground">{cov.symbol}</span>
                                        <span className="text-[11px] text-muted-foreground">
                                            {cov.start_date || cov.coverage_start || "-"} to {cov.end_date || cov.coverage_end || "-"}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Timeframe & Capital section */}
                <div className="space-y-4 pt-4 border-t border-border mt-6">
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider flex items-center gap-1.5">
                        <Compass className="w-4 h-4 text-indigo-500" /> Backtest Timeline & Cash
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-xs text-muted-foreground font-semibold">Start Date</label>
                            <input
                                type="date"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.backtest.start_date}
                                onChange={e => updateConfig((prev: any) => ({ ...prev, backtest: { ...prev.backtest, start_date: e.target.value } }))}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-xs text-muted-foreground font-semibold">End Date</label>
                            <input
                                type="date"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.backtest.end_date}
                                onChange={e => updateConfig((prev: any) => ({ ...prev, backtest: { ...prev.backtest, end_date: e.target.value } }))}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-xs text-muted-foreground font-semibold">Initial Capital</label>
                            <input
                                type="number"
                                min="1"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
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
