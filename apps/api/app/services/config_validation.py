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
            "enum": ["BUY_AND_HOLD", "FIXED_WEIGHT_REBALANCE", "DCA", "MOMENTUM", "MEAN_REVERSION"],
            "default": "BUY_AND_HOLD",
        },
        "strategy_params": {
            "type": "object",
            "default": {},
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
                "contributions": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "enabled": {"type": "boolean", "default": False},
                        "amount": {"type": "number", "exclusiveMinimum": 0},
                        "frequency": {
                            "type": "string",
                            "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"],
                            "default": "MONTHLY",
                        },
                    },
                    "default": {"enabled": False},
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

    strategy = config.get("strategy")
    if isinstance(strategy, dict):
        strategy_type = strategy.get("type")
        if not strategy_type:
            raise ValueError("strategy.type is required when strategy is an object")
        if "strategy_params" not in config and "params" in strategy:
            config["strategy_params"] = strategy.get("params") or {}
        config["strategy"] = strategy_type

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
    if "contributions" not in backtest and "contributions" in config:
        backtest["contributions"] = config["contributions"]
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
        "contributions",
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

    strategy = str(config.get("strategy") or "BUY_AND_HOLD").upper()
    if strategy == "FIXED_WEIGHT_REBALANCE":
        params = config.get("strategy_params") or {}
        target_weights = params.get("target_weights") or {}
        if not isinstance(target_weights, dict) or not target_weights:
            raise ValueError(
                "Invalid config: strategy_params.target_weights is required for FIXED_WEIGHT_REBALANCE"
            )
        weight_sum = 0.0
        for symbol, weight in target_weights.items():
            if not symbol:
                raise ValueError("Invalid config: target_weights keys must be symbols")
            try:
                weight_val = float(weight)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid config: target_weights for {symbol} must be numeric"
                ) from exc
            if weight_val <= 0:
                raise ValueError(
                    f"Invalid config: target_weights for {symbol} must be > 0"
                )
            weight_sum += weight_val
        if weight_sum <= 0:
            raise ValueError("Invalid config: target_weights sum must be > 0")

        instrument_symbols = {str(inst.get("symbol")) for inst in instruments}
        weight_symbols = set(target_weights.keys())
        missing = instrument_symbols - weight_symbols
        extra = weight_symbols - instrument_symbols
        if missing:
            raise ValueError(
                f"Invalid config: target_weights missing symbols from universe: {sorted(missing)}"
            )
        if extra:
            raise ValueError(
                f"Invalid config: target_weights has unknown symbols: {sorted(extra)}"
            )

        drift_threshold = params.get("drift_threshold")
        if drift_threshold is not None:
            try:
                drift_val = float(drift_threshold)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Invalid config: drift_threshold must be numeric"
                ) from exc
            if drift_val < 0 or drift_val > 1:
                raise ValueError(
                    "Invalid config: drift_threshold must be between 0 and 1"
                )
    if strategy == "DCA":
        params = config.get("strategy_params") or {}
        buy_frequency = params.get("buy_frequency")
        if buy_frequency is not None:
            buy_freq = str(buy_frequency).upper()
            if buy_freq not in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}:
                raise ValueError(
                    "Invalid config: strategy_params.buy_frequency must be DAILY, WEEKLY, MONTHLY, or QUARTERLY"
                )
        weighting = params.get("weighting")
        if weighting is not None:
            weight_mode = str(weighting).upper()
            if weight_mode not in {"EQUAL", "TARGET_WEIGHTS", "INSTRUMENT_WEIGHTS"}:
                raise ValueError(
                    "Invalid config: strategy_params.weighting must be EQUAL, TARGET_WEIGHTS, or INSTRUMENT_WEIGHTS"
                )
        contrib = (backtest.get("contributions") or {}) if backtest else {}
        if contrib.get("enabled"):
            amount = contrib.get("amount")
            if amount is None:
                raise ValueError(
                    "Invalid config: backtest.contributions.amount is required when enabled"
                )
            if float(amount) <= 0:
                raise ValueError(
                    "Invalid config: backtest.contributions.amount must be > 0"
                )
            freq = str(contrib.get("frequency") or "MONTHLY").upper()
            if freq not in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}:
                raise ValueError(
                    "Invalid config: backtest.contributions.frequency must be DAILY, WEEKLY, MONTHLY, or QUARTERLY"
                )
    if strategy == "MOMENTUM":
        params = config.get("strategy_params") or {}
        lookback_days = params.get("lookback_days")
        if lookback_days is None:
            raise ValueError("Invalid config: strategy_params.lookback_days is required")
        try:
            lookback_val = int(lookback_days)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid config: strategy_params.lookback_days must be an integer"
            ) from exc
        if lookback_val <= 0:
            raise ValueError("Invalid config: lookback_days must be > 0")

        skip_days = params.get("skip_days", 1)
        try:
            skip_val = int(skip_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid config: skip_days must be an integer") from exc
        if skip_val < 0:
            raise ValueError("Invalid config: skip_days must be >= 0")

        top_k = params.get("top_k")
        if top_k is None:
            raise ValueError("Invalid config: strategy_params.top_k is required")
        try:
            top_k_val = int(top_k)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid config: top_k must be an integer") from exc
        if top_k_val <= 0:
            raise ValueError("Invalid config: top_k must be > 0")
        if instruments and top_k_val > len(instruments):
            raise ValueError(
                "Invalid config: top_k cannot exceed number of instruments"
            )

        rebalance_frequency = params.get("rebalance_frequency", "MONTHLY")
        freq = str(rebalance_frequency).upper()
        if freq not in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}:
            raise ValueError(
                "Invalid config: rebalance_frequency must be DAILY, WEEKLY, MONTHLY, or QUARTERLY"
            )

        weighting = params.get("weighting", "EQUAL")
        if str(weighting).upper() != "EQUAL":
            raise ValueError("Invalid config: MOMENTUM weighting must be EQUAL")
    if strategy == "MEAN_REVERSION":
        params = config.get("strategy_params") or {}
        lookback_days = params.get("lookback_days")
        if lookback_days is None:
            raise ValueError("Invalid config: strategy_params.lookback_days is required")
        try:
            lookback_val = int(lookback_days)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid config: strategy_params.lookback_days must be an integer"
            ) from exc
        if lookback_val <= 0:
            raise ValueError("Invalid config: lookback_days must be > 0")

        entry_threshold = params.get("entry_threshold")
        if entry_threshold is None:
            raise ValueError("Invalid config: strategy_params.entry_threshold is required")
        try:
            entry_val = float(entry_threshold)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid config: strategy_params.entry_threshold must be numeric"
            ) from exc
        if entry_val <= 0:
            raise ValueError("Invalid config: entry_threshold must be > 0")

        exit_threshold = params.get("exit_threshold")
        hold_days = params.get("hold_days")
        if exit_threshold is None and hold_days is None:
            raise ValueError(
                "Invalid config: strategy_params.exit_threshold or hold_days is required"
            )
        if exit_threshold is not None:
            try:
                exit_val = float(exit_threshold)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Invalid config: strategy_params.exit_threshold must be numeric"
                ) from exc
            if exit_val < 0:
                raise ValueError("Invalid config: exit_threshold must be >= 0")
            if exit_val >= entry_val:
                raise ValueError("Invalid config: exit_threshold must be < entry_threshold")

        if hold_days is not None:
            try:
                hold_val = int(hold_days)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Invalid config: strategy_params.hold_days must be an integer"
                ) from exc
            if hold_val <= 0:
                raise ValueError("Invalid config: hold_days must be > 0")

        rebalance_frequency = params.get("rebalance_frequency", "DAILY")
        freq = str(rebalance_frequency).upper()
        if freq not in {"DAILY", "WEEKLY"}:
            raise ValueError(
                "Invalid config: rebalance_frequency must be DAILY or WEEKLY"
            )
