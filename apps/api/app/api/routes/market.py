from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import logging
from math import sqrt
from statistics import median
import time

from fastapi import APIRouter, HTTPException, Query, status

from app.data.duckdb import get_duckdb_conn
from app.schemas.market import MarketBarOut, MarketCoverageOut, MarketSnapshotOut

router = APIRouter(prefix="/market", tags=["market"])
logger = logging.getLogger("uvicorn.error")

MAX_SYMBOLS = 20
MAX_RANGE_DAYS = 730
DEFAULT_RANGE_DAYS = 180
ALLOWED_FIELDS = {"open", "high", "low", "close", "volume"}
ALLOWED_CALENDARS = {"GLOBAL", "US", "IN", "FX"}
ALLOWED_MISSING = {"RAW", "FORWARD_FILL", "DROP"}
SNAPSHOT_TTL_SECONDS = 60.0
BARS_TTL_SECONDS = 45.0

_snapshot_cache: dict[tuple, tuple[float, list[MarketSnapshotOut]]] = {}
_bars_cache: dict[tuple, tuple[float, list[MarketBarOut]]] = {}


def _parse_symbols(symbols: str) -> list[str]:
    parsed = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    if not parsed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="symbols is required")
    if len(parsed) > MAX_SYMBOLS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"symbols supports at most {MAX_SYMBOLS} values",
        )
    return parsed


def _parse_fields(fields: str | None) -> list[str]:
    parsed = [field.strip().lower() for field in (fields or "close").split(",") if field.strip()]
    if not parsed:
        parsed = ["close"]
    invalid = sorted(set(parsed) - ALLOWED_FIELDS)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported fields: {', '.join(invalid)}",
        )
    return parsed


def _parse_calendar(calendar: str | None) -> str:
    calendar_norm = str(calendar or "GLOBAL").strip().upper()
    if calendar_norm not in ALLOWED_CALENDARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported calendar '{calendar_norm}'",
        )
    return calendar_norm


def _parse_missing_bar(policy: str | None) -> str:
    policy_norm = str(policy or "RAW").strip().upper()
    if policy_norm not in ALLOWED_MISSING:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported missing_bar '{policy_norm}'",
        )
    return policy_norm


def _date_bounds(con, symbols: list[str]) -> tuple[date, date]:
    placeholders = ",".join(["?"] * len(symbols))
    row = con.execute(
        f"""
        SELECT min(date) AS min_date, max(date) AS max_date
        FROM prices
        WHERE upper(symbol) IN ({placeholders})
        """,
        symbols,
    ).fetchone()
    if row is None or row[0] is None or row[1] is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No market data found")
    return row[0], row[1]


def _resolve_dates(
    con,
    symbols: list[str],
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    min_date, max_date = _date_bounds(con, symbols)
    resolved_end = end_date or max_date
    resolved_end = min(resolved_end, max_date)
    resolved_start = start_date or max(min_date, resolved_end - timedelta(days=DEFAULT_RANGE_DAYS))
    if resolved_end < resolved_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be >= start_date",
        )
    if (resolved_end - resolved_start).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"date range must be <= {MAX_RANGE_DAYS} days",
        )
    return resolved_start, resolved_end


def _calendar_dates(con, calendar: str, start_date: date, end_date: date) -> list[date]:
    if calendar == "GLOBAL":
        query = """
            SELECT date
            FROM global_trading_days
            WHERE date BETWEEN ? AND ?
            ORDER BY date
        """
        rows = con.execute(query, [start_date, end_date]).fetchall()
    else:
        field = {
            "US": "is_us_trading",
            "IN": "is_in_trading",
            "FX": "is_fx_trading",
        }[calendar]
        query = f"""
            SELECT date
            FROM global_calendar
            WHERE date BETWEEN ? AND ?
              AND {field}
            ORDER BY date
        """
        rows = con.execute(query, [start_date, end_date]).fetchall()
    return [row[0] for row in rows]


def _raw_price_rows(
    con,
    symbols: list[str],
    start_date: date,
    end_date: date,
    fields: list[str],
) -> list[tuple]:
    placeholders = ",".join(["?"] * len(symbols))
    selected = ", ".join(f"p.{field}" for field in fields)
    return con.execute(
        f"""
        SELECT
            p.date,
            upper(p.symbol) AS symbol,
            p.currency,
            p.exchange,
            {selected}
        FROM prices p
        WHERE upper(p.symbol) IN ({placeholders})
          AND p.date BETWEEN ? AND ?
        ORDER BY p.date ASC, upper(p.symbol) ASC
        """,
        [*symbols, start_date, end_date],
    ).fetchall()


