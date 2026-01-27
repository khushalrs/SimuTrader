"""Calendar policy helpers for the backtest engine."""

from __future__ import annotations

from typing import Dict

strict_missing_bar = True


def calendar_for_asset_class(asset_class: str, config_calendars_map: Dict[str, str] | None = None) -> str:
    if config_calendars_map and asset_class in config_calendars_map:
        return config_calendars_map[asset_class]

    mapping = {
        "US_EQUITY": "US",
        "IN_EQUITY": "IN",
        "FX": "FX",
    }
    asset_class_norm = str(asset_class).strip().upper()
    if asset_class_norm not in mapping:
        raise ValueError(f"Unknown asset class '{asset_class_norm}'")
    return mapping[asset_class_norm]


def is_market_open(flags_row: dict, cal_name: str) -> bool:
    cal_norm = str(cal_name).strip().upper()
    key_map = {
        "US": "is_us_trading",
        "IN": "is_in_trading",
        "FX": "is_fx_trading",
    }
    key = key_map.get(cal_norm)
    if key is None:
        raise ValueError(f"Unsupported calendar '{cal_norm}'")
    return bool(flags_row.get(key))
