"""Calendar query helpers for DuckDB views."""

from __future__ import annotations

from datetime import date
from typing import Iterable, List

_CALENDAR_COLS = {
    "US": "is_us_trading",
    "IN": "is_in_trading",
    "FX": "is_fx_trading",
}


def _normalize_calendars(calendars: Iterable[str]) -> List[str]:
    seen = []
    for cal in calendars:
        if cal is None:
            continue
        cal_norm = str(cal).strip().upper()
        if not cal_norm:
            continue
        if cal_norm not in _CALENDAR_COLS:
            raise ValueError(f"Unsupported calendar '{cal_norm}'. Expected one of {sorted(_CALENDAR_COLS)}")
        if cal_norm not in seen:
            seen.append(cal_norm)
    if not seen:
        raise ValueError("At least one calendar is required")
    return seen


def get_global_trading_days(conn, start_date: date, end_date: date) -> List[date]:
    rows = conn.execute(
        """
        SELECT date
        FROM global_trading_days
        WHERE date >= ? AND date <= ?
        ORDER BY date
        """,
        [start_date, end_date],
    ).fetchall()
    return [row[0] for row in rows]


def get_calendar_flags(conn, start_date: date, end_date: date):
    return conn.execute(
        """
        SELECT *
        FROM global_calendar
        WHERE date >= ? AND date <= ?
        ORDER BY date
        """,
        [start_date, end_date],
    ).fetchall()


def get_run_trading_days(conn, start_date: date, end_date: date, calendars: Iterable[str]) -> List[date]:
    cal_list = _normalize_calendars(calendars)
    columns = [f"{_CALENDAR_COLS[c]}" for c in cal_list]
    where_or = " OR ".join(columns)

    rows = conn.execute(
        f"""
        SELECT date
        FROM calendar_pivot
        WHERE date >= ? AND date <= ?
          AND ({where_or})
        ORDER BY date
        """,
        [start_date, end_date],
    ).fetchall()
    return [row[0] for row in rows]