def _bar_rows_to_out(rows: list[dict]) -> list[MarketBarOut]:
    return [MarketBarOut.model_validate(row) for row in rows]


def _cache_get(cache: dict, key: tuple, ttl_seconds: float):
    cached = cache.get(key)
    if cached is None:
        return None
    expires_at, payload = cached
    if time.monotonic() >= expires_at:
        cache.pop(key, None)
        return None
    return payload


def _cache_set(cache: dict, key: tuple, payload: list, ttl_seconds: float) -> None:
    cache[key] = (time.monotonic() + ttl_seconds, payload)


def _downsample_rows(rows: list[MarketBarOut], max_points: int | None) -> list[MarketBarOut]:
    if max_points is None or max_points <= 0:
        return rows

    by_symbol: dict[str, list[MarketBarOut]] = defaultdict(list)
    for row in rows:
        by_symbol[row.symbol].append(row)

    reduced: list[MarketBarOut] = []
    for symbol_rows in by_symbol.values():
        if len(symbol_rows) <= max_points:
            reduced.extend(symbol_rows)
            continue

        sampled_indexes = set()
        if max_points == 1:
            sampled_indexes.add(len(symbol_rows) - 1)
        else:
            span = len(symbol_rows) - 1
            for idx in range(max_points):
                sampled_indexes.add(round(idx * span / (max_points - 1)))
        reduced.extend(symbol_rows[idx] for idx in sorted(sampled_indexes))

    return sorted(reduced, key=lambda row: (row.date, row.symbol))


def _continuous_bars(
    con,
    symbols: list[str],
    start_date: date,
    end_date: date,
    fields: list[str],
    calendar: str,
    missing_bar: str,
) -> list[MarketBarOut]:
    raw_rows = _raw_price_rows(con, symbols, start_date, end_date, fields)
    calendar_dates = _calendar_dates(con, calendar, start_date, end_date)
    by_symbol_date: dict[str, dict[date, dict]] = defaultdict(dict)
    first_observed: dict[str, dict] = {}

    for row in raw_rows:
        row_date, symbol, currency, exchange, *values = row
        payload = {
            "date": row_date.isoformat(),
            "symbol": symbol,
            "currency": currency,
            "exchange": exchange,
        }
        for field, value in zip(fields, values):
            payload[field] = value
        by_symbol_date[symbol][row_date] = payload
        if symbol not in first_observed:
            first_observed[symbol] = payload

    emitted: list[dict] = []
    last_seen: dict[str, dict] = {symbol: None for symbol in symbols}  # type: ignore[assignment]

    for current_date in calendar_dates:
        for symbol in symbols:
            payload = by_symbol_date[symbol].get(current_date)
            if payload is not None:
                last_seen[symbol] = payload
                emitted.append(payload)
                continue
            if missing_bar == "DROP":
                continue
            if missing_bar == "FORWARD_FILL":
                source = last_seen[symbol] or first_observed.get(symbol)
                if source is None:
                    continue
                filled = dict(source)
                filled["date"] = current_date.isoformat()
                emitted.append(filled)
                if last_seen[symbol] is None:
                    last_seen[symbol] = filled
    return _bar_rows_to_out(emitted)


def _return_for_window(series: list[tuple[date, float]], window_days: int) -> float | None:
    if not series:
        return None
    last_date, last_close = series[-1]
    anchor_date = last_date - timedelta(days=window_days)
    anchor_close = None
    for current_date, close in reversed(series):
        if current_date <= anchor_date:
            anchor_close = close
            break
    if anchor_close is None or anchor_close == 0:
        return None
    return last_close / anchor_close - 1.0


def _rolling_vols(series: list[tuple[date, float]], window: int = 20) -> list[float]:
    closes = [close for _, close in series]
    returns: list[float] = []
    for prev, curr in zip(closes[:-1], closes[1:]):
        if prev != 0:
            returns.append(curr / prev - 1.0)
    vols: list[float] = []
    for idx in range(window - 1, len(returns)):
        sample = returns[idx - window + 1 : idx + 1]
        mean = sum(sample) / len(sample)
        variance = sum((value - mean) ** 2 for value in sample) / len(sample)
        vols.append(sqrt(variance) * sqrt(252.0))
    return vols


