from __future__ import annotations

from difflib import get_close_matches
from typing import Any, Iterable

from app.services.capabilities import STRATEGY_CAPABILITIES
from app.services.config_validation import CONFIG_SCHEMA


CANONICAL_PATCH_PATHS: dict[str, str] = {
    "execution.commission.model": "commission.model",
    "execution.commission.bps": "commission.bps",
    "execution.commission.min_fee": "commission.min_fee_native",
    "execution.slippage.model": "slippage.model",
    "execution.slippage.bps": "slippage.bps",
    "execution.fill_price": "fill_price_policy",
}

_ALIASES_BY_CANONICAL: dict[str, list[str]] = {}
for _alias, _canonical in CANONICAL_PATCH_PATHS.items():
    _ALIASES_BY_CANONICAL.setdefault(_canonical, []).append(_alias)

_DESCRIPTIONS: dict[str, str] = {
    "version": "Backtest configuration contract version.",
    "strategy": "Strategy implementation used by the run.",
    "base_currency": "Currency used to report portfolio equity and metrics.",
    "benchmark": "Optional benchmark symbol used for relative-return analytics.",
    "commission.model": "Commission calculation model.",
    "commission.bps": "Commission charged on traded notional.",
    "commission.min_fee_native": "Minimum commission per fill in the instrument currency.",
    "slippage.model": "Execution slippage calculation model.",
    "slippage.bps": "Adverse execution-price adjustment applied to each fill.",
    "fill_price_policy": "Bar price used as the reference execution price.",
    "execution.cash_buffer_pct": "Fraction of equity reserved as cash when allocating.",
    "financing.margin.enabled": "Allow cash borrowing when orders exceed available cash.",
    "financing.margin.max_leverage": "Maximum portfolio leverage permitted by margin.",
    "financing.margin.daily_interest_bps": "Daily interest charged on negative cash.",
    "financing.shorting.enabled": "Allow negative target positions.",
    "financing.shorting.borrow_fee_daily_bps": "Daily borrow fee charged on short market value.",
    "risk.max_gross_leverage": "Maximum sum of absolute portfolio weights.",
    "risk.max_net_leverage": "Maximum absolute signed portfolio exposure.",
    "risk.max_weight": "Maximum absolute weight permitted for one instrument.",
    "risk.risk_free_rate_annual": "Annual risk-free rate used by Sharpe and alpha calculations.",
    "backtest.start_date": "First requested calendar date of the simulation.",
    "backtest.end_date": "Last requested calendar date of the simulation.",
    "backtest.evaluation_start_date": "First date included in metrics after any warm-up period.",
    "backtest.initial_cash": "Starting portfolio cash in the base currency.",
    "backtest.initial_cash_by_currency.*": "Starting cash balance for a currency code.",
    "backtest.contributions.enabled": "Enable periodic external cash contributions.",
    "backtest.contributions.amount": "Cash added on each contribution date in base currency.",
    "backtest.contributions.frequency": "Cadence for external cash contributions.",
    "data_policy.missing_bar": "Policy applied when an instrument lacks a required price.",
    "data_policy.missing_fx": "Policy applied when a required FX observation is missing.",
    "universe.calendars.US_EQUITY": "Trading calendar used for US equities.",
    "universe.calendars.IN_EQUITY": "Trading calendar used for Indian equities.",
    "universe.calendars.FX": "Trading calendar used for FX series.",
    "tax.regime": "Tax regime applied to realized gains.",
}

_UNITS: dict[str, str] = {
    "commission.bps": "basis_points",
    "commission.min_fee_native": "native_currency",
    "slippage.bps": "basis_points",
    "execution.cash_buffer_pct": "fraction",
    "financing.margin.max_leverage": "multiple",
    "financing.margin.daily_interest_bps": "basis_points_per_day",
    "financing.shorting.borrow_fee_daily_bps": "basis_points_per_day",
    "risk.max_gross_leverage": "multiple",
    "risk.max_net_leverage": "multiple",
    "risk.max_weight": "fraction",
    "risk.risk_free_rate_annual": "fraction_per_year",
    "backtest.initial_cash": "base_currency",
    "backtest.initial_cash_by_currency.*": "native_currency",
    "backtest.contributions.amount": "base_currency",
    "tax.us.short_term_days": "calendar_days",
    "tax.us.short_rate": "fraction",
    "tax.us.long_rate": "fraction",
    "tax.india.short_term_days": "calendar_days",
    "tax.india.short_rate": "fraction",
    "tax.india.long_rate": "fraction",
    "tax.short_term_days": "calendar_days",
    "tax.short_rate": "fraction",
    "tax.long_rate": "fraction",
}

_NON_SWEEPABLE_EXACT = {
    "version",
    "strategy",
    "base_currency",
    "benchmark",
    "backtest.start_date",
    "backtest.end_date",
    "backtest.evaluation_start_date",
}
_NON_SWEEPABLE_PREFIXES = (
    "explain.",
    "universe.",
    "data_policy.",
)


def canonicalize_config_path(path: str) -> str:
    cleaned = str(path or "").strip()
    return CANONICAL_PATCH_PATHS.get(cleaned, cleaned)


def _schema_types(schema: dict[str, Any]) -> list[str]:
    raw = schema.get("type")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw if item != "null"]
    return []


def _humanize(path: str) -> str:
    label = path.replace(".*", " value").split(".")[-1].replace("_", " ")
    return f"Configures {label}."


