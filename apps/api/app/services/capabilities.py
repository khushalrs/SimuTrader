from __future__ import annotations

from typing import Any


ASSET_CLASS_CURRENCIES: dict[str, str] = {
    "US_EQUITY": "USD",
    "IN_EQUITY": "INR",
}

ASSET_CLASS_COUNTRIES: dict[str, str] = {
    "US_EQUITY": "US",
    "IN_EQUITY": "IN",
}


def currency_for_asset_class(asset_class: str) -> str | None:
    return ASSET_CLASS_CURRENCIES.get(str(asset_class or "").upper())


def country_for_asset_class(asset_class: str) -> str:
    return ASSET_CLASS_COUNTRIES.get(str(asset_class or "").upper(), "UNKNOWN")


STRATEGY_CAPABILITIES: dict[str, dict[str, Any]] = {
    "BUY_AND_HOLD": {
        "description": (
            "Invest once using equal weights, instrument weights, or native-value amounts, "
            "then hold the resulting positions for the run."
        ),
        "required_params": [],
        "optional_params": [],
        "defaults": {},
        "param_types": {},
        "supports_mixed_currency": True,
        "supports_shorting": True,
        "supports_margin": True,
        "allocation_modes": ["equal", "weights", "amounts"],
        "supported_allocation_modes": ["equal", "weights", "amounts"],
        "supported_asset_classes": ["US_EQUITY", "IN_EQUITY"],
    },
    "FIXED_WEIGHT_REBALANCE": {
        "description": (
            "Rebalance the portfolio to signed target weights on a schedule, optionally "
            "only when allocation drift reaches a threshold."
        ),
        "required_params": ["target_weights"],
        "optional_params": ["rebalance_frequency", "drift_threshold"],
        "defaults": {
            "rebalance_frequency": "MONTHLY",
            "drift_threshold": 0.0,
        },
        "param_types": {
            "target_weights": {
                "type": "object",
                "value_type": "number",
                "description": "The target percentage allocation weight for each asset (must sum to 100% or will be normalized)."
            },
            "rebalance_frequency": {
                "type": "string",
                "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"],
                "description": "How often the strategy portfolio is checked and adjusted to match target allocations."
            },
            "drift_threshold": {
                "type": "number",
                "min": 0.0,
                "max": 1.0,
                "description": "The percentage allocation drift (e.g. 0.05 for 5%) that triggers an out-of-schedule rebalancing of assets."
            },
        },
        "supports_mixed_currency": True,
        "supports_shorting": True,
        "supports_margin": True,
        "allocation_modes": ["weights"],
        "supported_allocation_modes": ["weights"],
        "supported_asset_classes": ["US_EQUITY", "IN_EQUITY"],
    },
    "DCA": {
        "description": (
            "Deploy available cash incrementally without rebalancing existing holdings; "
            "contribution amount and frequency are configured under backtest.contributions."
        ),
        "required_params": [],
        "optional_params": ["buy_frequency", "weighting", "target_weights"],
        "defaults": {
            "buy_frequency": "MONTHLY",
            "weighting": "EQUAL",
            "target_weights": {},
        },
        "param_types": {
            "buy_frequency": {
                "type": "string",
                "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"],
                "description": "How often periodic buy allocations are executed."
            },
            "weighting": {
                "type": "string",
                "enum": ["EQUAL", "TARGET_WEIGHTS", "INSTRUMENT_WEIGHTS"],
                "description": "The portfolio weighting methodology (e.g. equal weights, risk-parity, or value-weighted)."
            },
            "target_weights": {
                "type": "object",
                "value_type": "number",
                "value_exclusive_min": 0.0,
                "description": "Custom target weights to use if weighting is set to TARGET_WEIGHTS."
            },
        },
        "supports_mixed_currency": True,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal", "weights"],
        "supported_allocation_modes": ["equal", "weights"],
        "supported_asset_classes": ["US_EQUITY", "IN_EQUITY"],
    },
    "MOMENTUM": {
        "description": (
            "Rank instruments by trailing return after a skip window and allocate equally "
            "to the strongest top-k instruments on each rebalance date."
        ),
        "required_params": ["lookback_days", "top_k"],
        "optional_params": ["skip_days", "rebalance_frequency", "weighting"],
        "defaults": {
            "skip_days": 1,
            "rebalance_frequency": "MONTHLY",
            "weighting": "EQUAL",
        },
        "param_types": {
            "lookback_days": {
                "type": "integer",
                "min": 1,
                "description": "The number of historical trading days used to calculate asset performance (e.g. 252 days for 1 year)."
            },
            "skip_days": {
                "type": "integer",
                "min": 0,
                "description": "The number of recent trading days to ignore to avoid short-term market noise or mean reversion effects."
            },
            "top_k": {
                "type": "integer",
                "min": 1,
                "description": "The maximum number of top-performing assets to purchase during each rebalancing cycle."
            },
            "rebalance_frequency": {
                "type": "string",
                "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"],
                "description": "How often the strategy portfolio is checked and adjusted to match target allocations."
            },
            "weighting": {
                "type": "string",
                "enum": ["EQUAL"],
                "description": "The portfolio weighting methodology (e.g. equal weights)."
            },
        },
        "supports_mixed_currency": True,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal"],
        "supported_allocation_modes": ["equal"],
        "supported_asset_classes": ["US_EQUITY", "IN_EQUITY"],
    },
    "MEAN_REVERSION": {
        "description": (
            "Enter instruments trading sufficiently below their rolling mean and exit by "
            "a mean-reversion threshold or a configured holding period."
        ),
        "required_params": ["lookback_days", "entry_threshold"],
        "optional_params": [
            "exit_threshold",
            "hold_days",
            "rebalance_frequency",
        ],
        "defaults": {"rebalance_frequency": "DAILY"},
        "param_types": {
            "lookback_days": {
                "type": "integer",
                "min": 1,
                "description": "The number of historical trading days used to calculate rolling moving average indicators (e.g., 20 days for 1 month)."
            },
            "entry_threshold": {
                "type": "number",
                "exclusive_min": 0.0,
                "description": "The statistical Z-Score threshold at which to trigger a buy order (e.g. 2.0 standard deviations)."
            },
            "exit_threshold": {
                "type": "number",
                "min": 0.0,
                "description": "The statistical Z-Score threshold at which to close an active position (must be less than the entry threshold, e.g. 0.0)."
            },
            "hold_days": {
                "type": "integer",
                "min": 1,
                "description": "The maximum number of calendar days to hold an active position before auto-exiting."
            },
            "rebalance_frequency": {
                "type": "string",
                "enum": ["DAILY", "WEEKLY"],
                "description": "How often the strategy portfolio is checked and adjusted to match target allocations."
            },
        },
        "supports_mixed_currency": True,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal"],
        "supported_allocation_modes": ["equal"],
        "supported_asset_classes": ["US_EQUITY", "IN_EQUITY"],
    },
}


def strategy_supports_mixed_currency(strategy: str) -> bool:
    capability = STRATEGY_CAPABILITIES.get(str(strategy or "").upper()) or {}
    return bool(capability.get("supports_mixed_currency"))


def get_capabilities() -> dict[str, dict[str, Any]]:
    return {"strategies": STRATEGY_CAPABILITIES}


def get_strategy_schemas() -> dict[str, dict[str, Any]]:
    return STRATEGY_CAPABILITIES
