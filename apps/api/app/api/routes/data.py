from __future__ import annotations

from datetime import date
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.data.duckdb import get_duckdb_conn
from app.services.preflight import _query_symbol_coverage


router = APIRouter(prefix="/data", tags=["data"])
SYMBOL_RE = re.compile(r"[A-Z0-9.\-]{1,20}")
MAX_SYMBOLS = 200


def _parse_symbols(symbols: str | None) -> list[str] | None:
    if symbols is None:
        return None
    parsed = list(dict.fromkeys(part.strip().upper() for part in symbols.split(",") if part.strip()))
    if not parsed:
        raise HTTPException(status_code=422, detail="symbols must contain at least one symbol")
    if len(parsed) > MAX_SYMBOLS:
        raise HTTPException(status_code=422, detail=f"symbols supports at most {MAX_SYMBOLS} values")
    invalid = [symbol for symbol in parsed if SYMBOL_RE.fullmatch(symbol) is None]
    if invalid:
        raise HTTPException(status_code=400, detail=f"invalid symbols: {invalid}")
    return parsed


def _available_symbols(limit: int) -> list[str]:
    con = get_duckdb_conn()
    try:
        return [
            str(row[0]).upper()
            for row in con.execute(
                "SELECT DISTINCT upper(symbol) FROM prices ORDER BY 1 LIMIT ?", [limit]
            ).fetchall()
        ]
    finally:
        con.close()


def _date_bounds(symbols: list[str]) -> tuple[date, date]:
    placeholders = ",".join(["?"] * len(symbols))
    con = get_duckdb_conn()
    try:
        row = con.execute(
            f"SELECT min(date), max(date) FROM prices WHERE upper(symbol) IN ({placeholders})",
            symbols,
        ).fetchone()
        if not row or row[0] is None or row[1] is None:
            row = con.execute("SELECT min(date), max(date) FROM prices").fetchone()
    finally:
        con.close()
    if not row or row[0] is None or row[1] is None:
        raise HTTPException(status_code=404, detail="No market data found")
    return row[0], row[1]


def _resolve_scope(
    symbols: str | None,
    start: date | None,
    end: date | None,
    limit: int,
) -> tuple[list[str], date, date]:
    parsed = _parse_symbols(symbols) or _available_symbols(limit)
    if not parsed:
        raise HTTPException(status_code=404, detail="No market data found")
    first, last = _date_bounds(parsed)
    resolved_start = start or first
    resolved_end = end or last
    if resolved_end < resolved_start:
        raise HTTPException(status_code=422, detail="end must be >= start")
    return parsed, resolved_start, resolved_end


@router.get("/snapshot")
def get_data_snapshot() -> dict[str, Any]:
    con = get_duckdb_conn()
    try:
        row = con.execute(
            """
            SELECT count(*), count(DISTINCT upper(symbol)), min(date), max(date)
            FROM prices
            """
        ).fetchone()
        asset_classes = [row[0] for row in con.execute(
            "SELECT DISTINCT asset_class FROM prices WHERE asset_class IS NOT NULL ORDER BY 1"
        ).fetchall()]
        currencies = [row[0] for row in con.execute(
            "SELECT DISTINCT currency FROM prices WHERE currency IS NOT NULL ORDER BY 1"
        ).fetchall()]
        data_sources = [row[0] for row in con.execute(
            "SELECT DISTINCT data_source FROM prices WHERE data_source IS NOT NULL ORDER BY 1"
        ).fetchall()]
    finally:
        con.close()
    return {
        "row_count": int(row[0] or 0),
        "symbol_count": int(row[1] or 0),
        "first_date": row[2],
        "last_date": row[3],
        "asset_classes": asset_classes,
        "currencies": currencies,
        "data_sources": data_sources,
    }


@router.get("/coverage")
def get_data_coverage(
    symbols: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=200, ge=1, le=MAX_SYMBOLS),
) -> list[dict[str, Any]]:
    parsed, resolved_start, resolved_end = _resolve_scope(symbols, start, end, limit)
    coverage, _, _ = _query_symbol_coverage(parsed, resolved_start, resolved_end)
    return coverage


