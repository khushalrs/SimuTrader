"""JSON Schema validation + defaulting for backtest configs."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker, validators

CONFIG_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "version": {"type": "integer", "minimum": 1, "default": 1},
        "strategy": {
            "type": "string",
            "enum": ["BUY_AND_HOLD"],
            "default": "BUY_AND_HOLD",
        },
        "base_currency": {"type": "string", "enum": ["USD", "INR"], "default": "USD"},
        "commission": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "model": {"type": "string", "enum": ["BPS"], "default": "BPS"},
                "bps": {"type": "number", "minimum": 0, "default": 0},
                "min_fee_native": {"type": "number", "minimum": 0, "default": 0},
            },
            "default": {"model": "BPS", "bps": 0, "min_fee_native": 0},
        },
        "slippage": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "model": {"type": "string", "enum": ["BPS"], "default": "BPS"},
                "bps": {"type": "number", "minimum": 0, "default": 0},
            },
            "default": {"model": "BPS", "bps": 0},
        },
        "fill_price_policy": {
            "type": "string",
            "enum": ["CLOSE"],
            "default": "CLOSE",
        },
        "universe": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "instruments": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "symbol": {"type": "string", "minLength": 1},
                            "asset_class": {
                                "type": "string",
                                "enum": ["US_EQUITY", "IN_EQUITY", "FX"],
                            },
                            "amount": {"type": "number", "exclusiveMinimum": 0},
                            "weight": {"type": "number", "exclusiveMinimum": 0},
                        },
                        "required": ["symbol", "asset_class"],
                        "allOf": [
                            {
                                "not": {
                                    "required": ["amount", "weight"],
                                }
                            }
                        ],
                    },
                },
                "calendars": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "US_EQUITY": {"type": "string"},
                        "IN_EQUITY": {"type": "string"},
                        "FX": {"type": "string"},
                    },
                },
            },
            "required": ["instruments"],
        },
        "backtest": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "initial_cash": {"type": "number", "exclusiveMinimum": 0},
                "initial_cash_by_currency": {
                    "type": "object",
                    "additionalProperties": {"type": "number", "exclusiveMinimum": 0},
                },
            },
            "required": ["start_date", "end_date", "initial_cash"],
        },
        "data_policy": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "missing_bar": {
                    "type": "string",
                    "enum": ["FAIL", "FORWARD_FILL"],
                    "default": "FAIL",
                }
            },
            "default": {"missing_bar": "FAIL"},
        },
    },
    "required": ["version", "universe", "backtest"],
}


def _extend_with_default(validator_class):
    validate_props = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):  # noqa: ANN001
        if isinstance(instance, dict):
            for prop, subschema in properties.items():
                if "default" in subschema and prop not in instance:
                    instance[prop] = copy.deepcopy(subschema["default"])
        yield from validate_props(validator, properties, instance, schema)

    return validators.extend(validator_class, {"properties": set_defaults})


def _format_error(err) -> str:
    path = ".".join(str(part) for part in err.absolute_path)
    if path:
        return f"{path}: {err.message}"
    return err.message


def _normalize_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("config_snapshot must be an object")
    config: Dict[str, Any] = copy.deepcopy(raw)

    universe = config.get("universe") or {}
    instruments = list(universe.get("instruments") or [])
    if not instruments:
        symbol = config.get("symbol")
        asset_class = config.get("asset_class")
        amount = config.get("amount")
        weight = config.get("weight")
        if symbol or asset_class or amount is not None or weight is not None:
            instrument: Dict[str, Any] = {
                "symbol": symbol,
                "asset_class": asset_class,
            }
            if amount is not None:
                instrument["amount"] = amount
            if weight is not None:
                instrument["weight"] = weight
            instruments = [instrument]
    if instruments:
        universe["instruments"] = instruments
        config["universe"] = universe

    backtest = config.get("backtest") or {}
    for key in ("start_date", "end_date", "initial_cash"):
        if key not in backtest and key in config:
            backtest[key] = config[key]
    if "initial_cash_by_currency" not in backtest and "initial_cash_by_currency" in config:
        backtest["initial_cash_by_currency"] = config["initial_cash_by_currency"]
    config["backtest"] = backtest

    for key in (
        "symbol",
        "asset_class",
        "amount",
        "weight",
        "start_date",
        "end_date",
        "initial_cash",
        "initial_cash_by_currency",
    ):
        if key in config:
            config.pop(key)

    return config


def validate_and_resolve_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    config = _normalize_config(raw)
    validator_cls = _extend_with_default(Draft202012Validator)
    validator = validator_cls(CONFIG_SCHEMA, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(config), key=lambda err: list(err.absolute_path))
    if errors:
        message = "; ".join(_format_error(err) for err in errors)
        raise ValueError(f"Invalid config: {message}")
    _validate_cross_fields(config)
    return config


def _parse_date(value: Any, field_name: str) -> date:
    if value is None:
        raise ValueError(f"Missing {field_name} in backtest config")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} format: {value}") from exc


def _validate_cross_fields(config: Dict[str, Any]) -> None:
    backtest = config.get("backtest") or {}
    start_date = _parse_date(backtest.get("start_date"), "start_date")
    end_date = _parse_date(backtest.get("end_date"), "end_date")
    if end_date < start_date:
        raise ValueError("Invalid config: end_date must be >= start_date")


    instruments = (config.get("universe") or {}).get("instruments") or []
    has_amount = any("amount" in inst for inst in instruments)
    has_weight = any("weight" in inst for inst in instruments)
    if has_amount and has_weight:
        raise ValueError("Invalid config: cannot mix amount and weight across instruments")
    if has_amount:
        missing = [inst.get("symbol") for inst in instruments if "amount" not in inst]
        if missing:
            raise ValueError(
                f"Invalid config: amount required for all instruments (missing: {missing})"
            )
    if has_weight:
        missing = [inst.get("symbol") for inst in instruments if "weight" not in inst]
        if missing:
            raise ValueError(
                f"Invalid config: weight required for all instruments (missing: {missing})"
            )
    if has_amount and "initial_cash_by_currency" not in backtest:
        initial_cash = float(backtest.get("initial_cash") or 0)
        total_amount = sum(float(inst.get("amount") or 0) for inst in instruments)
        if total_amount > initial_cash:
            raise ValueError(
                f"Invalid config: total amount {total_amount:.2f} exceeds initial_cash {initial_cash:.2f}"
            )
