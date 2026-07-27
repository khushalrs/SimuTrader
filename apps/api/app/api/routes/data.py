from __future__ import annotations

from collections import OrderedDict
from datetime import date
import json
import logging
import os
import re
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from redis.exceptions import RedisError

from app.data.duckdb import get_duckdb_conn
from app.services.preflight import _query_symbol_coverage
from app.services.redis_store import get_cache_redis
from app.settings import get_settings


router = APIRouter(prefix="/data", tags=["data"])
logger = logging.getLogger(__name__)
SYMBOL_RE = re.compile(r"[A-Z0-9.\-]{1,20}")
MAX_SYMBOLS = 200
DATA_CACHE_TTL_SECONDS = 900.0
DATA_QUALITY_CACHE_TTL_SECONDS = 86_400
DATA_CACHE_MAX_KEYS = 256
_data_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_data_cache_lock = threading.Lock()


def _cache_get(key: str) -> Any | None:
    now = time.monotonic()
    with _data_cache_lock:
        cached = _data_cache.get(key)
        if cached is None:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            _data_cache.pop(key, None)
            return None
        _data_cache.move_to_end(key)
        return payload


def _cache_set(key: str, payload: Any) -> Any:
    with _data_cache_lock:
        _data_cache[key] = (time.monotonic() + DATA_CACHE_TTL_SECONDS, payload)
        _data_cache.move_to_end(key)
        while len(_data_cache) > DATA_CACHE_MAX_KEYS:
            _data_cache.popitem(last=False)
    return payload


def _quality_redis_key(cache_key: str) -> str:
    settings = get_settings()
    snapshot_id = os.getenv("DATA_SNAPSHOT_ID", "unknown").strip() or "unknown"
    return f"{settings.redis_cache_prefix}:data:{snapshot_id}:quality:v1:{cache_key}"


def _quality_cache_get(cache_key: str) -> Any | None:
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    redis_key = _quality_redis_key(cache_key)
    try:
        value = get_cache_redis().get(redis_key)
        if not value:
            return None
        payload = json.loads(value)
        if not isinstance(payload, list):
            return None
        return _cache_set(cache_key, payload)
    except (RedisError, ValueError, TypeError):
        logger.debug("Data quality Redis cache read failed for key=%s", redis_key, exc_info=True)
        return None


def _quality_cache_set(cache_key: str, payload: Any) -> Any:
    _cache_set(cache_key, payload)
    redis_key = _quality_redis_key(cache_key)
    try:
        get_cache_redis().setex(
            redis_key,
            DATA_QUALITY_CACHE_TTL_SECONDS,
            json.dumps(payload),
        )
    except (RedisError, TypeError, ValueError):
        logger.debug("Data quality Redis cache write failed for key=%s", redis_key, exc_info=True)
    return payload


def _cache_headers(response: Response, hit: bool) -> None:
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
    response.headers["X-Data-Cache"] = "HIT" if hit else "MISS"


def _scope_cache_key(
    endpoint: str,
    symbols: str | None,
    start: date | None,
    end: date | None,
    *limits: int,
) -> str:
    parsed = _parse_symbols(symbols)
    return "|".join(
        [
            endpoint,
            ",".join(parsed or []),
            start.isoformat() if start else "",
            end.isoformat() if end else "",
            *(str(value) for value in limits),
        ]
    )


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
            f"SELECT min(date), max(date) FROM prices WHERE symbol IN ({placeholders})",
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
def get_data_snapshot(response: Response) -> dict[str, Any]:
    cache_key = "snapshot"
    cached = _cache_get(cache_key)
    if cached is not None:
        _cache_headers(response, True)
        return cached
    con = get_duckdb_conn()
    try:
        tables = {str(item[0]) for item in con.execute("SHOW TABLES").fetchall()}
        row = con.execute(
            """
            SELECT count(*), count(DISTINCT upper(symbol)), min(date), max(date)
            FROM prices
            """
        ).fetchone()
        dimension_table = "assets" if "assets" in tables else "prices"
        symbol_count = (
            con.execute("SELECT count(*) FROM assets").fetchone()[0]
            if dimension_table == "assets"
            else row[1]
        )
        asset_classes = [item[0] for item in con.execute(
            f"SELECT DISTINCT asset_class FROM {dimension_table} WHERE asset_class IS NOT NULL ORDER BY 1"
        ).fetchall()]
        currencies = [item[0] for item in con.execute(
            f"SELECT DISTINCT currency FROM {dimension_table} WHERE currency IS NOT NULL ORDER BY 1"
        ).fetchall()]
        data_sources = [item[0] for item in con.execute(
            f"SELECT DISTINCT data_source FROM {dimension_table} WHERE data_source IS NOT NULL ORDER BY 1"
        ).fetchall()]
    finally:
        con.close()
    payload = {
        "row_count": int(row[0] or 0),
        "symbol_count": int(symbol_count or 0),
        "first_date": row[2],
        "last_date": row[3],
        "asset_classes": asset_classes,
        "currencies": currencies,
        "data_sources": data_sources,
    }
    _cache_headers(response, False)
    return _cache_set(cache_key, payload)