@router.get("/bars", response_model=list[MarketBarOut])
def get_market_bars(
    symbols: str = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    fields: str | None = Query(default=None),
    calendar: str | None = Query(default=None),
    missing_bar: str | None = Query(default=None),
    max_points: int | None = Query(default=None, ge=2, le=5000),
) -> list[MarketBarOut]:
    route_started = time.perf_counter()
    parsed_symbols = _parse_symbols(symbols)
    parsed_fields = _parse_fields(fields)
    parsed_calendar = _parse_calendar(calendar)
    parsed_missing = _parse_missing_bar(missing_bar)
    request_cache_key = (
        tuple(sorted(parsed_symbols)),
        start_date.isoformat() if start_date is not None else None,
        end_date.isoformat() if end_date is not None else None,
        tuple(parsed_fields),
        parsed_calendar,
        parsed_missing,
    )
    cached = _cache_get(_bars_cache, request_cache_key, BARS_TTL_SECONDS)
    if cached is not None:
        response = _downsample_rows(cached, max_points)
        logger.info(
            "market.bars cache_hit=true symbols=%s rows=%s total_ms=%.2f",
            ",".join(parsed_symbols),
            len(response),
            (time.perf_counter() - route_started) * 1000.0,
        )
        return response

    con = get_duckdb_conn()
    try:
        query_started = time.perf_counter()
        resolved_start, resolved_end = _resolve_dates(con, parsed_symbols, start_date, end_date)
        resolved_cache_key = (
            tuple(sorted(parsed_symbols)),
            resolved_start.isoformat(),
            resolved_end.isoformat(),
            tuple(parsed_fields),
            parsed_calendar,
            parsed_missing,
        )
        cached = _cache_get(_bars_cache, resolved_cache_key, BARS_TTL_SECONDS)
        if cached is not None:
            response = _downsample_rows(cached, max_points)
            logger.info(
                "market.bars cache_hit=true symbols=%s rows=%s total_ms=%.2f",
                ",".join(parsed_symbols),
                len(response),
                (time.perf_counter() - route_started) * 1000.0,
            )
            return response

        if parsed_missing == "RAW":
            rows = _raw_price_rows(con, parsed_symbols, resolved_start, resolved_end, parsed_fields)
            query_ms = (time.perf_counter() - query_started) * 1000.0
            model_started = time.perf_counter()
            payload = []
            for row in rows:
                row_date, symbol, currency, exchange, *values = row
                item = {
                    "date": row_date.isoformat(),
                    "symbol": symbol,
                    "currency": currency,
                    "exchange": exchange,
                }
                for field, value in zip(parsed_fields, values):
                    item[field] = value
                payload.append(item)
            out = _bar_rows_to_out(payload)
            model_ms = (time.perf_counter() - model_started) * 1000.0
            processing_ms = 0.0
        else:
            query_ms = (time.perf_counter() - query_started) * 1000.0
            processing_started = time.perf_counter()
            out = _continuous_bars(
                con,
                parsed_symbols,
                resolved_start,
                resolved_end,
                parsed_fields,
                parsed_calendar,
                parsed_missing,
            )
            processing_ms = (time.perf_counter() - processing_started) * 1000.0
            model_ms = 0.0
        _cache_set(_bars_cache, request_cache_key, out, BARS_TTL_SECONDS)
        _cache_set(_bars_cache, resolved_cache_key, out, BARS_TTL_SECONDS)
        response = _downsample_rows(out, max_points)
        logger.info(
            "market.bars cache_hit=false symbols=%s rows=%s duckdb_ms=%.2f processing_ms=%.2f model_ms=%.2f total_ms=%.2f",
            ",".join(parsed_symbols),
            len(response),
            query_ms,
            processing_ms,
            model_ms,
            (time.perf_counter() - route_started) * 1000.0,
        )
        return response
    finally:
        con.close()


