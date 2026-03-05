"use client"

import { useState } from "react"
import { UniverseStep } from "./steps/UniverseStep"
import { StrategyStep } from "./steps/StrategyStep"
import { RealismStep } from "./steps/RealismStep"
import { ReviewStep } from "./steps/ReviewStep"

export function StrategyBuilder() {
    const [currentStep, setCurrentStep] = useState(1);
    const [config, setConfig] = useState({
        version: "1.0",
        name: "Custom Strategy",
        universe: {
            base_currency: "USD",
            instruments: [] as any[],
            calendars: {
                US_EQUITY: "US",
                IN_EQUITY: "IN",
                FX: "US"
            }
        },
        backtest: {
            start_date: "2018-01-02",
            end_date: "2024-12-31",
            initial_cash: 100000,
            cash_currency: "USD",
            contributions: {
                enabled: false,
                amount: 0,
                frequency: "MONTHLY"
            }
        },
        execution: {
            commission: { model: "BPS", bps: 1.0, min_fee: 0.0 },
            slippage: { model: "BPS", bps: 2.0 },
            fill_price: "CLOSE"
        },
        financing: {
            margin: { enabled: true, max_leverage: 2.0, daily_interest_bps: 1.5 },
            shorting: { enabled: true, borrow_fee_daily_bps: 1.0, locate_required: false }
        },
        tax: {
            regime: "US",
            us: { short_term_days: 365, short_rate: 0.30, long_rate: 0.15 },
            india: { short_term_days: 365, short_rate: 0.15, long_rate: 0.10 },
            lot_method: "FIFO"
        },
        strategy: {
            type: "BUY_AND_HOLD",
            params: {}
        },
        risk: {
            max_position_weight: 0.25,
            max_gross_leverage: 2.0,
            stop_loss: { enabled: false, pct: 0.20 }
        }
    });

    const nextStep = () => setCurrentStep(prev => Math.min(prev + 1, 4));
    const prevStep = () => setCurrentStep(prev => Math.max(prev - 1, 1));
    const updateConfig = (updater: (prev: any) => any) => setConfig(updater);

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Strategy Builder</h1>
                    <p className="text-muted-foreground mt-2">
                        Configure your universe, strategy, and risk parameters realistically.
                    </p>
                </div>
            </div>

            {/* Stepper Header */}
            <div className="flex items-center space-x-2 border-b border-border pb-4 mb-6 text-sm text-muted-foreground">
                <div className={`px-3 py-1 rounded-full ${currentStep === 1 ? 'bg-primary text-primary-foreground font-medium' : currentStep > 1 ? 'bg-muted text-foreground' : ''}`}>1. Universe</div>
                <div className="w-8 h-px bg-border"></div>
                <div className={`px-3 py-1 rounded-full ${currentStep === 2 ? 'bg-primary text-primary-foreground font-medium' : currentStep > 2 ? 'bg-muted text-foreground' : ''}`}>2. Strategy</div>
                <div className="w-8 h-px bg-border"></div>
                <div className={`px-3 py-1 rounded-full ${currentStep === 3 ? 'bg-primary text-primary-foreground font-medium' : currentStep > 3 ? 'bg-muted text-foreground' : ''}`}>3. Realism</div>
                <div className="w-8 h-px bg-border"></div>
                <div className={`px-3 py-1 rounded-full ${currentStep === 4 ? 'bg-primary text-primary-foreground font-medium' : ''}`}>4. Review</div>
            </div>

            {/* Step Content */}
            <div className="bg-card border border-border rounded-lg shadow-sm min-h-[400px]">
                {currentStep === 1 && <UniverseStep config={config} updateConfig={updateConfig} nextStep={nextStep} />}
                {currentStep === 2 && <StrategyStep config={config} updateConfig={updateConfig} nextStep={nextStep} prevStep={prevStep} />}
                {currentStep === 3 && <RealismStep config={config} updateConfig={updateConfig} nextStep={nextStep} prevStep={prevStep} />}
                {currentStep === 4 && <ReviewStep config={config} prevStep={prevStep} />}
            </div>
        </div>
    )
}
