"use client"

import { Button } from "@/components/ui/button"
import { useEffect, useState } from "react"
import { AlertCircle, Sliders, Info, Loader2 } from "lucide-react"
import { getStrategySchemas } from "@/lib/api"

const PARAM_HELP: Record<string, string> = {
    lookback_days: "The number of historical trading days used to calculate asset performance or moving average indicators (e.g. 252 days for 1 year, 20 days for 1 month).",
    skip_days: "The number of recent trading days to ignore to avoid short-term market noise or mean reversion effects (e.g. 21 days to skip the most recent month).",
    top_k: "The maximum number of top-performing assets to purchase during each rebalancing cycle.",
    entry_threshold: "The statistical Z-Score threshold at which to trigger a buy order (e.g. 2.0 indicates the price is 2 standard deviations below the mean).",
    exit_threshold: "The statistical Z-Score threshold at which to close an active position (must be less than the entry threshold, e.g. 0.0 or 0.5).",
    hold_days: "The maximum number of calendar days to hold an active position before auto-exiting (if exit threshold is not triggered first).",
    drift_threshold: "The percentage allocation drift (e.g. 0.05 for 5%) that triggers an out-of-schedule rebalancing of assets.",
    rebalance_frequency: "How often the strategy portfolio is checked and adjusted to match target allocations.",
    weighting: "The portfolio weighting methodology (e.g. equal weights, risk-parity, or value-weighted).",
    target_weights: "The target percentage allocation weight for each asset (must sum to 100% or will be normalized)."
}

const FALLBACK_DESCRIPTIONS: Record<string, string> = {
    BUY_AND_HOLD: "Buy and Hold assigns equal weight to all selected assets on day 1 and maintains those holdings until the end of the simulation period.",
    FIXED_WEIGHT_REBALANCE: "Fixed Weight Rebalance maintains target allocation weights over time by rebalancing assets periodically (daily, weekly, monthly, quarterly) or when they drift past a specified threshold.",
    DCA: "Dollar-Cost Averaging periodically allocates fixed dollar amounts or equal weights to selected assets at specified intervals.",
    MOMENTUM: "Momentum strategy selects top performing assets based on historical performance over a specified lookback period (e.g. 252 days) and rebalances holdings periodically.",
    MEAN_REVERSION: "Mean Reversion trades assets based on their statistical deviation (Z-score) from a moving average. It enters when price deviates significantly and exits when it reverts."
}