@router.get("/coverage", response_model=list[MarketCoverageOut])
def get_market_coverage(
    symbols: str = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    calendar: str | None = Query(default=None),
) -> list[MarketCoverageOut]:
    parsed_symbols = _parse_symbols(symbols)
    parsed_calendar = _parse_calendar(calendar)

    con = get_duckdb_conn()
    try:
        resolved_start, resolved_end = _resolve_dates(con, parsed_symbols, start_date, end_date)
        placeholders = ",".join(["?"] * len(parsed_symbols))
        rows = con.execute(
            f"""
            SELECT
                upper(symbol) AS symbol,
                min(date) AS first_date,
                max(date) AS last_date,
                count(*) AS rows
            FROM prices
            WHERE upper(symbol) IN ({placeholders})
              AND date BETWEEN ? AND ?
            GROUP BY upper(symbol)
            ORDER BY upper(symbol)
            """,
            [*parsed_symbols, resolved_start, resolved_end],
        ).fetchall()
        row_map = {row[0]: row for row in rows}
        calendar_days = _calendar_dates(con, parsed_calendar, resolved_start, resolved_end)
        total_days = len(calendar_days)
        payload = []
        for symbol in parsed_symbols:
            row = row_map.get(symbol)
            if row is None:
                continue
            count = int(row[3])
            payload.append(
                MarketCoverageOut(
                    symbol=row[0],
                    first_date=row[1].isoformat(),
                    last_date=row[2].isoformat(),
                    rows=count,
                    missing_ratio=((total_days - count) / total_days) if total_days else None,
                )
            )
        return payload
    finally:
        con.close()


@router.get("/snapshot", response_model=list[MarketSnapshotOut])
def get_market_snapshot(
    symbols: str = Query(...),
    end_date: date | None = Query(default=None),
) -> list[MarketSnapshotOut]:
    route_started = time.perf_counter()
    parsed_symbols = _parse_symbols(symbols)
    request_cache_key = (
        tuple(sorted(parsed_symbols)),
        end_date.isoformat() if end_date is not None else None,
    )
    cached = _cache_get(_snapshot_cache, request_cache_key, SNAPSHOT_TTL_SECONDS)
    if cached is not None:
        logger.info(
            "market.snapshot cache_hit=true symbols=%s rows=%s total_ms=%.2f",
            ",".join(parsed_symbols),
            len(cached),
            (time.perf_counter() - route_started) * 1000.0,
        )
        return cached

    con = get_duckdb_conn()
    try:
        query_started = time.perf_counter()
        _, max_date = _date_bounds(con, parsed_symbols)
        resolved_end = min(end_date or max_date, max_date)
        resolved_cache_key = (tuple(sorted(parsed_symbols)), resolved_end.isoformat())
        cached = _cache_get(_snapshot_cache, resolved_cache_key, SNAPSHOT_TTL_SECONDS)
        if cached is not None:
            logger.info(
                "market.snapshot cache_hit=true symbols=%s rows=%s total_ms=%.2f",
                ",".join(parsed_symbols),
                len(cached),
                (time.perf_counter() - route_started) * 1000.0,
            )
            return cached
        resolved_start = resolved_end - timedelta(days=420)
        rows = _raw_price_rows(con, parsed_symbols, resolved_start, resolved_end, ["close"])
        query_ms = (time.perf_counter() - query_started) * 1000.0
    finally:
        con.close()

    processing_started = time.perf_counter()
    by_symbol: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for row_date, symbol, _currency, _exchange, close in rows:
        if close is None:
            continue
        by_symbol[symbol].append((row_date, float(close)))

    payload = []
    for symbol in parsed_symbols:
        series = by_symbol.get(symbol, [])
        if not series:
            continue
        vols = _rolling_vols(series, window=20)
        payload.append(
            MarketSnapshotOut(
                symbol=symbol,
                last_date=series[-1][0].isoformat(),
                last_close=series[-1][1],
                return_1w=_return_for_window(series, 7),
                return_1m=_return_for_window(series, 30),
                return_3m=_return_for_window(series, 90),
                return_1y=_return_for_window(series, 365),
                recent_vol_20d=vols[-1] if vols else None,
                median_vol_1y=median(vols[-252:]) if vols else None,
                meta={"observations": len(series)},
            )
        )
    processing_ms = (time.perf_counter() - processing_started) * 1000.0
    _cache_set(_snapshot_cache, request_cache_key, payload, SNAPSHOT_TTL_SECONDS)
    _cache_set(_snapshot_cache, resolved_cache_key, payload, SNAPSHOT_TTL_SECONDS)
    logger.info(
        "market.snapshot cache_hit=false symbols=%s rows=%s duckdb_ms=%.2f processing_ms=%.2f total_ms=%.2f",
        ",".join(parsed_symbols),
        len(payload),
        query_ms,
        processing_ms,
        (time.perf_counter() - route_started) * 1000.0,
    )
    return payload
