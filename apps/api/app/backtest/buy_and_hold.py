"""Minimal buy-and-hold backtest engine (multi-symbol)."""

from __future__ import annotations

from datetime import date
from math import sqrt
from typing import Any, Dict, Iterable, Tuple

from sqlalchemy.orm import Session

from app.data.duckdb import get_duckdb_conn
from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric
from app.services import calendar_policy


def _parse_date(value: Any, field_name: str) -> date:
    if value is None:
        raise ValueError(f"Missing {field_name} in config_snapshot")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _extract_config(
    config: Dict[str, Any],
) -> Tuple[list[dict[str, Any]], Dict[str, str] | None, date, date, float]:
    universe = config.get("universe") or {}
    instruments = list(universe.get("instruments") or [])

    if not instruments:
        symbol = config.get("symbol")
        asset_class = config.get("asset_class")
        amount = config.get("amount")
        weight = config.get("weight")
        if symbol or asset_class or amount is not None or weight is not None:
            instruments = [
                {
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "amount": amount,
                    "weight": weight,
                }
            ]

    if not instruments:
        raise ValueError(
            "config_snapshot missing instruments (expected universe.instruments or top-level symbol)"
        )

    parsed: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    has_amount = False
    has_weight = False
    for idx, inst in enumerate(instruments, start=1):
        symbol = inst.get("symbol")
        asset_class = inst.get("asset_class")
        amount = inst.get("amount")
        weight = inst.get("weight")

        if not symbol:
            raise ValueError(f"instrument #{idx} missing symbol")
        if not asset_class:
            raise ValueError(f"instrument #{idx} missing asset_class")
        if symbol in seen_symbols:
            raise ValueError(f"duplicate symbol '{symbol}' in instruments")
        if amount is not None and weight is not None:
            raise ValueError(f"instrument '{symbol}' cannot specify both amount and weight")

        if amount is not None:
            amount_val = float(amount)
            if amount_val <= 0:
                raise ValueError(f"instrument '{symbol}' amount must be > 0")
            parsed.append({"symbol": symbol, "asset_class": asset_class, "amount": amount_val})
            has_amount = True
        else:
            if weight is not None:
                weight_val = float(weight)
                if weight_val <= 0:
                    raise ValueError(f"instrument '{symbol}' weight must be > 0")
                parsed.append({"symbol": symbol, "asset_class": asset_class, "weight": weight_val})
                has_weight = True
            else:
                parsed.append({"symbol": symbol, "asset_class": asset_class})
        seen_symbols.add(symbol)

    if has_amount and has_weight:
        raise ValueError("cannot mix amount and weight across instruments")
    if has_amount:
        missing = [inst["symbol"] for inst in parsed if "amount" not in inst]
        if missing:
            raise ValueError(f"amount required for all instruments (missing: {missing})")
    if has_weight:
        missing = [inst["symbol"] for inst in parsed if "weight" not in inst]
        if missing:
            raise ValueError(f"weight required for all instruments (missing: {missing})")

    calendars_map = universe.get("calendars")
    backtest_cfg = config.get("backtest") or {}
    start_date = _parse_date(backtest_cfg.get("start_date") or config.get("start_date"), "start_date")
    end_date = _parse_date(backtest_cfg.get("end_date") or config.get("end_date"), "end_date")
    initial_cash = float(backtest_cfg.get("initial_cash") or config.get("initial_cash") or 10000.0)

    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    if has_amount:
        total_amount = sum(inst["amount"] for inst in parsed)
        if total_amount > initial_cash:
            raise ValueError(
                f"total amount {total_amount:.2f} exceeds initial_cash {initial_cash:.2f}"
            )
    else:
        if has_weight:
            weight_sum = sum(inst["weight"] for inst in parsed)
            if weight_sum <= 0:
                raise ValueError("weight sum must be > 0")
            for inst in parsed:
                inst["weight"] = inst["weight"] / weight_sum
        else:
            equal_weight = 1.0 / len(parsed)
            for inst in parsed:
                inst["weight"] = equal_weight

        for inst in parsed:
            inst["amount"] = inst["weight"] * initial_cash

    return parsed, calendars_map, start_date, end_date, initial_cash


def _ensure_calendar_views(con) -> None:
    try:
        con.execute("select 1 from global_calendar limit 1")
        con.execute("select 1 from global_trading_days limit 1")
    except Exception as exc:
        raise RuntimeError(
            "DuckDB calendar views missing. Run scripts/create_calendar_views.py first."
        ) from exc


def _fetch_calendar_with_prices(
    con, symbols: list[str], start_date: date, end_date: date
) -> Iterable[tuple]:
    if not symbols:
        raise ValueError("At least one symbol is required")
    placeholders = ",".join(["?"] * len(symbols))
    return con.execute(
        f"""
        SELECT
            g.date,
            g.is_us_trading,
            g.is_in_trading,
            g.is_fx_trading,
            p.symbol,
            p.close
        FROM global_calendar g
        LEFT JOIN prices p
            ON p.date = g.date
           AND p.symbol IN ({placeholders})
        WHERE g.date BETWEEN ? AND ?
        ORDER BY g.date, p.symbol
        """,
        [*symbols, start_date, end_date],
    ).fetchall()


