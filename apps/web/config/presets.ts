import { TrendingUp, Layers, Zap, Activity } from "lucide-react"

export interface PresetConfig {
    id: string
    title: string
    universe: string
    behavior: string
    icon: any
    color: string
    config_snapshot: any
}

export const presets: PresetConfig[] = [
    {
        id: "buy-hold-us",
        title: "Buy & Hold — US Mega Cap",
        universe: "S&P 500 Top 50",
        behavior: "Passive indexing with quarterly rebalancing.",
        icon: TrendingUp,
        color: "text-blue-500",
        config_snapshot: {
            version: 1,
            strategy: "BUY_AND_HOLD",
            strategy_params: {
                rebalance_frequency: "quarterly"
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
        title: "Equal Weight — India Top 10",
        universe: "NIFTY 50 Top 10",
        behavior: "Contrarian rebalancing to equal weights.",
        icon: Layers,
        color: "text-orange-500",
        config_snapshot: {
            version: 1,
            strategy: "FIXED_WEIGHT_REBALANCE",
            strategy_params: {
                rebalance_frequency: "monthly",
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
        title: "Momentum — Top K Monthly",
        universe: "Nasdaq 100",
        behavior: "Aggressive rotation into winners.",
        icon: Zap,
        color: "text-yellow-500",
        config_snapshot: {
            version: 1,
            strategy: "MOMENTUM",
            strategy_params: {
                rebalance_frequency: "monthly",
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
        title: "Mean Reversion — Conservative",
        universe: "Russell 2000",
        behavior: "Buying dips, selling rips.",
        icon: Activity,
        color: "text-green-500",
        config_snapshot: {
            version: 1,
            strategy: "MEAN_REVERSION",
            strategy_params: {
                entry_z_score: -2.0,
                exit_z_score: 0.0,
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
