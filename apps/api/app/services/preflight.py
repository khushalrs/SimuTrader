from __future__ import annotations

from datetime import date
from math import ceil
from typing import Any

from app.data.duckdb import get_duckdb_conn
from app.services.config_validation import validate_and_resolve_config
from app.services.capabilities import STRATEGY_CAPABILITIES


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _required_fx_pairs(currencies: set[str], base_currency: str) -> list[str]:
    if not currencies or currencies == {base_currency}:
        return []
    if currencies.issubset({"USD", "INR"}) and base_currency in {"USD", "INR"}:
        return ["USDINR"]
    return [f"{currency}{base_currency}" for currency in sorted(currencies) if currency != base_currency]


def _query_symbol_coverage(
    symbols: list[str], start_date: date, end_date: date
) -> tuple[list[dict[str, Any]], dict[str, str], tuple[Any, Any, int] | None]:
    placeholders = ",".join(["?"] * len(symbols))
    con = get_duckdb_conn()
    try:
        rows = con.execute(
            f"""
            SELECT
                symbol,
                min(currency) AS currency,
                min(asset_class) AS asset_class,
                min(exchange) AS exchange,
                min(date) AS first_date,
                max(date) AS last_date,
                count(*) AS rows
            FROM prices
            WHERE symbol IN ({placeholders})
              AND date BETWEEN ? AND ?
            GROUP BY symbol
            """,
            [*symbols, start_date, end_date],
        ).fetchall()
        coverage_by_symbol = {
            row[0]: {
                "symbol": row[0],
                "currency": row[1],
                "asset_class": row[2],
                "exchange": row[3],
                "first_date": row[4],
                "last_date": row[5],
                "rows": int(row[6] or 0),
            }
            for row in rows
        }
        coverage = []
        for symbol in symbols:
            row = coverage_by_symbol.get(symbol)
            if row is None:
                coverage.append(
                    {
                        "symbol": symbol,
                        "currency": None,
                        "asset_class": None,
                        "exchange": None,
                        "first_date": None,
                        "last_date": None,
                        "rows": 0,
                    }
                )
            else:
                coverage.append(row)

        effective = con.execute(
            f"""
            SELECT min(date), max(date), count(DISTINCT date)
            FROM prices
            WHERE symbol IN ({placeholders})
              AND date BETWEEN ? AND ?
            """,
            [*symbols, start_date, end_date],
        ).fetchone()
        symbol_currencies = {
            item["symbol"]: str(item["currency"]).upper()
            for item in coverage
            if item.get("currency")
        }
        return coverage, symbol_currencies, effective
    finally:
        con.close()


def _has_usd_inr_history(start_date: date, end_date: date) -> bool:
    con = get_duckdb_conn()
    try:
        row = con.execute(
            """
            SELECT count(*)
            FROM prices
            WHERE upper(symbol) = 'USDINR'
              AND date BETWEEN ? AND ?
            """,
            [start_date, end_date],
        ).fetchone()
        return bool(row and int(row[0] or 0) > 0)
    finally:
        con.close()


def _flag(
    code: str,
    severity: str,
    message: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "details": details,
    }


def _configured_weights(config: dict[str, Any]) -> dict[str, float]:
    strategy = str(config.get("strategy") or "BUY_AND_HOLD").upper()
    params = config.get("strategy_params") or {}
    instruments = (config.get("universe") or {}).get("instruments") or []
    candidate: Any = None
    if strategy == "FIXED_WEIGHT_REBALANCE":
        candidate = params.get("target_weights")
    elif strategy == "DCA" and params.get("target_weights"):
        candidate = params.get("target_weights")
    elif instruments and all("weight" in instrument for instrument in instruments):
        candidate = {
            str(instrument.get("symbol") or ""): instrument.get("weight")
            for instrument in instruments
        }
    if not isinstance(candidate, dict):
        return {}
    try:
        return {str(symbol): float(weight) for symbol, weight in candidate.items()}
    except (TypeError, ValueError):
        return {}


