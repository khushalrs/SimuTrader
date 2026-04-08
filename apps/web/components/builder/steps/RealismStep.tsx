"use client"

import { Button } from "@/components/ui/button"

export function RealismStep({ config, updateConfig, nextStep, prevStep }: any) {

    // Handlers for Execution
    const setExecution = (field: string, value: any) => {
        updateConfig((prev: any) => ({
            ...prev, execution: { ...prev.execution, [field]: value }
        }))
    }
    const setCommission = (bps: number) => {
        updateConfig((prev: any) => ({
            ...prev, execution: { ...prev.execution, commission: { ...prev.execution.commission, bps } }
        }))
    }
    const setSlippage = (bps: number) => {
        updateConfig((prev: any) => ({
            ...prev, execution: { ...prev.execution, slippage: { ...prev.execution.slippage, bps } }
        }))
    }

    // Handlers for Financing / Taxes
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
    const setTaxRegime = (regime: string) => {
        updateConfig((prev: any) => ({
            ...prev, tax: { ...prev.tax, regime }
        }))
    }

    return (
        <div className="p-6 flex flex-col h-full">
            <div className="mb-6">
                <h2 className="text-xl font-semibold">Realism Knobs</h2>

            </div>

            <div className="space-y-8 flex-1">

                {/* Execution Costs */}
                <div className="space-y-4">
                    <h3 className="text-sm font-medium border-b border-border pb-2">Execution & Frictions</h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Commission (BPS)</label>
                            <input
                                type="number"
                                step="0.5"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.execution.commission.bps}
                                onChange={e => setCommission(parseFloat(e.target.value))}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Slippage (BPS)</label>
                            <input
                                type="number"
                                step="0.5"
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.execution.slippage.bps}
                                onChange={e => setSlippage(parseFloat(e.target.value))}
                            />
                        </div>
                    </div>
                </div>

                {/* Financing */}
                <div className="space-y-4">
                    <h3 className="text-sm font-medium border-b border-border pb-2">Financing</h3>
                    <div className="flex flex-col space-y-4">
                        <label className="flex items-center space-x-3 cursor-pointer">
                            <input
                                type="checkbox"
                                className="w-4 h-4 rounded border-input text-primary focus:ring-primary"
                                checked={config.financing.margin.enabled || false}
                                onChange={e => toggleMargin(e.target.checked)}
                            />
                            <span className="text-sm font-medium">Enable Margin Borrowing</span>
                        </label>
                        {config.financing.margin.enabled && (
                            <div className="pl-7 grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Max Leverage</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                                        value={config.financing.margin.max_leverage}
                                        onChange={e => updateConfig((prev: any) => ({ ...prev, financing: { ...prev.financing, margin: { ...prev.financing.margin, max_leverage: parseFloat(e.target.value) } } }))}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Daily Interest BPS</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                                        value={config.financing.margin.daily_interest_bps}
                                        onChange={e => updateConfig((prev: any) => ({ ...prev, financing: { ...prev.financing, margin: { ...prev.financing.margin, daily_interest_bps: parseFloat(e.target.value) } } }))}
                                    />
                                </div>
                            </div>
                        )}

                        <label className="flex items-center space-x-3 cursor-pointer mt-2">
                            <input
                                type="checkbox"
                                className="w-4 h-4 rounded border-input text-primary focus:ring-primary"
                                checked={config.financing.shorting.enabled || false}
                                onChange={e => toggleShorting(e.target.checked)}
                            />
                            <span className="text-sm font-medium">Enable Shorting</span>
                        </label>
                        {config.financing.shorting.enabled && (
                            <div className="pl-7 grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Borrow Fee (Daily BPS)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                                        value={config.financing.shorting.borrow_fee_daily_bps}
                                        onChange={e => updateConfig((prev: any) => ({ ...prev, financing: { ...prev.financing, shorting: { ...prev.financing.shorting, borrow_fee_daily_bps: parseFloat(e.target.value) } } }))}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Taxes/Reporting */}
                <div className="space-y-4">
                    <h3 className="text-sm font-medium border-b border-border pb-2">Taxes & Geography</h3>
                    <div className="space-y-2">
                        <label className="text-xs text-muted-foreground">Tax Regime</label>
                        <select
                            className="flex h-9 w-full md:w-1/2 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            value={config.tax.regime || "NONE"}
                            onChange={e => setTaxRegime(e.target.value)}
                        >
                            <option value="US">United States (IRS FIFO)</option>
                            <option value="INDIA">India (Income Tax FIFO)</option>
                            <option value="NONE">No Taxes (Tax Advantaged) - Default</option>
                        </select>
                    </div>
                </div>
            </div>

            <div className="mt-8 flex justify-between pt-4 border-t border-border">
                <Button variant="outline" onClick={prevStep}>Back</Button>
                <Button onClick={nextStep}>Next Step</Button>
            </div>
        </div>
    )
}
