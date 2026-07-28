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
                "unit": "fraction",
                "description": (
                    "Signed target allocation by symbol. Values are fractions of equity "
                    "(0.25 means 25%); the engine normalizes by total absolute weight."
                ),
            },
            "rebalance_frequency": {
                "type": "string",
                "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"],
                "unit": "cadence",
                "description": "How often target allocations are evaluated and rebalanced.",
            },
            "drift_threshold": {
                "type": "number",
                "min": 0.0,
                "max": 1.0,
                "unit": "fraction",
                "description": (
                    "Minimum absolute allocation drift that triggers a rebalance "
                    "(0.05 means five percentage points)."
                ),
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
                "unit": "cadence",
                "description": "How often available contribution cash is invested.",
            },
            "weighting": {
                "type": "string",
                "enum": ["EQUAL", "TARGET_WEIGHTS", "INSTRUMENT_WEIGHTS"],
                "unit": "allocation_mode",
                "description": (
                    "How each contribution is allocated: equally, by strategy target "
                    "weights, or by weights on the configured instruments."
                ),
            },
            "target_weights": {
                "type": "object",
                "value_type": "number",
                "value_exclusive_min": 0.0,
                "unit": "fraction",
                "description": (
                    "Positive allocation fraction by symbol when weighting is "
                    "TARGET_WEIGHTS."
                ),
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
                "unit": "trading_days",
                "description": "Historical trading observations used to measure trailing return.",
            },
            "skip_days": {
                "type": "integer",
                "min": 0,
                "unit": "trading_days",
                "description": (
                    "Most-recent trading observations excluded from the momentum window."
                ),
            },
            "top_k": {
                "type": "integer",
                "min": 1,
                "unit": "instruments",
                "description": "Maximum number of highest-ranked instruments selected.",
            },
            "rebalance_frequency": {
                "type": "string",
                "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"],
                "unit": "cadence",
                "description": "How often momentum ranks and target allocations are refreshed.",
            },
            "weighting": {
                "type": "string",
                "enum": ["EQUAL"],
                "unit": "allocation_mode",
                "description": (
                    "Allocation method for selected instruments; currently equal weight."
                ),
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
                "unit": "trading_days",
                "description": (
                    "Historical trading observations used for the rolling mean and deviation."
                ),
            },
            "entry_threshold": {
                "type": "number",
                "exclusive_min": 0.0,
                "unit": "z_score",
                "description": (
                    "Positive z-score magnitude below the rolling mean required to enter."
                ),
            },
            "exit_threshold": {
                "type": "number",
                "min": 0.0,
                "unit": "z_score",
                "description": "Absolute z-score at or below which an open position exits.",
            },
            "hold_days": {
                "type": "integer",
                "min": 1,
                "unit": "evaluation_intervals",
                "description": "Maximum strategy evaluation intervals held before forced exit.",
            },
            "rebalance_frequency": {
                "type": "string",
                "enum": ["DAILY", "WEEKLY"],
                "unit": "cadence",
                "description": "How often entry and exit conditions are evaluated.",
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
