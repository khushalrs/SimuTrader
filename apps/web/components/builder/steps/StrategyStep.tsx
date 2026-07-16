"use client"

import { Button } from "@/components/ui/button"
import { useEffect, useState } from "react"
import { AlertCircle } from "lucide-react"

export function StrategyStep({ config, updateConfig, nextStep, prevStep }: any) {
    const strategyTypes = ["BUY_AND_HOLD", "FIXED_WEIGHT_REBALANCE", "DCA", "MOMENTUM", "MEAN_REVERSION"];
    const instrumentCount = config.universe.instruments?.length || 0;
    const [validationError, setValidationError] = useState<string | null>(null);
    const [warnings, setWarnings] = useState<string[]>([]);

    useEffect(() => {
        const list: string[] = [];
        const strategy = config.strategy.type;
        const instruments = config.universe.instruments || [];
        const shortingEnabled = config.financing?.shorting?.enabled;
        const marginEnabled = config.financing?.margin?.enabled;
        
        // Multi-currency momentum check
        if (strategy === "MOMENTUM") {
            const assetClasses = new Set(instruments.map((i: any) => i.asset_class));
            if (assetClasses.size > 1) {
                list.push("Momentum currently supports single-currency universes. Your universe contains assets from multiple classes/currencies.");
            }
        }
        
        // Negative weights/amounts check
        const targetWeights = config.strategy.params.target_weights || {};
        const hasNegativeWeights = Object.values(targetWeights).some((w: any) => parseFloat(w) < 0) || instruments.some((i: any) => parseFloat(i.weight || i.amount || 0) < 0);
        if (hasNegativeWeights && !shortingEnabled) {
            list.push("Negative weights/allocations require shorting to be enabled in Step 3 (Realism).");
        }
        
        // Leverage warning
        const maxGrossLeverage = config.risk?.max_gross_leverage || 1.0;
        if (maxGrossLeverage > 1.0 && !marginEnabled) {
            list.push(`Gross leverage limit is set to ${maxGrossLeverage}x. Leverage above 1.0 requires margin to be enabled in Step 3 (Realism).`);
        }
        
        setWarnings(list);
    }, [config]);

    useEffect(() => {
        if (config.strategy.type === "MOMENTUM") {
            const currentTopK = config.strategy.params.top_k || 3;
            if (currentTopK > instrumentCount && instrumentCount > 0) {
                updateConfig((prev: any) => ({
                    ...prev,
                    strategy: {
                        ...prev.strategy,
                        params: { ...prev.strategy.params, top_k: instrumentCount }
                    }
                }));
            }
        }
    }, [config.strategy.type, instrumentCount, config.strategy.params.top_k, updateConfig]);

    useEffect(() => {
        setValidationError(null);
        if (config.strategy.type === "MOMENTUM") {
            const tk = config.strategy.params.top_k || 3;
            if (instrumentCount === 0) setValidationError("Please select at least 1 instrument in Step 1.");
            else if (tk < 1 || tk > instrumentCount) setValidationError("Top K must be between 1 and the number of selected instruments.");
        } else if (config.strategy.type === "MEAN_REVERSION") {
            const p = config.strategy.params;
            if (p.entry_threshold === undefined || p.entry_threshold <= 0) setValidationError("Entry threshold must be > 0.");
            else if (p.exit_threshold !== undefined && p.exit_threshold !== "" && p.exit_threshold < 0) setValidationError("Exit threshold must be >= 0.");
            else if (p.exit_threshold !== undefined && p.exit_threshold !== "" && p.exit_threshold >= p.entry_threshold) setValidationError("Exit threshold must be < entry threshold.");
            else if (p.hold_days !== undefined && p.hold_days !== "" && p.hold_days <= 0) setValidationError("Hold days must be > 0.");
            else if ((p.exit_threshold === undefined || p.exit_threshold === "") && (p.hold_days === undefined || p.hold_days === "")) setValidationError("Must specify either Exit Threshold or Hold Days.");
        } else if (config.strategy.type === "FIXED_WEIGHT_REBALANCE") {
            const p = config.strategy.params;
            const tw = p.target_weights || {};
            const symbols = config.universe.instruments.map((i: any) => i.symbol);
            const missing = symbols.filter((s: string) => tw[s] === undefined || tw[s] === "");
            if (instrumentCount === 0) {
                setValidationError("Please select at least 1 instrument in Step 1.");
            } else if (missing.length > 0) {
                setValidationError(`Must specify target weights for all symbols. Missing: ${missing.join(", ")}`);
            } else {
                const totalGross = Object.values(tw).reduce((acc: number, val: any) => acc + Math.abs(parseFloat(val || 0)), 0);
                if (totalGross <= 0) {
                    setValidationError("Sum of absolute weights must be greater than 0%.");
                }
                const drift = p.drift_threshold;
                if (drift !== undefined && drift !== "" && (drift < 0 || drift > 1)) {
                    setValidationError("Drift threshold must be between 0.0 and 1.0 (0% to 100%).");
                }
            }
        }
    }, [config.strategy, instrumentCount, config.universe.instruments]);

    const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const type = e.target.value;
        let defaultParams = {};

        if (type === "MOMENTUM") {
            defaultParams = { lookback_days: 252, skip_days: 21, top_k: Math.max(1, Math.min(3, instrumentCount || 1)), rebalance_frequency: "MONTHLY", weighting: "EQUAL" }
        } else if (type === "MEAN_REVERSION") {
            defaultParams = { entry_threshold: 2.0, lookback_days: 20, hold_days: 5 }
        } else if (type === "DCA") {
            defaultParams = { weighting: "EQUAL" }
        } else if (type === "FIXED_WEIGHT_REBALANCE") {
            const weights: Record<string, number> = {};
            config.universe.instruments.forEach((inst: any) => {
                weights[inst.symbol] = instrumentCount > 0 ? parseFloat((1 / instrumentCount).toFixed(4)) : 1.0;
            });
            defaultParams = { rebalance_frequency: "MONTHLY", target_weights: weights, drift_threshold: 0.05 }
        }

        updateConfig((prev: any) => ({
            ...prev,
            strategy: { type, params: defaultParams }
        }));
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

    return (
        <div className="p-6 flex flex-col h-full">
            <h2 className="text-xl font-semibold mb-6">Configure Strategy</h2>

            <div className="space-y-6 flex-1">
                <div className="space-y-2">
                    <label className="text-sm font-medium">Strategy Type</label>
                    <select
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        value={config.strategy.type}
                        onChange={handleTypeChange}
                    >
                        {strategyTypes.map(t => (
                            <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                        ))}
                    </select>
                </div>

                <div className="bg-muted/30 border border-border rounded-lg p-4 space-y-4">
                    <h3 className="text-sm font-medium border-b border-border pb-2">Parameters</h3>

                    {config.strategy.type === "BUY_AND_HOLD" && (
                        <p className="text-sm text-muted-foreground">Buy and hold assigns equal weight to all assets on day 1 and holds them until the end.</p>
                    )}

                    {config.strategy.type === "FIXED_WEIGHT_REBALANCE" && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Rebalance Frequency</label>
                                    <select
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                        value={config.strategy.params.rebalance_frequency || "MONTHLY"}
                                        onChange={e => setParam("rebalance_frequency", e.target.value)}
                                    >
                                        <option value="DAILY">Daily</option>
                                        <option value="WEEKLY">Weekly</option>
                                        <option value="MONTHLY">Monthly</option>
                                        <option value="QUARTERLY">Quarterly</option>
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-muted-foreground">Drift Threshold (Optional)</label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        min="0"
                                        max="1"
                                        placeholder="e.g. 0.05 (5%)"
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                        value={config.strategy.params.drift_threshold ?? ""}
                                        onChange={e => {
                                            const val = e.target.value;
                                            setParam("drift_threshold", val === "" ? "" : parseFloat(val));
                                        }}
                                    />
                                </div>
                            </div>
                            
                            <div className="space-y-2 pt-2">
                                <label className="text-xs font-semibold text-foreground">Target Weights (%)</label>
                                <div className="border border-border rounded-md p-3 space-y-2.5 bg-background/50">
                                    {config.universe.instruments.map((inst: any) => {
                                        const tw = config.strategy.params.target_weights || {};
                                        const currentVal = tw[inst.symbol] ?? "";
                                        return (
                                            <div key={inst.symbol} className="flex items-center justify-between text-xs">
                                                <span className="font-medium text-foreground">{inst.symbol}</span>
                                                <div className="flex items-center space-x-1.5">
                                                    <input
                                                        type="number"
                                                        step="0.1"
                                                        className="w-20 h-7 rounded border bg-background px-2 text-center text-xs focus:ring-1 focus:ring-primary focus:outline-none"
                                                        value={currentVal !== "" ? (parseFloat(currentVal) * 100).toFixed(1) : ""}
                                                        onChange={e => {
                                                            const val = e.target.value;
                                                            const newWeights = { ...tw };
                                                            if (val === "") {
                                                                delete newWeights[inst.symbol];
                                                            } else {
                                                                newWeights[inst.symbol] = parseFloat((parseFloat(val) / 100).toFixed(4));
                                                            }
                                                            setParam("target_weights", newWeights);
                                                        }}
                                                    />
                                                    <span className="text-muted-foreground">%</span>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                                <p className="text-[10px] text-muted-foreground">Weights will be automatically normalized to sum to 100% by the backtest engine.</p>
                            </div>
                        </div>
                    )}

                    {config.strategy.type === "MOMENTUM" && (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Lookback Days</label>
                                <input
                                    type="number"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.lookback_days || 252}
                                    onChange={e => setParam("lookback_days", parseInt(e.target.value))}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Skip Days</label>
                                <input
                                    type="number"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.skip_days || 21}
                                    onChange={e => setParam("skip_days", parseInt(e.target.value))}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Top K</label>
                                <input
                                    type="number"
                                    min="1"
                                    max={instrumentCount}
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.top_k || 3}
                                    onChange={e => {
                                        let val = parseInt(e.target.value);
                                        if (!isNaN(val)) {
                                            if (val > instrumentCount) val = instrumentCount;
                                            if (val < 1) val = 1;
                                            setParam("top_k", val);
                                        } else {
                                            setParam("top_k", "");
                                        }
                                    }}
                                />
                                <p className="text-[10px] text-muted-foreground pt-1">Cannot exceed {instrumentCount} selected instruments.</p>
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Rebalance</label>
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.rebalance_frequency || "MONTHLY"}
                                    onChange={e => setParam("rebalance_frequency", e.target.value)}
                                >
                                    <option value="WEEKLY">Weekly</option>
                                    <option value="MONTHLY">Monthly</option>
                                    <option value="QUARTERLY">Quarterly</option>
                                </select>
                            </div>
                        </div>
                    )}

                    {config.strategy.type === "MEAN_REVERSION" && (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Lookback Days</label>
                                <input
                                    type="number"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.lookback_days || 20}
                                    onChange={e => setParam("lookback_days", parseInt(e.target.value))}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Entry Threshold (Z-Score)</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.entry_threshold ?? 2.0}
                                    onChange={e => setParam("entry_threshold", parseFloat(e.target.value))}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Exit Threshold (Optional)</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    placeholder="e.g. 0.0"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.exit_threshold ?? ""}
                                    onChange={e => {
                                        const val = e.target.value;
                                        if (val === "") setParam("exit_threshold", "");
                                        else setParam("exit_threshold", parseFloat(val));
                                    }}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Hold Days (Optional)</label>
                                <input
                                    type="number"
                                    placeholder="e.g. 5"
                                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={config.strategy.params.hold_days ?? ""}
                                    onChange={e => {
                                        const val = e.target.value;
                                        if (val === "") setParam("hold_days", "");
                                        else setParam("hold_days", parseInt(val));
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {config.strategy.type === "DCA" && (
                        <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Periodic Buy Targets</label>
                            <select
                                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                value={config.strategy.params.weighting || "EQUAL"}
                                onChange={e => setParam("weighting", e.target.value)}
                            >
                                <option value="EQUAL">Equal Target Weights</option>
                            </select>
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-8 flex flex-col pt-4 border-t border-border gap-4">
                {warnings.length > 0 && (
                    <div className="space-y-2">
                        {warnings.map((w, idx) => (
                            <div key={idx} className="flex items-center space-x-2 text-xs text-amber-600 bg-amber-50 border border-amber-200 p-2.5 rounded-md">
                                <AlertCircle className="w-4 h-4 text-amber-500 shrink-0" />
                                <span>{w}</span>
                            </div>
                        ))}
                    </div>
                )}
                {validationError && (
                    <div className="text-sm text-destructive font-medium bg-destructive/10 border border-destructive/20 p-2 rounded w-fit">
                        {validationError}
                    </div>
                )}
                <div className="flex justify-between w-full">
                    <Button variant="outline" onClick={prevStep}>Back</Button>
                    <Button onClick={nextStep} disabled={!!validationError}>Next Step</Button>
                </div>
            </div>
        </div>
    )
}
