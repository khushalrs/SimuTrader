"""Minimal buy-and-hold backtest engine (single symbol)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, Tuple

from sqlalchemy.orm import Session

from app.data.duckdb import get_duckdb_conn
from app.models.backtests import BacktestRun, RunDailyEquity
from app.services import calendar_policy


def _parse_date(value: Any, field_name: str) -> date:
    if value is None:
        raise ValueError(f"Missing {field_name} in config_snapshot")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _extract_config(config: Dict[str, Any]) -> Tuple[str, str, Dict[str, str] | None, date, date, float]:
    symbol = config.get("symbol")
    asset_class = config.get("asset_class")

    universe = config.get("universe") or {}
    instruments = universe.get("instruments") or []
    if not symbol and instruments:
        symbol = instruments[0].get("symbol")
        asset_class = asset_class or instruments[0].get("asset_class")

    if not symbol:
        raise ValueError("config_snapshot missing symbol (expected top-level or universe.instruments)")
    if not asset_class:
        raise ValueError("config_snapshot missing asset_class (expected top-level or instrument.asset_class)")

    calendars_map = universe.get("calendars")
    backtest_cfg = config.get("backtest") or {}
    start_date = _parse_date(backtest_cfg.get("start_date") or config.get("start_date"), "start_date")
    end_date = _parse_date(backtest_cfg.get("end_date") or config.get("end_date"), "end_date")
    initial_cash = float(backtest_cfg.get("initial_cash") or config.get("initial_cash") or 10000.0)

    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    return symbol, asset_class, calendars_map, start_date, end_date, initial_cash


def _ensure_calendar_views(con) -> None:
    try:
        con.execute("select 1 from global_calendar limit 1")
        con.execute("select 1 from global_trading_days limit 1")
    except Exception as exc:
        raise RuntimeError(
            "DuckDB calendar views missing. Run scripts/create_calendar_views.py first."
        ) from exc


def _fetch_calendar_with_prices(
    con, symbol: str, start_date: date, end_date: date
) -> Iterable[tuple]:
    return con.execute(
        """
        SELECT
            g.date,
            g.is_us_trading,
            g.is_in_trading,
            g.is_fx_trading,
            p.close
        FROM global_calendar g
        LEFT JOIN prices p
            ON p.date = g.date
           AND p.symbol = ?
        WHERE g.date BETWEEN ? AND ?
        ORDER BY g.date
        """,
        [symbol, start_date, end_date],
    ).fetchall()


def run_buy_and_hold(db: Session, run: BacktestRun, config_snapshot: Dict[str, Any]) -> int:
    symbol, asset_class, calendars_map, start_date, end_date, initial_cash = _extract_config(
        config_snapshot
    )

    con = get_duckdb_conn()
    try:
        _ensure_calendar_views(con)
        rows = _fetch_calendar_with_prices(con, symbol, start_date, end_date)
    finally:
        con.close()

    if not rows:
        raise ValueError(f"No calendar rows between {start_date} and {end_date}")

    cal_name = calendar_policy.calendar_for_asset_class(asset_class, calendars_map)
    calendar_policy.strict_missing_bar = False

    db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run.run_id).delete(
        synchronize_session=False
    )

    position_qty = 0.0
    cash = initial_cash
    last_price = None
    peak_equity = initial_cash
    records: list[RunDailyEquity] = []

    for dt, is_us, is_in, is_fx, close in rows:
        flags = {"is_us_trading": is_us, "is_in_trading": is_in, "is_fx_trading": is_fx}
        market_open = calendar_policy.is_market_open(flags, cal_name)

        if market_open and close is not None:
            if position_qty == 0.0:
                position_qty = cash / float(close)
                cash -= position_qty * float(close)
            last_price = float(close)

        if last_price is None:
            position_value = 0.0
            equity = cash
        else:
            position_value = position_qty * last_price
            equity = cash + position_value

        if equity > peak_equity:
            peak_equity = equity
        drawdown = (equity / peak_equity - 1.0) if peak_equity else 0.0

        records.append(
            RunDailyEquity(
                run_id=run.run_id,
                date=dt,
                equity_base=equity,
                cash_base=cash,
                gross_exposure_base=abs(position_value),
                net_exposure_base=position_value,
                drawdown=drawdown,
                fees_cum_base=0.0,
                taxes_cum_base=0.0,
                borrow_fees_cum_base=0.0,
                margin_interest_cum_base=0.0,
            )
        )

    db.bulk_save_objects(records)
    return len(records)
