"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Scale, Receipt, ShieldCheck, TrendingUp } from "lucide-react"

export function RealismStep({ config, updateConfig, nextStep, prevStep }: any) {
    const [feePreset, setFeePreset] = useState<"free" | "low" | "high" | "custom">("low")
    const [taxPreset, setTaxPreset] = useState<"none" | "us" | "india" | "custom">("none")

    // Set initial preset selections based on values in config
    useEffect(() => {
        const comm = config.execution?.commission?.bps ?? 0
        const slip = config.execution?.slippage?.bps ?? 0
        const regime = config.tax?.regime || "NONE"

        // Deduce fee preset
        if (comm === 0 && slip === 0) {
            setFeePreset("free")
        } else if (comm === 1 && slip === 2) {
            setFeePreset("low")
        } else if (comm === 10 && slip === 15) {
            setFeePreset("high")
        } else {
            setFeePreset("custom")
        }

        // Deduce tax preset
        if (regime === "NONE") {
            setTaxPreset("none")
        } else if (regime === "US") {
            setTaxPreset("us")
        } else if (regime === "INDIA") {
            setTaxPreset("india")
        } else {
            setTaxPreset("custom")
        }
    }, [config])

    // Handlers for Execution preset selection
    const handleSelectFeePreset = (preset: "free" | "low" | "high" | "custom") => {
        setFeePreset(preset)
        if (preset === "free") {
            updateConfig((prev: any) => ({
                ...prev,
                execution: {
                    ...prev.execution,
                    commission: { ...prev.execution.commission, bps: 0 },
                    slippage: { ...prev.execution.slippage, bps: 0 }
                }
            }))
        } else if (preset === "low") {
            updateConfig((prev: any) => ({
                ...prev,
                execution: {
                    ...prev.execution,
                    commission: { ...prev.execution.commission, bps: 1 },
                    slippage: { ...prev.execution.slippage, bps: 2 }
                }
            }))
        } else if (preset === "high") {
            updateConfig((prev: any) => ({
                ...prev,
                execution: {
                    ...prev.execution,
                    commission: { ...prev.execution.commission, bps: 10 },
                    slippage: { ...prev.execution.slippage, bps: 15 }
                }
            }))
        }
    }

    const handleSelectTaxPreset = (preset: "none" | "us" | "india" | "custom") => {
        setTaxPreset(preset)
        if (preset === "none") {
            updateConfig((prev: any) => ({
                ...prev,
                tax: { ...prev.tax, regime: "NONE" }
            }))
        } else if (preset === "us") {
            updateConfig((prev: any) => ({
                ...prev,
                tax: { ...prev.tax, regime: "US" }
            }))
        } else if (preset === "india") {
            updateConfig((prev: any) => ({
                ...prev,
                tax: { ...prev.tax, regime: "INDIA" }
            }))
        }
    }

    // Direct input handlers
    const setCommission = (bps: number) => {
        setFeePreset("custom")
        updateConfig((prev: any) => ({
            ...prev, execution: { ...prev.execution, commission: { ...prev.execution.commission, bps } }
        }))
    }

    const setSlippage = (bps: number) => {
        setFeePreset("custom")
        updateConfig((prev: any) => ({
            ...prev, execution: { ...prev.execution, slippage: { ...prev.execution.slippage, bps } }
        }))
    }

    const toggleMargin = (enabled: boolean) => {
        updateConfig((prev: any) => ({
            ...prev, financing: { ...prev.financing, margin: { ...prev.financing.margin, enabled } }
        }))
    }

    const toggleShorting = (enabled: boolean) => {
        updateConfig((prev: any) => ({
            ...prev, financing: { ...prev.financing, shorting: { ...prev.financing.shorting, enabled } }
        }))
    }

    return (
        <div className="p-6 flex flex-col h-full space-y-6 text-sm">
            <div>
                <h2 className="text-xl font-bold tracking-tight">Realism & Cost Friction Knobs</h2>
                <p className="text-xs text-muted-foreground mt-1">
                    Select presets or customize execution costs, financing constraints, leverage parameters, and tax regimes.
                </p>
            </div>

            <div className="space-y-6 flex-1">
                {/* Fee Presets Cards */}
                <div className="space-y-3">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5 pb-1 border-b">
                        <Scale className="w-3.5 h-3.5 text-primary" /> Execution Fee Presets
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {/* Free Card */}
                        <div 
                            onClick={() => handleSelectFeePreset("free")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${feePreset === "free" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">Free Preset</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">0 bps Commission / 0 bps Slippage</span>
                        </div>

                        {/* Low Cost Card */}
                        <div 
                            onClick={() => handleSelectFeePreset("low")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${feePreset === "low" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">Low Friction</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">1 bps Commission / 2 bps Slippage</span>
                        </div>

                        {/* High Cost Card */}
                        <div 
                            onClick={() => handleSelectFeePreset("high")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${feePreset === "high" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">High Friction</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">10 bps Commission / 15 bps Slippage</span>
                        </div>

                        {/* Custom Card */}
                        <div 
                            onClick={() => handleSelectFeePreset("custom")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${feePreset === "custom" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">Custom Setup</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">Define execution costs manually below</span>
                        </div>
                    </div>

                    {/* Manual Fee Inputs */}
                    {feePreset === "custom" && (
                        <div className="grid grid-cols-2 gap-4 p-3 bg-muted/20 border border-border/80 rounded-xl animate-in fade-in duration-200 mt-2">
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-muted-foreground uppercase">Commission BPS</label>
                                <input
                                    type="number"
                                    step="0.5"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.execution.commission.bps}
                                    onChange={e => setCommission(parseFloat(e.target.value) || 0)}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-muted-foreground uppercase">Slippage BPS</label>
                                <input
                                    type="number"
                                    step="0.5"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.execution.slippage.bps}
                                    onChange={e => setSlippage(parseFloat(e.target.value) || 0)}
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* Tax Presets Cards */}
                <div className="space-y-3">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5 pb-1 border-b">
                        <Receipt className="w-3.5 h-3.5 text-rose-500" /> Tax Regime Presets
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {/* None Tax */}
                        <div 
                            onClick={() => handleSelectTaxPreset("none")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${taxPreset === "none" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">No Taxes</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">Tax-advantaged holdings (NONE)</span>
                        </div>

                        {/* US Tax */}
                        <div 
                            onClick={() => handleSelectTaxPreset("us")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${taxPreset === "us" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">United States</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">Short/Long-term FIFO taxation (US)</span>
                        </div>

                        {/* India Tax */}
                        <div 
                            onClick={() => handleSelectTaxPreset("india")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${taxPreset === "india" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">India (STCG/LTCG)</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">Indian Rupee income taxation (INDIA)</span>
                        </div>

                        {/* Custom Tax */}
                        <div 
                            onClick={() => handleSelectTaxPreset("custom")}
                            className={`p-3 border rounded-xl cursor-pointer transition-all hover:bg-muted/30 select-none flex flex-col justify-between min-h-[75px] ${taxPreset === "custom" ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "bg-card"}`}
                        >
                            <span className="font-semibold text-foreground text-xs">Other / Custom</span>
                            <span className="text-[10px] text-muted-foreground mt-1 block">Choose and configure details manually</span>
                        </div>
                    </div>

                    {/* Manual Tax Select */}
                    {taxPreset === "custom" && (
                        <div className="p-3 bg-muted/20 border border-border/80 rounded-xl animate-in fade-in duration-200 mt-2">
                            <label className="text-[10px] font-semibold text-muted-foreground uppercase">Custom Tax Regime</label>
                            <select
                                className="flex h-9 w-full md:w-1/2 rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring mt-1.5"
                                value={config.tax.regime || "NONE"}
                                onChange={e => updateConfig((prev: any) => ({ ...prev, tax: { ...prev.tax, regime: e.target.value } }))}
                            >
                                <option value="US">US (IRS FIFO buckets)</option>
                                <option value="INDIA">India (STCG/LTCG FIFO)</option>
                                <option value="GERMANY">Germany (Flat Abgeltungsteuer)</option>
                                <option value="NONE">None (Tax Advantaged)</option>
                            </select>
                        </div>
                    )}
                </div>

                {/* Financing */}
                <div className="space-y-3">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5 pb-1 border-b">
                        <TrendingUp className="w-3.5 h-3.5 text-indigo-500" /> Margin Financing & Short Borrowing
                    </h3>
                    <div className="flex flex-col space-y-4">
                        <label className="flex items-center space-x-3 cursor-pointer">
                            <input
                                type="checkbox"
                                className="w-4 h-4 rounded border-input text-primary focus:ring-primary"
                                checked={config.financing.margin.enabled || false}
                                onChange={e => toggleMargin(e.target.checked)}
                            />
                            <span className="text-xs font-medium text-foreground">Enable Margin Borrowing</span>
                        </label>
                        {config.financing.margin.enabled && (
                            <div className="pl-7 grid grid-cols-2 gap-4 animate-in slide-in-from-top-2 duration-200">
                                <div className="space-y-1">
                                    <label className="text-[10px] font-semibold text-muted-foreground uppercase">Max Leverage Multiplier</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1"
                                        value={config.financing.margin.max_leverage}
                                        onChange={e => updateConfig((prev: any) => ({ ...prev, financing: { ...prev.financing, margin: { ...prev.financing.margin, max_leverage: parseFloat(e.target.value) || 1 } } }))}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-[10px] font-semibold text-muted-foreground uppercase">Daily Interest BPS</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1"
                                        value={config.financing.margin.daily_interest_bps}
                                        onChange={e => updateConfig((prev: any) => ({ ...prev, financing: { ...prev.financing, margin: { ...prev.financing.margin, daily_interest_bps: parseFloat(e.target.value) || 0 } } }))}
                                    />
                                </div>
                            </div>
                        )}

                        <label className="flex items-center space-x-3 cursor-pointer">
                            <input
                                type="checkbox"
                                className="w-4 h-4 rounded border-input text-primary focus:ring-primary"
                                checked={config.financing.shorting.enabled || false}
                                onChange={e => toggleShorting(e.target.checked)}
                            />
                            <span className="text-xs font-medium text-foreground">Enable Short Position Selling</span>
                        </label>
                        {config.financing.shorting.enabled && (
                            <div className="pl-7 grid grid-cols-2 gap-4 animate-in slide-in-from-top-2 duration-200">
                                <div className="space-y-1">
                                    <label className="text-[10px] font-semibold text-muted-foreground uppercase">Borrow Fee (Daily BPS)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1"
                                        value={config.financing.shorting.borrow_fee_daily_bps}
                                        onChange={e => updateConfig((prev: any) => ({ ...prev, financing: { ...prev.financing, shorting: { ...prev.financing.shorting, borrow_fee_daily_bps: parseFloat(e.target.value) || 0 } } }))}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="mt-8 flex justify-between pt-4 border-t border-border">
                <Button variant="outline" onClick={prevStep}>Back</Button>
                <Button onClick={nextStep} className="bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/95 hover:to-indigo-600/95">Next Step</Button>
            </div>
        </div>
    )
}