@router.get("/coverage")
def get_data_coverage(
    response: Response,
    symbols: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=200, ge=1, le=MAX_SYMBOLS),
) -> list[dict[str, Any]]:
    cache_key = _scope_cache_key("coverage", symbols, start, end, limit)
    cached = _cache_get(cache_key)
    if cached is not None:
        _cache_headers(response, True)
        return cached
    parsed, resolved_start, resolved_end = _resolve_scope(symbols, start, end, limit)
    coverage, _, _ = _query_symbol_coverage(parsed, resolved_start, resolved_end)
    _cache_headers(response, False)
    return _cache_set(cache_key, coverage)


@router.get("/quality")
def get_data_quality(
    response: Response,
    symbols: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=50, ge=1, le=MAX_SYMBOLS),
) -> list[dict[str, Any]]:
    cache_key = _scope_cache_key("quality", symbols, start, end, limit)
    cached = _quality_cache_get(cache_key)
    if cached is not None:
        _cache_headers(response, True)
        return cached
    parsed, resolved_start, resolved_end = _resolve_scope(symbols, start, end, limit)
    placeholders = ",".join(["?"] * len(parsed))
    con = get_duckdb_conn()
    try:
        rows = con.execute(
            f"""
            SELECT
                symbol,
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
            WHERE symbol IN ({placeholders}) AND date BETWEEN ? AND ?
            GROUP BY symbol
            ORDER BY symbol
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
    _cache_headers(response, False)
    return _quality_cache_set(cache_key, result)


def warm_default_data_quality_cache() -> None:
    """Populate the expensive default quality view before the API accepts traffic."""
    cache_key = _scope_cache_key("quality", None, None, None, 50)
    if _quality_cache_get(cache_key) is None:
        get_data_quality(Response(), symbols=None, start=None, end=None, limit=50)


@router.get("/missing-bars")
def get_data_missing_bars(
    response: Response,
    symbols: str | None = None,
    start: date | None = None,
    end: date | None = None,
    symbol_limit: int = Query(default=10, ge=1, le=MAX_SYMBOLS),
    limit: int = Query(default=500, ge=1, le=10000),
) -> list[dict[str, Any]]:
    cache_key = _scope_cache_key(
        "missing-bars", symbols, start, end, symbol_limit, limit
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        _cache_headers(response, True)
        return cached
    parsed, resolved_start, resolved_end = _resolve_scope(
        symbols, start, end, symbol_limit
    )
    placeholders = ",".join(["?"] * len(parsed))
    con = get_duckdb_conn()
    try:
        rows = con.execute(
            f"""
            WITH selected AS (
                SELECT symbol, min(asset_class) AS asset_class
                FROM prices
                WHERE symbol IN ({placeholders})
                GROUP BY symbol
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
              ON p.symbol = e.symbol AND p.date = e.date
            WHERE p.date IS NULL
            ORDER BY e.date, e.symbol
            LIMIT ?
            """,
            [*parsed, resolved_start, resolved_end, limit],
        ).fetchall()
    finally:
        con.close()
    payload = [
        {"symbol": row[0], "asset_class": row[1], "date": row[2]}
        for row in rows
    ]
    _cache_headers(response, False)
    return _cache_set(cache_key, payload)