export function StrategyStep({ config, updateConfig, nextStep, prevStep }: any) {
    const [schemas, setSchemas] = useState<any[]>([])
    const [isLoadingSchemas, setIsLoadingSchemas] = useState(true)
    const [validationError, setValidationError] = useState<string | null>(null)
    const [warnings, setWarnings] = useState<string[]>([])

    const instrumentCount = config.universe.instruments?.length || 0

    // Fetch strategy schemas from backend
    useEffect(() => {
        let active = true
        getStrategySchemas().then(res => {
            if (active) {
                const schemaList = Array.isArray(res) ? res : []
                setSchemas(schemaList)
                setIsLoadingSchemas(false)
            }
        }).catch((err) => {
            console.error("Failed to load strategy schemas:", err)
            if (active) setIsLoadingSchemas(false)
        })
        return () => { active = false }
    }, [])

    const selectedSchema = schemas.find(s => s.type === config.strategy.type)

    // Check if parameter is required
    const isParamRequired = (key: string) => {
        if (!selectedSchema) return true // default to required if no schema
        
        // standard JSON Schema rules
        const requiredList = selectedSchema.required || selectedSchema.required_params || []
        if (Array.isArray(requiredList) && requiredList.includes(key)) return true
        if (selectedSchema.parameters?.[key]?.required === true) return true
        
        // If explicitly optional
        const optionalList = selectedSchema.optional_params || selectedSchema.optional || []
        if (Array.isArray(optionalList) && optionalList.includes(key)) return false
        
        // Default fallbacks for built-in strategies
        if (config.strategy.type === "MOMENTUM") {
            return ["lookback_days", "top_k", "rebalance_frequency"].includes(key)
        }
        if (config.strategy.type === "MEAN_REVERSION") {
            return ["lookback_days", "entry_threshold"].includes(key)
        }
        if (config.strategy.type === "FIXED_WEIGHT_REBALANCE") {
            return ["rebalance_frequency", "target_weights"].includes(key)
        }
        if (config.strategy.type === "DCA") {
            return ["weighting"].includes(key)
        }
        
        return false
    }

    // Feasibility / Warning checks
    useEffect(() => {
        const list: string[] = []
        const strategy = config.strategy.type
        const instruments = config.universe.instruments || []
        const shortingEnabled = config.financing?.shorting?.enabled
        const marginEnabled = config.financing?.margin?.enabled
        
        // Multi-currency checks
        if (strategy === "MOMENTUM") {
            const assetClasses = new Set(instruments.map((i: any) => i.asset_class))
            if (assetClasses.size > 1) {
                list.push("Momentum currently supports single-currency universes. Your universe contains assets from multiple classes/currencies.")
            }
        }
        
        // Negative weights/amounts check
        const targetWeights = config.strategy.params.target_weights || {}
        const hasNegativeWeights = Object.values(targetWeights).some((w: any) => parseFloat(w) < 0) || 
                                   instruments.some((i: any) => parseFloat(i.weight || i.amount || 0) < 0)
        if (hasNegativeWeights && !shortingEnabled) {
            list.push("Negative weights/allocations require shorting to be enabled in Step 3 (Realism).")
        }
        
        // Leverage warning
        const maxGrossLeverage = config.risk?.max_gross_leverage || 1.0
        if (maxGrossLeverage > 1.0 && !marginEnabled) {
            list.push(`Gross leverage limit is set to ${maxGrossLeverage}x. Leverage above 1.0 requires margin to be enabled in Step 3 (Realism).`)
        }

        // Warn on unsupported combinations of strategy and asset classes
        if (selectedSchema && selectedSchema.supported_asset_classes) {
            const unsupported = instruments.filter((i: any) => !selectedSchema.supported_asset_classes.includes(i.asset_class))
            if (unsupported.length > 0) {
                list.push(`Warning: The selected strategy type does not officially support some of your chosen asset classes: ${Array.from(new Set(unsupported.map((i: any) => i.asset_class))).join(", ")}.`)
            }
        }
        
        setWarnings(list)
    }, [config, selectedSchema])

    // Validation checks
    useEffect(() => {
        setValidationError(null)
        const type = config.strategy.type
        const p = config.strategy.params || {}
        const instruments = config.universe.instruments || []

        if (type === "MOMENTUM") {
            const tk = p.top_k !== undefined && p.top_k !== "" ? parseInt(p.top_k) : 3
            if (instrumentCount === 0) {
                setValidationError("Please select at least 1 instrument in Step 1.")
            } else if (tk > instrumentCount && instrumentCount > 0) {
                // Auto-clamp top_k to available instrument count
                updateConfig((prev: any) => ({
                    ...prev,
                    strategy: {
                        ...prev.strategy,
                        params: { ...prev.strategy.params, top_k: Math.max(1, instrumentCount) }
                    }
                }))
            }
        } else if (type === "MEAN_REVERSION") {
            if (p.entry_threshold === undefined || p.entry_threshold <= 0) setValidationError("Entry threshold must be > 0.")
            else if (p.exit_threshold !== undefined && p.exit_threshold !== "" && p.exit_threshold < 0) setValidationError("Exit threshold must be >= 0.")
            else if (p.exit_threshold !== undefined && p.exit_threshold !== "" && p.exit_threshold >= p.entry_threshold) setValidationError("Exit threshold must be < entry threshold.")
            else if (p.hold_days !== undefined && p.hold_days !== "" && p.hold_days <= 0) setValidationError("Hold days must be > 0.")
            else if ((p.exit_threshold === undefined || p.exit_threshold === "") && (p.hold_days === undefined || p.hold_days === "")) setValidationError("Must specify either Exit Threshold or Hold Days.")
        } else if (type === "FIXED_WEIGHT_REBALANCE") {
            const tw = p.target_weights || {}
            const symbols = instruments.map((i: any) => i.symbol)
            const missing = symbols.filter((s: string) => tw[s] === undefined || tw[s] === "")
            if (instrumentCount === 0) {
                setValidationError("Please select at least 1 instrument in Step 1.")
            } else if (missing.length > 0) {
                // Auto-populate target weights for missing symbols
                const newWeights: Record<string, number> = { ...tw }
                symbols.forEach((s: string) => {
                    if (newWeights[s] === undefined || newWeights[s] === null || (newWeights[s] as any) === "") {
                        newWeights[s] = instrumentCount > 0 ? parseFloat((1 / instrumentCount).toFixed(4)) : 1.0
                    }
                })
                updateConfig((prev: any) => ({
                    ...prev,
                    strategy: {
                        ...prev.strategy,
                        params: { ...prev.strategy.params, target_weights: newWeights }
                    }
                }))
            } else {
                const totalGross = Object.values(tw).reduce((acc: number, val: any) => acc + Math.abs(parseFloat(val || 0)), 0)
                if (totalGross <= 0) {
                    setValidationError("Sum of absolute weights must be greater than 0%.")
                }
                const drift = p.drift_threshold
                if (drift !== undefined && drift !== "" && (drift < 0 || drift > 1)) {
                    setValidationError("Drift threshold must be between 0.0 and 1.0 (0% to 100%).")
                }
            }
        }
    }, [config.strategy, instrumentCount])

    const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const type = e.target.value
        let defaultParams: any = {}

        const match = schemas.find(s => s.type === type)
        if (match && match.parameters) {
            Object.entries(match.parameters).forEach(([key, paramSchema]: [string, any]) => {
                defaultParams[key] = paramSchema.default ?? ""
            })
        } else {
            if (type === "MOMENTUM") {
                defaultParams = { lookback_days: 252, skip_days: 21, top_k: Math.max(1, Math.min(3, instrumentCount || 1)), rebalance_frequency: "MONTHLY", weighting: "EQUAL" }
            } else if (type === "MEAN_REVERSION") {
                defaultParams = { entry_threshold: 2.0, lookback_days: 20, hold_days: 5 }
            } else if (type === "DCA") {
                defaultParams = { weighting: "EQUAL" }
            } else if (type === "FIXED_WEIGHT_REBALANCE") {
                const weights: Record<string, number> = {}
                config.universe.instruments.forEach((inst: any) => {
                    weights[inst.symbol] = instrumentCount > 0 ? parseFloat((1 / instrumentCount).toFixed(4)) : 1.0
                })
                defaultParams = { rebalance_frequency: "MONTHLY", target_weights: weights, drift_threshold: 0.05 }
            }
        }

        updateConfig((prev: any) => ({
            ...prev,
            strategy: { type, params: defaultParams }
        }))
    }

    const setParam = (key: string, value: any) => {
        updateConfig((prev: any) => ({
            ...prev,
            strategy: {
                ...prev.strategy,
                params: { ...prev.strategy.params, [key]: value }
            }
        }))
    }

    const strategyOptions = schemas.length > 0 
        ? schemas.map(s => ({ value: s.type || s.name, label: s.name || s.type }))
        : [
            { value: "BUY_AND_HOLD", label: "Buy And Hold" },
            { value: "FIXED_WEIGHT_REBALANCE", label: "Fixed Weight Rebalance" },
            { value: "DCA", label: "DCA" },
            { value: "MOMENTUM", label: "Momentum" },
            { value: "MEAN_REVERSION", label: "Mean Reversion" }
          ]

    const getParamRangeText = (paramSchema: any) => {
        const min = paramSchema?.minimum ?? paramSchema?.min
        const max = paramSchema?.maximum ?? paramSchema?.max
        if (min !== undefined && max !== undefined) return `Range: ${min} to ${max}`
        if (min !== undefined) return `Min: ${min}`
        if (max !== undefined) return `Max: ${max}`
        return ""
    }

    const renderParamLabel = (key: string, labelText: string) => {
        const required = isParamRequired(key)
        return (
            <label className="text-xs font-semibold text-foreground flex items-center">
                <span>{labelText}</span>
                {required ? (
                    <span className="text-rose-500 ml-0.5 font-bold" title="Required Parameter">*</span>
                ) : (
                    <span className="text-muted-foreground/60 text-[10px] font-normal ml-1">(Optional)</span>
                )}
            </label>
        )
    }

    const renderParamFieldHelp = (key: string, paramSchema?: any) => {
        const helpText = paramSchema?.description || PARAM_HELP[key]
        const rangeText = paramSchema ? getParamRangeText(paramSchema) : ""
        const unitText = paramSchema?.unit ? `Unit: ${String(paramSchema.unit).replaceAll("_", " ")}` : ""
        if (!helpText && !rangeText && !unitText) return null
        return (
            <div className="space-y-0.5 mt-1">
                {helpText && <p className="text-[10px] text-muted-foreground leading-normal">{helpText}</p>}
                {unitText && <p className="text-[10px] text-muted-foreground/80">{unitText}</p>}
                {rangeText && <p className="text-[10px] text-primary/80 font-medium font-mono">{rangeText}</p>}
            </div>
        )
    }

    const strategyDescription = selectedSchema?.description || FALLBACK_DESCRIPTIONS[config.strategy.type] || ""

    return (
        <div className="p-6 flex flex-col h-full space-y-6">
            <div>
                <h2 className="text-xl font-bold tracking-tight">Configure Strategy Rules</h2>
                <p className="text-xs text-muted-foreground mt-1">
                    Select a core execution strategy and customize parameters dynamically mapped from the backtest engine schema rules.
                </p>
            </div>

            <div className="space-y-6 flex-1">
                <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase text-muted-foreground">Select Strategy Type</label>
                    {isLoadingSchemas ? (
                        <div className="flex items-center space-x-2 h-10 px-3 border rounded-md bg-muted/40 animate-pulse text-xs text-muted-foreground">
                            <Loader2 className="w-4 h-4 animate-spin text-primary" />
                            <span>Loading strategy schemas from backtest engine...</span>
                        </div>
                    ) : (
                        <select
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            value={config.strategy.type}
                            onChange={handleTypeChange}
                        >
                            {strategyOptions.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label.replace(/_/g, " ")}</option>
                            ))}
                        </select>
                    )}
                </div>

                {strategyDescription && (
                    <div className="flex items-start gap-2.5 p-3 rounded-lg border border-primary/10 bg-primary/5 text-xs text-foreground/80">
                        <Info className="w-4 h-4 shrink-0 text-primary mt-0.5" />
                        <p>{strategyDescription}</p>
                    </div>
                )}

                <div className="bg-muted/30 border border-border rounded-xl p-4 space-y-4">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5 pb-2 border-b border-border/50">
                        <Sliders className="w-3.5 h-3.5 text-primary" /> Execution Parameters
                    </h3>

                    {config.strategy.type === "BUY_AND_HOLD" && (
                        <p className="text-xs text-muted-foreground text-center py-6 font-medium">This strategy takes no configuration parameters.</p>
                    )}

                    {config.strategy.type === "FIXED_WEIGHT_REBALANCE" && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    {renderParamLabel("rebalance_frequency", "Rebalance Frequency")}
                                    <select
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                        value={config.strategy.params.rebalance_frequency || "MONTHLY"}
                                        onChange={e => setParam("rebalance_frequency", e.target.value)}
                                    >
                                        <option value="DAILY">Daily</option>
                                        <option value="WEEKLY">Weekly</option>
                                        <option value="MONTHLY">Monthly</option>
                                        <option value="QUARTERLY">Quarterly</option>
                                    </select>
                                    {renderParamFieldHelp("rebalance_frequency", selectedSchema?.parameters?.rebalance_frequency)}
                                </div>
                                <div className="space-y-1.5">
                                    {renderParamLabel("drift_threshold", "Drift Threshold")}
                                    <input
                                        type="number"
                                        step="0.01"
                                        min="0"
                                        max="1"
                                        placeholder="e.g. 0.05 (5%)"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                        value={config.strategy.params.drift_threshold ?? ""}
                                        onChange={e => {
                                            const val = e.target.value
                                            setParam("drift_threshold", val === "" ? "" : parseFloat(val))
                                        }}
                                    />
                                    {renderParamFieldHelp("drift_threshold", selectedSchema?.parameters?.drift_threshold)}
                                </div>
                            </div>
                            
                            <div className="space-y-2 pt-2">
                                {renderParamLabel("target_weights", "Target Weights (%)")}
                                <div className="border border-border rounded-md p-3 space-y-2.5 bg-background/50">
                                    {config.universe.instruments.map((inst: any) => {
                                        const tw = config.strategy.params.target_weights || {}
                                        const currentVal = tw[inst.symbol] ?? ""
                                        return (
                                            <div key={inst.symbol} className="flex items-center justify-between text-xs">
                                                <span className="font-semibold text-foreground">{inst.symbol}</span>
                                                <div className="flex items-center space-x-1.5">
                                                    <input
                                                        type="number"
                                                        step="0.1"
                                                        className="w-20 h-8 rounded border bg-background px-2 text-center text-xs focus:ring-1 focus:ring-primary focus:outline-none"
                                                        value={currentVal !== "" ? (parseFloat(currentVal) * 100).toFixed(1) : ""}
                                                        onChange={e => {
                                                            const val = e.target.value
                                                            const newWeights = { ...tw }
                                                            if (val === "") {
                                                                delete newWeights[inst.symbol]
                                                            } else {
                                                                newWeights[inst.symbol] = parseFloat((parseFloat(val) / 100).toFixed(4))
                                                            }
                                                            setParam("target_weights", newWeights)
                                                        }}
                                                    />
                                                    <span className="text-muted-foreground">%</span>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                                {renderParamFieldHelp("target_weights", selectedSchema?.parameters?.target_weights)}
                            </div>
                        </div>
                    )}

                    {config.strategy.type === "MOMENTUM" && (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                {renderParamLabel("lookback_days", "Lookback Days")}
                                <input
                                    type="number"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.lookback_days || 252}
                                    onChange={e => setParam("lookback_days", parseInt(e.target.value))}
                                />
                                {renderParamFieldHelp("lookback_days", selectedSchema?.parameters?.lookback_days)}
                            </div>
                            <div className="space-y-1.5">
                                {renderParamLabel("skip_days", "Skip Days")}
                                <input
                                    type="number"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.skip_days || 21}
                                    onChange={e => setParam("skip_days", parseInt(e.target.value))}
                                />
                                {renderParamFieldHelp("skip_days", selectedSchema?.parameters?.skip_days)}
                            </div>
                            <div className="space-y-1.5">
                                {renderParamLabel("top_k", "Top K Assets")}
                                <input
                                    type="number"
                                    min="1"
                                    max={instrumentCount}
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.top_k || 3}
                                    onChange={e => {
                                        let val = parseInt(e.target.value)
                                        if (!isNaN(val)) {
                                            if (val > instrumentCount) val = instrumentCount
                                            if (val < 1) val = 1
                                            setParam("top_k", val)
                                        } else {
                                            setParam("top_k", "")
                                        }
                                    }}
                                />
                                {renderParamFieldHelp("top_k", selectedSchema?.parameters?.top_k)}
                            </div>
                            <div className="space-y-1.5">
                                {renderParamLabel("rebalance_frequency", "Rebalance Frequency")}
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.rebalance_frequency || "MONTHLY"}
                                    onChange={e => setParam("rebalance_frequency", e.target.value)}
                                >
                                    <option value="WEEKLY">Weekly</option>
                                    <option value="MONTHLY">Monthly</option>
                                    <option value="QUARTERLY">Quarterly</option>
                                </select>
                                {renderParamFieldHelp("rebalance_frequency", selectedSchema?.parameters?.rebalance_frequency)}
                            </div>
                        </div>
                    )}

                    {config.strategy.type === "MEAN_REVERSION" && (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                {renderParamLabel("lookback_days", "Lookback Days")}
                                <input
                                    type="number"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.lookback_days || 20}
                                    onChange={e => setParam("lookback_days", parseInt(e.target.value))}
                                />
                                {renderParamFieldHelp("lookback_days", selectedSchema?.parameters?.lookback_days)}
                            </div>
                            <div className="space-y-1.5">
                                {renderParamLabel("entry_threshold", "Entry Threshold (Z-Score)")}
                                <input
                                    type="number"
                                    step="0.1"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.entry_threshold ?? 2.0}
                                    onChange={e => setParam("entry_threshold", parseFloat(e.target.value))}
                                />
                                {renderParamFieldHelp("entry_threshold", selectedSchema?.parameters?.entry_threshold)}
                            </div>
                            <div className="space-y-1.5">
                                {renderParamLabel("exit_threshold", "Exit Threshold")}
                                <input
                                    type="number"
                                    step="0.1"
                                    placeholder="e.g. 0.0"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.exit_threshold ?? ""}
                                    onChange={e => {
                                        const val = e.target.value
                                        if (val === "") setParam("exit_threshold", "")
                                        else setParam("exit_threshold", parseFloat(val))
                                    }}
                                />
                                {renderParamFieldHelp("exit_threshold", selectedSchema?.parameters?.exit_threshold)}
                            </div>
                            <div className="space-y-1.5">
                                {renderParamLabel("hold_days", "Hold Days")}
                                <input
                                    type="number"
                                    placeholder="e.g. 5"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.hold_days ?? ""}
                                    onChange={e => {
                                        const val = e.target.value
                                        if (val === "") setParam("hold_days", "")
                                        else setParam("hold_days", parseInt(val))
                                    }}
                                />
                                {renderParamFieldHelp("hold_days", selectedSchema?.parameters?.hold_days)}
                            </div>
                        </div>
                    )}

                    {config.strategy.type === "DCA" && (
                        <div className="space-y-1.5">
                            {renderParamLabel("weighting", "Periodic Buy Weighting")}
                            <select
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.strategy.params.weighting || "EQUAL"}
                                onChange={e => setParam("weighting", e.target.value)}
                            >
                                <option value="EQUAL">Equal Target Weights</option>
                            </select>
                            {renderParamFieldHelp("weighting", selectedSchema?.parameters?.weighting)}
                        </div>
                    )}

                    {/* Dynamically render unknown parameter fields parsed from strategy schemas */}
                    {selectedSchema?.parameters && !["BUY_AND_HOLD", "FIXED_WEIGHT_REBALANCE", "MOMENTUM", "MEAN_REVERSION", "DCA"].includes(config.strategy.type) && (
                        <div className="space-y-6 pt-2">
                            {/* Required Parameters section */}
                            {Object.entries(selectedSchema.parameters).some(([key]) => isParamRequired(key)) && (
                                <div className="space-y-4">
                                    <h4 className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider pb-1 border-b">Required Configurations</h4>
                                    <div className="grid grid-cols-2 gap-4">
                                        {Object.entries(selectedSchema.parameters)
                                            .filter(([key]) => isParamRequired(key))
                                            .map(([key, paramSchema]: [string, any]) => (
                                                <div key={key} className="space-y-1.5">
                                                    {renderParamLabel(key, key.replace(/_/g, " "))}
                                                    {paramSchema.enum ? (
                                                        <select
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                            value={config.strategy.params[key] ?? paramSchema.default ?? ""}
                                                            onChange={e => setParam(key, e.target.value)}
                                                        >
                                                            {paramSchema.enum.map((opt: string) => (
                                                                <option key={opt} value={opt}>{opt}</option>
                                                            ))}
                                                        </select>
                                                    ) : (
                                                        <input
                                                            type={paramSchema.type === "number" || paramSchema.type === "integer" ? "number" : "text"}
                                                            placeholder={`Default: ${paramSchema.default ?? ""}`}
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                            value={config.strategy.params[key] ?? ""}
                                                            onChange={e => {
                                                                const val = e.target.value
                                                                setParam(key, paramSchema.type === "number" || paramSchema.type === "integer" ? (val === "" ? "" : parseFloat(val)) : val)
                                                            }}
                                                        />
                                                    )}
                                                    {renderParamFieldHelp(key, paramSchema)}
                                                </div>
                                            ))}
                                    </div>
                                </div>
                            )}

                            {/* Optional Parameters section */}
                            {Object.entries(selectedSchema.parameters).some(([key]) => !isParamRequired(key)) && (
                                <div className="space-y-4 pt-2">
                                    <h4 className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider pb-1 border-b">Optional Configurations</h4>
                                    <div className="grid grid-cols-2 gap-4">
                                        {Object.entries(selectedSchema.parameters)
                                            .filter(([key]) => !isParamRequired(key))
                                            .map(([key, paramSchema]: [string, any]) => (
                                                <div key={key} className="space-y-1.5">
                                                    {renderParamLabel(key, key.replace(/_/g, " "))}
                                                    {paramSchema.enum ? (
                                                        <select
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                            value={config.strategy.params[key] ?? paramSchema.default ?? ""}
                                                            onChange={e => setParam(key, e.target.value)}
                                                        >
                                                            {paramSchema.enum.map((opt: string) => (
                                                                <option key={opt} value={opt}>{opt}</option>
                                                            ))}
                                                        </select>
                                                    ) : (
                                                        <input
                                                            type={paramSchema.type === "number" || paramSchema.type === "integer" ? "number" : "text"}
                                                            placeholder={`Default: ${paramSchema.default ?? ""}`}
                                                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                            value={config.strategy.params[key] ?? ""}
                                                            onChange={e => {
                                                                const val = e.target.value
                                                                setParam(key, paramSchema.type === "number" || paramSchema.type === "integer" ? (val === "" ? "" : parseFloat(val)) : val)
                                                            }}
                                                        />
                                                    )}
                                                    {renderParamFieldHelp(key, paramSchema)}
                                                </div>
                                            ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-8 flex flex-col pt-4 border-t border-border gap-4">
                {warnings.length > 0 && (
                    <div className="space-y-2">
                        {warnings.map((w, idx) => (
                            <div key={idx} className="flex items-center space-x-2 text-xs text-amber-600 bg-amber-50 border border-amber-200 dark:bg-amber-950/20 dark:border-amber-900 p-2.5 rounded-md">
                                <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
                                <span>{w}</span>
                            </div>
                        ))}
                    </div>
                )}
                {validationError && (
                    <div className="text-xs text-rose-600 bg-rose-50 border border-rose-200 dark:bg-rose-950/20 dark:border-rose-900 p-2.5 rounded-md font-medium">
                        {validationError}
                    </div>
                )}
                <div className="flex justify-between w-full pt-2">
                    <Button variant="outline" onClick={prevStep}>Back</Button>
                    <Button onClick={nextStep} disabled={!!validationError}>Next Step</Button>
                </div>
            </div>
        </div>
    )
}