def _is_sweepable(path: str, schema_type: str) -> bool:
    if schema_type in {"object", "array"}:
        return False
    if path in _NON_SWEEPABLE_EXACT:
        return False
    return not any(path.startswith(prefix) for prefix in _NON_SWEEPABLE_PREFIXES)


def _entry_from_schema(path: str, schema: dict[str, Any]) -> dict[str, Any]:
    types = _schema_types(schema)
    schema_type = types[0] if types else "unknown"
    entry: dict[str, Any] = {
        "path": path,
        "canonical_path": path,
        "aliases": sorted(_ALIASES_BY_CANONICAL.get(path, [])),
        "type": schema_type,
        "description": str(
            schema.get("description") or _DESCRIPTIONS.get(path) or _humanize(path)
        ),
        "unit": _UNITS.get(path),
        "strategy": None,
        "sweepable": _is_sweepable(path, schema_type),
        "range_supported": schema_type in {"integer", "number"},
        "minimum": schema.get("minimum"),
        "maximum": schema.get("maximum"),
        "exclusive_minimum": schema.get("exclusiveMinimum"),
        "enum": schema.get("enum"),
        "default": schema.get("default"),
        "format": schema.get("format"),
    }
    return entry


def _walk_schema(
    schema: dict[str, Any],
    prefix: str = "",
) -> Iterable[dict[str, Any]]:
    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        for branch in one_of:
            if isinstance(branch, dict) and (
                branch.get("type") == "object" or branch.get("properties")
            ):
                yield from _walk_schema(branch, prefix)
        if not any(
            isinstance(branch, dict)
            and (branch.get("type") == "object" or branch.get("properties"))
            for branch in one_of
        ) and prefix:
            yield _entry_from_schema(prefix, schema)
        return

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            if not isinstance(child, dict):
                continue
            path = f"{prefix}.{name}" if prefix else name
            yield from _walk_schema(child, path)
        return

    additional = schema.get("additionalProperties")
    if isinstance(additional, dict) and prefix:
        yield _entry_from_schema(f"{prefix}.*", additional)
        return

    if prefix:
        yield _entry_from_schema(prefix, schema)


def _strategy_entries() -> Iterable[dict[str, Any]]:
    for strategy, capability in STRATEGY_CAPABILITIES.items():
        for name, metadata in (capability.get("param_types") or {}).items():
            path = f"strategy_params.{name}"
            param_type = str(metadata.get("type") or "unknown")
            yield {
                "path": path,
                "canonical_path": path,
                "aliases": [],
                "type": param_type,
                "description": str(metadata.get("description") or _humanize(path)),
                "unit": metadata.get("unit"),
                "strategy": strategy,
                "sweepable": param_type != "object",
                "range_supported": param_type in {"integer", "number"},
                "minimum": metadata.get("min"),
                "maximum": metadata.get("max"),
                "exclusive_minimum": metadata.get("exclusive_min"),
                "enum": metadata.get("enum"),
                "default": (capability.get("defaults") or {}).get(name),
                "format": None,
            }
            if param_type == "object" and metadata.get("value_type"):
                wildcard_path = f"{path}.*"
                value_type = str(metadata["value_type"])
                yield {
                    "path": wildcard_path,
                    "canonical_path": wildcard_path,
                    "aliases": [],
                    "type": value_type,
                    "description": str(
                        metadata.get("description") or _humanize(wildcard_path)
                    ),
                    "unit": metadata.get("unit"),
                    "strategy": strategy,
                    "sweepable": True,
                    "range_supported": value_type in {"integer", "number"},
                    "minimum": metadata.get("value_min"),
                    "maximum": metadata.get("value_max"),
                    "exclusive_minimum": metadata.get("value_exclusive_min"),
                    "enum": None,
                    "default": None,
                    "format": None,
                }


def get_config_paths(
    *,
    strategy: str | None = None,
    sweepable: bool | None = None,
) -> list[dict[str, Any]]:
    normalized_strategy = str(strategy or "").upper() or None
    if normalized_strategy and normalized_strategy not in STRATEGY_CAPABILITIES:
        raise ValueError(f"Unknown strategy '{strategy}'.")

    entries = [
        entry
        for entry in [*_walk_schema(CONFIG_SCHEMA), *_strategy_entries()]
        if entry["path"] not in CANONICAL_PATCH_PATHS
        and (
            entry["strategy"] is None
            or normalized_strategy is None
            or entry["strategy"] == normalized_strategy
        )
        and (sweepable is None or entry["sweepable"] is sweepable)
    ]
    return sorted(
        entries,
        key=lambda item: (item["path"], item["strategy"] or ""),
    )


def _matches_registry_path(requested: str, registered: str) -> bool:
    if requested == registered:
        return True
    if not registered.endswith(".*"):
        return False
    prefix = registered[:-1]
    return requested.startswith(prefix) and len(requested) > len(prefix)


def validate_sweep_path(path: str, *, strategy: str | None) -> str:
    requested = str(path or "").strip()
    if not requested or requested.startswith("_"):
        raise ValueError(f"Invalid research grid path '{path}'.")
    canonical = canonicalize_config_path(requested)
    candidates = get_config_paths(strategy=strategy, sweepable=True)
    if any(_matches_registry_path(canonical, entry["path"]) for entry in candidates):
        return canonical

    valid_paths = sorted({entry["path"] for entry in candidates})
    suggestions = get_close_matches(canonical, valid_paths, n=3, cutoff=0.45)
    hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    strategy_hint = f" for strategy {str(strategy).upper()}" if strategy else ""
    raise ValueError(
        f"Config path '{requested}' is not a valid sweep dimension{strategy_hint}.{hint}"
    )
