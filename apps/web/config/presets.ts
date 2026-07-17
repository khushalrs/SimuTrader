import { TrendingUp, Layers, Zap, Activity } from "lucide-react"

export interface PresetConfig {
    id: string
    title: string
    universe: string
    behavior: string
    icon: any
    color: string
    whatItDemonstrates: string
    universeDetails: string
    strategyType: string
    realismSettings: string
    expectedInsight: string
    config_snapshot: any
}

export const presets: PresetConfig[] = [
    {
        id: "buy-hold-us",
        title: "Buy & Hold — US Mega Cap",
        universe: "S&P 500 Top 5",
        behavior: "Passive indexing with quarterly rebalancing.",
        icon: TrendingUp,
        color: "text-blue-500",
        whatItDemonstrates: "Passive equity compounding and quarterly rebalancing rules.",
        universeDetails: "US Equities: AAPL, MSFT, GOOGL, AMZN, META",
        strategyType: "BUY_AND_HOLD (Equal Weight initial)",
        realismSettings: "US Taxes (30% ST, 15% LT), 5bps commission, 2bps slippage",
        expectedInsight: "Highlights long term compound interest curves under moderate friction.",
        config_snapshot: {
            version: 1,
            strategy: "BUY_AND_HOLD",
            strategy_params: {
                rebalance_frequency: "QUARTERLY"
            },
            base_currency: "USD",
            commission: {
                model: "BPS",
                bps: 5,
                min_fee_native: 1
            },
            slippage: {
                model: "BPS",
                bps: 2
            },
            fill_price_policy: "CLOSE",
            universe: {
                instruments: [
                    { symbol: "AAPL", asset_class: "US_EQUITY" },
                    { symbol: "MSFT", asset_class: "US_EQUITY" },
                    { symbol: "GOOGL", asset_class: "US_EQUITY" },
                    { symbol: "AMZN", asset_class: "US_EQUITY" },
                    { symbol: "META", asset_class: "US_EQUITY" }
                ],
                calendars: {
                    US_EQUITY: "US"
                }
            },
            backtest: {
                start_date: "2020-01-01",
                end_date: "2023-12-31",
                initial_cash: 100000,
                contributions: {
                    enabled: false
                }
            },
            data_policy: {
                missing_bar: "FORWARD_FILL"
            }
        }
    },
    {
        id: "equal-weight-in",
        title: "Tax Regime Comparison",
        universe: "India Listed Top 5",
        behavior: "Contrarian rebalancing under India listed equity tax rules.",
        icon: Layers,
        color: "text-orange-500",
        whatItDemonstrates: "How identical trades generate different net returns under US vs India tax parameters.",
        universeDetails: "India Equities: RELIANCE, TCS, HDFCBANK, ICICIBANK, INFY",
        strategyType: "FIXED_WEIGHT_REBALANCE (20% Target weight, Monthly)",
        realismSettings: "India Taxes (20% ST, 12.5% LT), 20bps commission, 5bps slippage",
        expectedInsight: "Demonstrates listed equity capital gains efficiency post-July 2024 tax codes.",
        config_snapshot: {
            version: 1,
            strategy: "FIXED_WEIGHT_REBALANCE",
            strategy_params: {
                rebalance_frequency: "MONTHLY",
                weights: {
                    "RELIANCE": 0.2,
                    "TCS": 0.2,
                    "HDFCBANK": 0.2,
                    "ICICIBANK": 0.2,
                    "INFY": 0.2
                }
            },
            base_currency: "INR",
            commission: {
                model: "BPS",
                bps: 20,
                min_fee_native: 20
            },
            slippage: {
                model: "BPS",
                bps: 5
            },
            fill_price_policy: "CLOSE",
            universe: {
                instruments: [
                    { symbol: "RELIANCE", asset_class: "IN_EQUITY" },
                    { symbol: "TCS", asset_class: "IN_EQUITY" },
                    { symbol: "HDFCBANK", asset_class: "IN_EQUITY" },
                    { symbol: "ICICIBANK", asset_class: "IN_EQUITY" },
                    { symbol: "INFY", asset_class: "IN_EQUITY" }
                ],
                calendars: {
                    IN_EQUITY: "IN"
                }
            },
            backtest: {
                start_date: "2021-01-01",
                end_date: "2023-12-31",
                initial_cash: 1000000,
                contributions: {
                    enabled: false
                }
            },
            data_policy: {
                missing_bar: "FORWARD_FILL"
            }
        }
    },
    {
        id: "momentum",
        title: "Momentum — Nasdaq Rotator",
        universe: "Nasdaq High Beta Tech",
        behavior: "Aggressive re-allocation into top performers.",
        icon: Zap,
        color: "text-yellow-500",
        whatItDemonstrates: "Lookback-driven momentum rotation under strict commission friction.",
        universeDetails: "US Equities: NVDA, AMD, TSLA, NFLX, QQQ",
        strategyType: "MOMENTUM (Top 2 winners, skip 21 days, Monthly rebalance)",
        realismSettings: "US Taxes, 5bps commission, 5bps slippage, margin enabled",
        expectedInsight: "Shows how high turnover generates high transaction cost drag.",
        config_snapshot: {
            version: 1,
            strategy: "MOMENTUM",
            strategy_params: {
                rebalance_frequency: "MONTHLY",
                lookback_days: 126,
                top_k: 2
            },
            base_currency: "USD",
            commission: {
                model: "BPS",
                bps: 5,
                min_fee_native: 1
            },
            slippage: {
                model: "BPS",
                bps: 5
            },
            fill_price_policy: "CLOSE",
            universe: {
                instruments: [
                    { symbol: "NVDA", asset_class: "US_EQUITY" },
                    { symbol: "AMD", asset_class: "US_EQUITY" },
                    { symbol: "TSLA", asset_class: "US_EQUITY" },
                    { symbol: "NFLX", asset_class: "US_EQUITY" },
                    { symbol: "QQQ", asset_class: "US_EQUITY" }
                ],
                calendars: {
                    US_EQUITY: "US"
                }
            },
            backtest: {
                start_date: "2022-01-01",
                end_date: "2023-12-31",
                initial_cash: 50000,
                contributions: {
                    enabled: false
                }
            },
            data_policy: {
                missing_bar: "FORWARD_FILL"
            }
        }
    },
    {
        id: "mean-reversion",
        title: "Mean Reversion — Small Cap Dip Buyer",
        universe: "Small Cap & Growth ETFs",
        behavior: "Counter-trend dip buying and mean reversion exit.",
        icon: Activity,
        color: "text-green-500",
        whatItDemonstrates: "Short term Z-score reversal entries and trade-holding limit exits.",
        universeDetails: "US ETFs: IWM, ARKK, XBI",
        strategyType: "MEAN_REVERSION (Z-Score entry at 2.0, 5-day holding lock)",
        realismSettings: "US Taxes, 5bps commission, 2bps slippage",
        expectedInsight: "Exposes the interaction of short-term tax rates on high-velocity strategy gains.",
        config_snapshot: {
            version: 1,
            strategy: "MEAN_REVERSION",
            strategy_params: {
                entry_threshold: 2.0,
                exit_threshold: 0.0,
                lookback_days: 20
            },
            base_currency: "USD",
            commission: {
                model: "BPS",
                bps: 5,
                min_fee_native: 1
            },
            slippage: {
                model: "BPS",
                bps: 2
            },
            fill_price_policy: "CLOSE",
            universe: {
                instruments: [
                    { symbol: "IWM", asset_class: "US_EQUITY" },
                    { symbol: "ARKK", asset_class: "US_EQUITY" },
                    { symbol: "XBI", asset_class: "US_EQUITY" }
                ],
                calendars: {
                    US_EQUITY: "US"
                }
            },
            backtest: {
                start_date: "2018-01-01",
                end_date: "2023-12-31",
                initial_cash: 250000,
                contributions: {
                    enabled: false
                }
            },
            data_policy: {
                missing_bar: "FORWARD_FILL"
            }
        }
    }
]