def _static_risk_checks(
    config: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    warnings: list[str] = []
    flags: list[dict[str, Any]] = []
    strategy = str(config.get("strategy") or "BUY_AND_HOLD").upper()
    instruments = (config.get("universe") or {}).get("instruments") or []
    params = config.get("strategy_params") or {}
    financing = config.get("financing") or {}
    margin = financing.get("margin") or {}
    shorting = financing.get("shorting") or {}
    risk = config.get("risk") or {}
    backtest = config.get("backtest") or {}

    weights = _configured_weights(config)
    if weights:
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            message = f"Configured weights sum to {weight_sum:.6f}; expected 1.0 ± 0.001."
            errors.append(message)
            flags.append(_flag("WEIGHTS_NOT_NORMALIZED", "error", message, weight_sum=weight_sum))
        negative_symbols = sorted(symbol for symbol, weight in weights.items() if weight < 0.0)
        if negative_symbols and not bool(shorting.get("enabled")):
            message = (
                "Negative weights require financing.shorting.enabled=true "
                f"(symbols: {negative_symbols})."
            )
            errors.append(message)
            flags.append(
                _flag(
                    "SHORTING_DISABLED",
                    "error",
                    message,
                    symbols=negative_symbols,
                )
            )

    leverage = float(
        risk.get("max_gross_leverage", margin.get("max_leverage", 1.0)) or 1.0
    )
    if leverage > 1.0 and not bool(margin.get("enabled")):
        message = "Leverage above 1.0 requires financing.margin.enabled=true."
        errors.append(message)
        flags.append(
            _flag("MARGIN_DISABLED", "error", message, max_gross_leverage=leverage)
        )

    if strategy == "MOMENTUM" and params.get("top_k") is not None:
        try:
            top_k = int(params["top_k"])
        except (TypeError, ValueError):
            top_k = 0
        if top_k > len(instruments):
            message = f"Momentum top_k ({top_k}) exceeds universe size ({len(instruments)})."
            errors.append(message)
            flags.append(
                _flag(
                    "TOP_K_EXCEEDS_UNIVERSE",
                    "error",
                    message,
                    top_k=top_k,
                    universe_size=len(instruments),
                )
            )

    contributions = backtest.get("contributions") or config.get("contributions") or {}
    if strategy == "DCA" and contributions.get("enabled"):
        contribution = float(contributions.get("amount") or 0.0)
        base_currency = str(config.get("base_currency") or "USD").upper()
        cash_buckets = backtest.get("initial_cash_by_currency") or {}
        available_cash = float(
            cash_buckets.get(base_currency, backtest.get("initial_cash") or 0.0)
        )
        if contribution > available_cash:
            message = (
                f"DCA contribution ({contribution:.2f}) exceeds currently available "
                f"{base_currency} cash ({available_cash:.2f}); it is treated as new external capital."
            )
            warnings.append(message)
            flags.append(
                _flag(
                    "DCA_CONTRIBUTION_EXCEEDS_CASH",
                    "warning",
                    message,
                    contribution=contribution,
                    available_cash=available_cash,
                    currency=base_currency,
                )
            )
    return errors, warnings, flags


def _estimate_rebalances(
    strategy: str,
    strategy_params: dict[str, Any],
    trading_days: int | None,
    start_date: date,
    end_date: date,
) -> int | None:
    if trading_days is None:
        return None
    if strategy == "BUY_AND_HOLD":
        return 1 if trading_days else 0
    frequency = str(
        strategy_params.get(
            "buy_frequency" if strategy == "DCA" else "rebalance_frequency",
            "MONTHLY",
        )
        or "MONTHLY"
    ).upper()
    if frequency == "DAILY":
        return trading_days
    if frequency == "WEEKLY":
        return ceil(trading_days / 5)
    month_count = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
    if frequency == "QUARTERLY":
        return ceil(month_count / 3)
    return month_count


def run_preflight(raw_config: dict[str, Any]) -> dict[str, Any]:
    raw_strategy = str(raw_config.get("strategy") or "BUY_AND_HOLD").upper()
    strategy_capability = dict(STRATEGY_CAPABILITIES.get(raw_strategy) or {})
    errors, warnings, risk_flags = _static_risk_checks(raw_config)
    data_coverage: list[dict[str, Any]] = []
    required_pairs: list[str] = []
    effective_start_date: date | None = None
    effective_end_date: date | None = None
    estimated_trading_days: int | None = None
    estimated_symbols = len(
        ((raw_config.get("universe") or {}).get("instruments") or [])
    )
    estimated_rebalance_count: int | None = None

    try:
        config = validate_and_resolve_config(raw_config)
    except ValueError as exc:
        validation_error = str(exc)
        if validation_error not in errors:
            errors.append(validation_error)
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "data_coverage": data_coverage,
            "required_fx_pairs": required_pairs,
            "effective_start_date": None,
            "effective_end_date": None,
            "strategy_capability": strategy_capability,
            "estimated_trading_days": None,
            "estimated_symbols": estimated_symbols,
            "estimated_rebalance_count": None,
            "risk_flags": risk_flags,
        }

    strategy = str(config.get("strategy") or "BUY_AND_HOLD").upper()
    strategy_capability = dict(STRATEGY_CAPABILITIES.get(strategy) or {})
    instruments = (config.get("universe") or {}).get("instruments") or []
    backtest = config.get("backtest") or {}
    start_date = _parse_date(backtest.get("start_date"))
    end_date = _parse_date(backtest.get("end_date"))
    base_currency = str(config.get("base_currency") or "USD").upper()
    symbols = [str(inst.get("symbol") or "").upper() for inst in instruments]
    estimated_symbols = len(symbols)

    try:
        data_coverage, symbol_currencies, effective = _query_symbol_coverage(symbols, start_date, end_date)
    except Exception as exc:
        errors.append(f"Unable to inspect market data coverage: {exc}")
        symbol_currencies = {}
        effective = None

    missing_symbols = [item["symbol"] for item in data_coverage if int(item.get("rows") or 0) == 0]
    if missing_symbols:
        errors.append(f"No market data found for symbols: {missing_symbols}")

    if effective and effective[0] is not None and effective[1] is not None:
        effective_start_date = effective[0]
        effective_end_date = effective[1]
        estimated_trading_days = int(effective[2] or 0)
        if effective_start_date != start_date:
            warnings.append(
                f"Start date will shift from {start_date} to {effective_start_date} based on available market data."
            )
        if effective_end_date != end_date:
            warnings.append(
                f"End date will shift from {end_date} to {effective_end_date} based on available market data."
            )

    estimated_rebalance_count = _estimate_rebalances(
        strategy,
        config.get("strategy_params") or {},
        estimated_trading_days,
        effective_start_date or start_date,
        effective_end_date or end_date,
    )

    if strategy == "MOMENTUM":
        params = config.get("strategy_params") or {}
        required_observations = int(params.get("lookback_days") or 0) + int(
            params.get("skip_days") or 0
        ) + 1
        insufficient = {
            str(item["symbol"]): int(item.get("rows") or 0)
            for item in data_coverage
            if int(item.get("rows") or 0) < required_observations
        }
        if insufficient:
            message = (
                f"Momentum requires at least {required_observations} observations per symbol; "
                f"insufficient coverage: {insufficient}."
            )
            errors.append(message)
            risk_flags.append(
                _flag(
                    "INSUFFICIENT_MOMENTUM_LOOKBACK",
                    "error",
                    message,
                    required_observations=required_observations,
                    available_observations=insufficient,
                )
            )

    currencies = set(symbol_currencies.values())
    required_pairs = _required_fx_pairs(currencies, base_currency)
    if required_pairs == ["USDINR"] and not _has_usd_inr_history(start_date, end_date):
        message = "Missing USDINR FX history for mixed-currency base conversion."
        errors.append(message)
        risk_flags.append(
            _flag(
                "MISSING_FX_DATA",
                "error",
                message,
                required_pair="USDINR",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
        )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "data_coverage": data_coverage,
        "required_fx_pairs": required_pairs,
        "effective_start_date": effective_start_date,
        "effective_end_date": effective_end_date,
        "strategy_capability": strategy_capability,
        "estimated_trading_days": estimated_trading_days,
        "estimated_symbols": estimated_symbols,
        "estimated_rebalance_count": estimated_rebalance_count,
        "risk_flags": risk_flags,
    }