@router.get("/quality")
def get_data_quality(
    symbols: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=200, ge=1, le=MAX_SYMBOLS),
) -> list[dict[str, Any]]:
    parsed, resolved_start, resolved_end = _resolve_scope(symbols, start, end, limit)
    placeholders = ",".join(["?"] * len(parsed))
    con = get_duckdb_conn()
    try:
        rows = con.execute(
            f"""
            SELECT
                upper(symbol) AS symbol,
                count(*) AS rows,
                count(*) - count(DISTINCT date) AS duplicate_dates,
                count(*) FILTER (
                    WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
                ) AS null_ohlc_rows,
                count(*) FILTER (WHERE close <= 0) AS nonpositive_close_rows,
                count(*) FILTER (
                    WHERE high < low OR high < greatest(open, close) OR low > least(open, close)
                ) AS invalid_ohlc_rows,
                count(*) FILTER (WHERE volume IS NULL OR volume < 0) AS invalid_volume_rows
            FROM prices
            WHERE upper(symbol) IN ({placeholders}) AND date BETWEEN ? AND ?
            GROUP BY upper(symbol)
            ORDER BY upper(symbol)
            """,
            [*parsed, resolved_start, resolved_end],
        ).fetchall()
    finally:
        con.close()
    by_symbol = {str(row[0]): row for row in rows}
    result = []
    for symbol in parsed:
        row = by_symbol.get(symbol)
        values = row or (symbol, 0, 0, 0, 0, 0, 0)
        row_count = int(values[1] or 0)
        issue_count = sum(int(value or 0) for value in values[2:])
        result.append(
            {
                "symbol": symbol,
                "rows": row_count,
                "duplicate_dates": int(values[2] or 0),
                "null_ohlc_rows": int(values[3] or 0),
                "nonpositive_close_rows": int(values[4] or 0),
                "invalid_ohlc_rows": int(values[5] or 0),
                "invalid_volume_rows": int(values[6] or 0),
                "quality_score": max(0.0, 1.0 - issue_count / max(row_count, 1)),
            }
        )
    return result


@router.get("/missing-bars")
def get_data_missing_bars(
    symbols: str | None = None,
    start: date | None = None,
    end: date | None = None,
    symbol_limit: int = Query(default=20, ge=1, le=MAX_SYMBOLS),
    limit: int = Query(default=2000, ge=1, le=10000),
) -> list[dict[str, Any]]:
    parsed, resolved_start, resolved_end = _resolve_scope(
        symbols, start, end, symbol_limit
    )
    placeholders = ",".join(["?"] * len(parsed))
    con = get_duckdb_conn()
    try:
        rows = con.execute(
            f"""
            WITH selected AS (
                SELECT upper(symbol) AS symbol, min(asset_class) AS asset_class
                FROM prices
                WHERE upper(symbol) IN ({placeholders})
                GROUP BY upper(symbol)
            ), expected AS (
                SELECT s.symbol, s.asset_class, c.date
                FROM selected s
                CROSS JOIN global_calendar c
                WHERE c.date BETWEEN ? AND ?
                  AND CASE
                    WHEN s.asset_class = 'US_EQUITY' THEN c.is_us_trading
                    WHEN s.asset_class = 'IN_EQUITY' THEN c.is_in_trading
                    WHEN s.asset_class = 'FX' THEN c.is_fx_trading
                    ELSE c.is_global_trading
                  END
            )
            SELECT e.symbol, e.asset_class, e.date
            FROM expected e
            LEFT JOIN prices p
              ON upper(p.symbol) = e.symbol AND p.date = e.date
            WHERE p.date IS NULL
            ORDER BY e.date, e.symbol
            LIMIT ?
            """,
            [*parsed, resolved_start, resolved_end, limit],
        ).fetchall()
    finally:
        con.close()
    return [
        {"symbol": row[0], "asset_class": row[1], "date": row[2]}
        for row in rows
    ]
