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
        "supports_mixed_currency": True,
        "supports_shorting": True,
        "supports_margin": True,
        "allocation_modes": ["equal", "weights", "amounts"],
    },
    "FIXED_WEIGHT_REBALANCE": {
        "supports_mixed_currency": True,
        "supports_shorting": True,
        "supports_margin": True,
        "allocation_modes": ["weights"],
    },
    "DCA": {
        "supports_mixed_currency": True,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal", "weights"],
    },
    "MOMENTUM": {
        "supports_mixed_currency": True,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal"],
    },
    "MEAN_REVERSION": {
        "supports_mixed_currency": True,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal"],
    },
}


def strategy_supports_mixed_currency(strategy: str) -> bool:
    capability = STRATEGY_CAPABILITIES.get(str(strategy or "").upper()) or {}
    return bool(capability.get("supports_mixed_currency"))


def get_capabilities() -> dict[str, dict[str, Any]]:
    return {"strategies": STRATEGY_CAPABILITIES}
