from __future__ import annotations

from typing import Any

GLOBAL_PRESET_ACTOR_KEY_PREFIX = "preset:global"

GLOBAL_PRESET_DEFINITIONS: dict[str, dict[str, Any]] = {
    "us-mega-cap-buy-hold": {
        "name": "US Mega Cap Buy & Hold",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "BUY_AND_HOLD",
            "base_currency": "USD",
            "commission": {"model": "BPS", "bps": 5, "min_fee_native": 1},
            "slippage": {"model": "BPS", "bps": 2},
            "fill_price_policy": "CLOSE",
            "universe": {
                "instruments": [
                    {"symbol": "AAPL", "asset_class": "US_EQUITY"},
                    {"symbol": "MSFT", "asset_class": "US_EQUITY"},
                    {"symbol": "GOOGL", "asset_class": "US_EQUITY"},
                    {"symbol": "AMZN", "asset_class": "US_EQUITY"},
                    {"symbol": "META", "asset_class": "US_EQUITY"},
                ],
                "calendars": {"US_EQUITY": "US"},
            },
            "backtest": {
                "start_date": "2020-01-01",
                "end_date": "2023-12-31",
                "initial_cash": 100000,
                "contributions": {"enabled": False},
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
    },
    "india-equity-buy-hold": {
        "name": "India Equity Buy & Hold",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "BUY_AND_HOLD",
            "base_currency": "INR",
            "commission": {"model": "BPS", "bps": 20, "min_fee_native": 20},
            "slippage": {"model": "BPS", "bps": 5},
            "fill_price_policy": "CLOSE",
            "universe": {
                "instruments": [
                    {"symbol": "RELIANCE", "asset_class": "IN_EQUITY"},
                    {"symbol": "TCS", "asset_class": "IN_EQUITY"},
                    {"symbol": "HDFCBANK", "asset_class": "IN_EQUITY"},
                    {"symbol": "ICICIBANK", "asset_class": "IN_EQUITY"},
                    {"symbol": "INFY", "asset_class": "IN_EQUITY"},
                ],
                "calendars": {"IN_EQUITY": "IN"},
            },
            "backtest": {
                "start_date": "2021-01-01",
                "end_date": "2023-12-31",
                "initial_cash": 1000000,
                "contributions": {"enabled": False},
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
    },
    "us-india-mixed-portfolio": {
        "name": "US vs India Mixed Portfolio",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "BUY_AND_HOLD",
            "base_currency": "USD",
            "commission": {"model": "BPS", "bps": 8, "min_fee_native": 1},
            "slippage": {"model": "BPS", "bps": 4},
            "fill_price_policy": "CLOSE",
            "universe": {
                "instruments": [
                    {"symbol": "AAPL", "asset_class": "US_EQUITY", "amount": 15000},
                    {"symbol": "MSFT", "asset_class": "US_EQUITY", "amount": 15000},
                    {"symbol": "RELIANCE", "asset_class": "IN_EQUITY", "amount": 1200000},
                    {"symbol": "TCS", "asset_class": "IN_EQUITY", "amount": 1200000},
                ],
                "calendars": {"US_EQUITY": "US", "IN_EQUITY": "IN"},
            },
            "backtest": {
                "start_date": "2021-01-01",
                "end_date": "2023-12-31",
                "initial_cash": 60000,
                "initial_cash_by_currency": {"USD": 35000, "INR": 2600000},
                "contributions": {"enabled": False},
            },
            "data_policy": {"missing_bar": "FORWARD_FILL", "missing_fx": "FORWARD_FILL"},
        },
    },
    "momentum-top-k": {
        "name": "Momentum Top-K",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "MOMENTUM",
            "strategy_params": {
                "rebalance_frequency": "MONTHLY",
                "lookback_days": 126,
                "top_k": 2,
                "skip_days": 1,
                "weighting": "EQUAL",
            },
            "base_currency": "USD",
            "commission": {"model": "BPS", "bps": 5, "min_fee_native": 1},
            "slippage": {"model": "BPS", "bps": 5},
            "fill_price_policy": "CLOSE",
            "universe": {
                "instruments": [
                    {"symbol": "NVDA", "asset_class": "US_EQUITY"},
                    {"symbol": "AMD", "asset_class": "US_EQUITY"},
                    {"symbol": "TSLA", "asset_class": "US_EQUITY"},
                    {"symbol": "NFLX", "asset_class": "US_EQUITY"},
                    {"symbol": "QQQ", "asset_class": "US_EQUITY"},
                ],
                "calendars": {"US_EQUITY": "US"},
            },
            "backtest": {
                "start_date": "2022-01-01",
                "end_date": "2023-12-31",
                "initial_cash": 50000,
                "contributions": {"enabled": False},
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
    },
    "tax-regime-comparison": {
        "name": "Tax Regime Comparison",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "BUY_AND_HOLD",
            "base_currency": "USD",
            "commission": {"model": "BPS", "bps": 5, "min_fee_native": 1},
            "slippage": {"model": "BPS", "bps": 2},
            "fill_price_policy": "CLOSE",
            "tax": {
                "regime": "US",
                "us": {"short_term_days": 365, "short_rate": 0.30, "long_rate": 0.15},
            },
            "universe": {
                "instruments": [
                    {"symbol": "AAPL", "asset_class": "US_EQUITY", "amount": 25000},
                    {"symbol": "MSFT", "asset_class": "US_EQUITY", "amount": 25000},
                ],
                "calendars": {"US_EQUITY": "US"},
            },
            "backtest": {
                "start_date": "2018-01-01",
                "end_date": "2023-12-31",
                "initial_cash": 60000,
                "contributions": {"enabled": False},
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
    },
    "long-short-margin-stress": {
        "name": "Long/Short Margin Stress Test",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "FIXED_WEIGHT_REBALANCE",
            "strategy_params": {
                "rebalance_frequency": "MONTHLY",
                "target_weights": {
                    "QQQ": 0.85,
                    "SPY": 0.65,
                    "IWM": -0.30,
                    "ARKK": -0.20,
                },
            },
            "base_currency": "USD",
            "commission": {"model": "BPS", "bps": 8, "min_fee_native": 1},
            "slippage": {"model": "BPS", "bps": 6},
            "fill_price_policy": "CLOSE",
            "financing": {
                "margin": {"enabled": True, "max_leverage": 2.0, "daily_interest_bps": 1.5},
                "shorting": {"enabled": True, "borrow_fee_daily_bps": 1.0},
            },
            "risk": {"max_gross_leverage": 2.0, "max_net_leverage": 1.5},
            "universe": {
                "instruments": [
                    {"symbol": "QQQ", "asset_class": "US_EQUITY"},
                    {"symbol": "SPY", "asset_class": "US_EQUITY"},
                    {"symbol": "IWM", "asset_class": "US_EQUITY"},
                    {"symbol": "ARKK", "asset_class": "US_EQUITY"},
                ],
                "calendars": {"US_EQUITY": "US"},
            },
            "backtest": {
                "start_date": "2020-01-01",
                "end_date": "2023-12-31",
                "initial_cash": 100000,
                "contributions": {"enabled": False},
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
    },
}


def global_preset_actor_key(preset_id: str) -> str:
    return f"{GLOBAL_PRESET_ACTOR_KEY_PREFIX}:{preset_id}"