def _compute_metrics(equity_series: list[float]) -> dict[str, float | None]:
    if len(equity_series) < 2:
        return {
            "cagr": None,
            "volatility": None,
            "sharpe": None,
            "max_drawdown": None,
            "gross_return": None,
            "net_return": None,
            "fee_drag": 0.0,
            "tax_drag": 0.0,
            "borrow_drag": 0.0,
            "margin_interest_drag": 0.0,
        }

    initial = equity_series[0]
    final = equity_series[-1]

    daily_returns: list[float] = []
    for prev, curr in zip(equity_series[:-1], equity_series[1:]):
        if prev != 0:
            daily_returns.append(curr / prev - 1.0)

    if daily_returns:
        mean_ret = sum(daily_returns) / len(daily_returns)
        if len(daily_returns) > 1:
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        else:
            variance = 0.0
        std_ret = sqrt(variance)
        volatility = std_ret * sqrt(252.0) if std_ret else 0.0
        sharpe = (mean_ret * 252.0) / volatility if volatility else None
        if initial > 0 and final > 0:
            cagr = (final / initial) ** (252.0 / len(daily_returns)) - 1.0
        else:
            cagr = None
    else:
        mean_ret = 0.0
        volatility = None
        sharpe = None
        cagr = None

    peak = equity_series[0]
    max_drawdown = 0.0
    for equity in equity_series:
        if equity > peak:
            peak = equity
        if peak:
            drawdown = equity / peak - 1.0
            if drawdown < max_drawdown:
                max_drawdown = drawdown

    gross_return = final / initial - 1.0 if initial else None

    return {
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "gross_return": gross_return,
        "net_return": gross_return,
        "fee_drag": 0.0,
        "tax_drag": 0.0,
        "borrow_drag": 0.0,
        "margin_interest_drag": 0.0,
    }


def run_buy_and_hold(db: Session, run: BacktestRun, config_snapshot: Dict[str, Any]) -> int:
    instruments, calendars_map, start_date, end_date, initial_cash = _extract_config(
        config_snapshot
    )
    symbols = [inst["symbol"] for inst in instruments]

    con = get_duckdb_conn()
    try:
        _ensure_calendar_views(con)
        rows = _fetch_calendar_with_prices(con, symbols, start_date, end_date)
    finally:
        con.close()

    if not rows:
        raise ValueError(f"No calendar rows between {start_date} and {end_date}")

    symbol_calendars = {
        inst["symbol"]: calendar_policy.calendar_for_asset_class(
            inst["asset_class"], calendars_map
        )
        for inst in instruments
    }
    calendar_policy.strict_missing_bar = False

    db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run.run_id).delete(
        synchronize_session=False
    )

    cash = initial_cash
    position_qty: dict[str, float] = {s: 0.0 for s in symbols}
    last_price: dict[str, float | None] = {s: None for s in symbols}
    has_bought: dict[str, bool] = {s: False for s in symbols}
    amount_alloc: dict[str, float] = {inst["symbol"]: inst["amount"] for inst in instruments}

    peak_equity = initial_cash
    records: list[RunDailyEquity] = []
    equity_series: list[float] = []

    current_date = None
    flags = None

    def finalize_day(day):
        nonlocal peak_equity
        if day is None:
            return

        total_position_value = 0.0
        for sym in symbols:
            price = last_price[sym]
            if price is not None:
                total_position_value += position_qty[sym] * price

        equity = cash + total_position_value
        if equity > peak_equity:
            peak_equity = equity
        drawdown = (equity / peak_equity - 1.0) if peak_equity else 0.0

        equity_series.append(equity)
        records.append(
            RunDailyEquity(
                run_id=run.run_id,
                date=day,
                equity_base=equity,
                cash_base=cash,
                gross_exposure_base=abs(total_position_value),
                net_exposure_base=total_position_value,
                drawdown=drawdown,
                fees_cum_base=0.0,
                taxes_cum_base=0.0,
                borrow_fees_cum_base=0.0,
                margin_interest_cum_base=0.0,
            )
        )

    for dt, is_us, is_in, is_fx, symbol, close in rows:
        if current_date is None:
            current_date = dt
        if dt != current_date:
            finalize_day(current_date)
            current_date = dt

        if symbol is None:
            continue

        flags = {"is_us_trading": is_us, "is_in_trading": is_in, "is_fx_trading": is_fx}
        cal_name = symbol_calendars[symbol]
        market_open = calendar_policy.is_market_open(flags, cal_name)

        if market_open and close is not None:
            price = float(close)
            if not has_bought[symbol]:
                amount = amount_alloc[symbol]
                if amount > cash:
                    raise ValueError(
                        f"insufficient cash for {symbol}: need {amount:.2f}, have {cash:.2f}"
                    )
                position_qty[symbol] = amount / price
                cash -= amount
                has_bought[symbol] = True
            last_price[symbol] = price

    finalize_day(current_date)

    db.bulk_save_objects(records)

    metrics = _compute_metrics(equity_series)
    db.query(RunMetric).filter(RunMetric.run_id == run.run_id).delete(synchronize_session=False)
    db.add(
        RunMetric(
            run_id=run.run_id,
            cagr=metrics["cagr"],
            volatility=metrics["volatility"],
            sharpe=metrics["sharpe"],
            sortino=None,
            max_drawdown=metrics["max_drawdown"],
            turnover=None,
            gross_return=metrics["gross_return"],
            net_return=metrics["net_return"],
            fee_drag=metrics["fee_drag"],
            tax_drag=metrics["tax_drag"],
            borrow_drag=metrics["borrow_drag"],
            margin_interest_drag=metrics["margin_interest_drag"],
            meta={},
        )
    )
    return len(records)
