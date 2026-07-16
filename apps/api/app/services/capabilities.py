from __future__ import annotations

from typing import Any


STRATEGY_CAPABILITIES: dict[str, dict[str, Any]] = {
    "BUY_AND_HOLD": {
        "supports_mixed_currency": True,
        "supports_shorting": True,
        "supports_margin": True,
        "allocation_modes": ["equal", "weights", "amounts"],
    },
    "FIXED_WEIGHT_REBALANCE": {
        "supports_mixed_currency": False,
        "supports_shorting": True,
        "supports_margin": True,
        "allocation_modes": ["weights"],
    },
    "DCA": {
        "supports_mixed_currency": False,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal", "weights"],
    },
    "MOMENTUM": {
        "supports_mixed_currency": False,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal"],
    },
    "MEAN_REVERSION": {
        "supports_mixed_currency": False,
        "supports_shorting": False,
        "supports_margin": True,
        "allocation_modes": ["equal"],
    },
}


def get_capabilities() -> dict[str, dict[str, Any]]:
    return {"strategies": STRATEGY_CAPABILITIES}
