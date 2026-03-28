from __future__ import annotations

from typing import Any

GLOBAL_PRESET_ACTOR_KEY_PREFIX = "preset:global"

GLOBAL_PRESET_DEFINITIONS: dict[str, dict[str, Any]] = {
    "buy-hold-us": {
        "name": "Preset: Buy & Hold - US Mega Cap",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "BUY_AND_HOLD",
            "strategy_params": {"rebalance_frequency": "quarterly"},
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
    "equal-weight-in": {
        "name": "Preset: Equal Weight - India Top 10",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "FIXED_WEIGHT_REBALANCE",
            "strategy_params": {
                "rebalance_frequency": "monthly",
                "target_weights": {
                    "RELIANCE": 0.2,
                    "TCS": 0.2,
                    "HDFCBANK": 0.2,
                    "ICICIBANK": 0.2,
                    "INFY": 0.2,
                },
            },
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
    "momentum": {
        "name": "Preset: Momentum - Top K Monthly",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "MOMENTUM",
            "strategy_params": {
                "rebalance_frequency": "monthly",
                "lookback_days": 126,
                "top_k": 2,
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
    "mean-reversion": {
        "name": "Preset: Mean Reversion - Conservative",
        "seed": 42,
        "data_snapshot_id": "default_snapshot_2026",
        "config_snapshot": {
            "version": 1,
            "strategy": "MEAN_REVERSION",
            "strategy_params": {
                "entry_threshold": 2.0,
                "exit_threshold": 0.5,
                "lookback_days": 20,
            },
            "base_currency": "USD",
            "commission": {"model": "BPS", "bps": 5, "min_fee_native": 1},
            "slippage": {"model": "BPS", "bps": 2},
            "fill_price_policy": "CLOSE",
            "universe": {
                "instruments": [
                    {"symbol": "IWM", "asset_class": "US_EQUITY"},
                    {"symbol": "ARKK", "asset_class": "US_EQUITY"},
                    {"symbol": "XBI", "asset_class": "US_EQUITY"},
                ],
                "calendars": {"US_EQUITY": "US"},
            },
            "backtest": {
                "start_date": "2018-01-01",
                "end_date": "2023-12-31",
                "initial_cash": 250000,
                "contributions": {"enabled": False},
            },
            "data_policy": {"missing_bar": "FORWARD_FILL"},
        },
    },
}


def global_preset_actor_key(preset_id: str) -> str:
    return f"{GLOBAL_PRESET_ACTOR_KEY_PREFIX}:{preset_id}"
