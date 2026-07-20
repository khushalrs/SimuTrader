from __future__ import annotations

from datetime import date
from typing import Any

from app.data.duckdb import get_duckdb_conn
from app.services.config_validation import validate_and_resolve_config
from app.services.capabilities import strategy_supports_mixed_currency


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
) -> tuple[list[dict[str, Any]], dict[str, str], tuple[Any, Any] | None]:
    placeholders = ",".join(["?"] * len(symbols))
    con = get_duckdb_conn()
    try:
        rows = con.execute(
            f"""
            SELECT
                upper(symbol) AS symbol,
                min(currency) AS currency,
                min(date) AS first_date,
                max(date) AS last_date,
                count(*) AS rows
            FROM prices
            WHERE upper(symbol) IN ({placeholders})
              AND date BETWEEN ? AND ?
            GROUP BY upper(symbol)
            """,
            [*symbols, start_date, end_date],
        ).fetchall()
        coverage_by_symbol = {
            row[0]: {
                "symbol": row[0],
                "currency": row[1],
                "first_date": row[2],
                "last_date": row[3],
                "rows": int(row[4] or 0),
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
                        "first_date": None,
                        "last_date": None,
                        "rows": 0,
                    }
                )
            else:
                coverage.append(row)

        effective = con.execute(
            f"""
            SELECT min(date), max(date)
            FROM prices
            WHERE upper(symbol) IN ({placeholders})
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


def run_preflight(raw_config: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    data_coverage: list[dict[str, Any]] = []
    required_pairs: list[str] = []
    effective_start_date: date | None = None
    effective_end_date: date | None = None

    try:
        config = validate_and_resolve_config(raw_config)
    except ValueError as exc:
        return {
            "ok": False,
            "errors": [str(exc)],
            "warnings": warnings,
            "data_coverage": data_coverage,
            "required_fx_pairs": required_pairs,
            "effective_start_date": None,
            "effective_end_date": None,
        }

    strategy = str(config.get("strategy") or "BUY_AND_HOLD").upper()
    instruments = (config.get("universe") or {}).get("instruments") or []
    backtest = config.get("backtest") or {}
    start_date = _parse_date(backtest.get("start_date"))
    end_date = _parse_date(backtest.get("end_date"))
    base_currency = str(config.get("base_currency") or "USD").upper()
    symbols = [str(inst.get("symbol") or "").upper() for inst in instruments]

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
        if effective_start_date != start_date:
            warnings.append(
                f"Start date will shift from {start_date} to {effective_start_date} based on available market data."
            )
        if effective_end_date != end_date:
            warnings.append(
                f"End date will shift from {end_date} to {effective_end_date} based on available market data."
            )

    currencies = set(symbol_currencies.values())
    required_pairs = _required_fx_pairs(currencies, base_currency)
    if len(currencies) > 1:
        if not strategy_supports_mixed_currency(strategy):
            errors.append(f"{strategy} does not support mixed-currency universes.")
        has_amounts = all("amount" in inst for inst in instruments)
        if strategy == "BUY_AND_HOLD":
            if "initial_cash_by_currency" not in backtest:
                errors.append(
                    "initial_cash_by_currency is required when the universe spans multiple currencies."
                )
            if not has_amounts:
                errors.append(
                    "Mixed-currency BUY_AND_HOLD runs require explicit amount allocations for every instrument."
                )

    if required_pairs == ["USDINR"] and not _has_usd_inr_history(start_date, end_date):
        errors.append(
            "Missing USDINR FX history for mixed-currency base conversion."
        )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "data_coverage": data_coverage,
        "required_fx_pairs": required_pairs,
        "effective_start_date": effective_start_date,
        "effective_end_date": effective_end_date,
    }
