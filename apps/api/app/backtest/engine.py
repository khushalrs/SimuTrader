"""Reusable backtest engine core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from typing import Callable, Dict, Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.data.duckdb import get_duckdb_conn
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunFill,
    RunFinancing,
    RunMetric,
    RunOrder,
    RunPosition,
)
from app.services import calendar_policy


@dataclass
class PositionState:
    qty: float = 0.0
    avg_cost_native: float = 0.0


@dataclass
class PortfolioState:
    cash: float
    positions: Dict[str, PositionState]
    last_price: Dict[str, float | None]


@dataclass
class DayContext:
    date: date
    flags: Dict[str, bool]
    prices: Dict[str, float | None]
    market_open: Dict[str, bool]
    state: PortfolioState


@dataclass
class OrderSpec:
    symbol: str
    side: str
    qty: float
    price: float


TargetAllocator = Callable[[DayContext], Dict[str, float] | None]


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
        FROM global_trading_days d
        JOIN global_calendar g
            ON g.date = d.date
        LEFT JOIN prices p
            ON p.date = d.date
           AND p.symbol IN ({placeholders})
        WHERE d.date BETWEEN ? AND ?
        ORDER BY d.date, p.symbol
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


def _targets_to_orders(
    state: PortfolioState,
    target_allocations: Dict[str, float],
    prices: Dict[str, float | None],
    market_open: Dict[str, bool],
) -> list[OrderSpec]:
    orders: list[OrderSpec] = []
    for symbol, target_value in target_allocations.items():
        if target_value < 0:
            raise ValueError(f"target allocation for {symbol} must be >= 0")
        if symbol not in state.positions:
            raise ValueError(f"Unknown symbol in target allocation: {symbol}")
        if not market_open.get(symbol):
            continue
        price = prices.get(symbol)
        if price is None:
            continue

        current_qty = state.positions[symbol].qty
        target_qty = target_value / price if price else 0.0
        delta = target_qty - current_qty
        if abs(delta) < 1e-9:
            continue
        side = "BUY" if delta > 0 else "SELL"
        orders.append(OrderSpec(symbol=symbol, side=side, qty=abs(delta), price=price))
    return orders


def run_engine(
    db: Session,
    run: BacktestRun,
    instruments: list[dict[str, str | float]],
    calendars_map: Dict[str, str] | None,
    start_date: date,
    end_date: date,
    initial_cash: float,
    target_allocations_fn: TargetAllocator,
    include_financing: bool = True,
) -> int:
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
    db.query(RunMetric).filter(RunMetric.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunOrder).filter(RunOrder.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunFill).filter(RunFill.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunPosition).filter(RunPosition.run_id == run.run_id).delete(
        synchronize_session=False
    )
    db.query(RunFinancing).filter(RunFinancing.run_id == run.run_id).delete(
        synchronize_session=False
    )

    state = PortfolioState(
        cash=initial_cash,
        positions={symbol: PositionState() for symbol in symbols},
        last_price={symbol: None for symbol in symbols},
    )

    equity_rows: list[RunDailyEquity] = []
    order_rows: list[RunOrder] = []
    fill_rows: list[RunFill] = []
    position_rows: list[RunPosition] = []
    financing_rows: list[RunFinancing] = []
    equity_series: list[float] = []
    peak_equity = initial_cash

    def process_day(day: date | None, flags: Dict[str, bool] | None, day_prices: Dict[str, float | None]) -> None:
        nonlocal peak_equity
        if day is None:
            return
        if flags is None:
            flags = {"is_us_trading": False, "is_in_trading": False, "is_fx_trading": False}

        market_open = {
            symbol: calendar_policy.is_market_open(flags, symbol_calendars[symbol])
            for symbol in symbols
        }

        for symbol in symbols:
            price = day_prices.get(symbol)
            if market_open.get(symbol) and price is not None:
                state.last_price[symbol] = price

        ctx = DayContext(
            date=day,
            flags=flags,
            prices=day_prices,
            market_open=market_open,
            state=state,
        )
        target_allocations = target_allocations_fn(ctx)

        if target_allocations:
            orders = _targets_to_orders(state, target_allocations, day_prices, market_open)
            sells = [order for order in orders if order.side == "SELL"]
            buys = [order for order in orders if order.side == "BUY"]
            for order in sells + buys:
                order_id = uuid4()
                order_rows.append(
                    RunOrder(
                        order_id=order_id,
                        run_id=run.run_id,
                        date=day,
                        symbol=order.symbol,
                        side=order.side,
                        qty=order.qty,
                        order_type="MKT",
                        limit_price=None,
                        status="FILLED",
                        meta={},
                    )
                )

                notional = order.qty * order.price
                pos = state.positions[order.symbol]
                if order.side == "BUY":
                    if notional > state.cash + 1e-9:
                        raise ValueError(
                            f"insufficient cash for {order.symbol}: need {notional:.2f}, have {state.cash:.2f}"
                        )
                    new_qty = pos.qty + order.qty
                    if new_qty > 0:
                        pos.avg_cost_native = (
                            (pos.avg_cost_native * pos.qty) + notional
                        ) / new_qty
                    pos.qty = new_qty
                    state.cash -= notional
                else:
                    if order.qty > pos.qty + 1e-9:
                        raise ValueError(
                            f"insufficient shares to sell {order.symbol}: want {order.qty:.6f}, have {pos.qty:.6f}"
                        )
                    pos.qty -= order.qty
                    state.cash += notional
                    if pos.qty == 0:
                        pos.avg_cost_native = 0.0

                fill_rows.append(
                    RunFill(
                        fill_id=uuid4(),
                        order_id=order_id,
                        run_id=run.run_id,
                        date=day,
                        symbol=order.symbol,
                        qty=order.qty,
                        price_native=order.price,
                        commission_native=0.0,
                        slippage_native=0.0,
                        notional_native=notional,
                        meta={},
                    )
                )

        total_position_value = 0.0
        gross_exposure = 0.0
        net_exposure = 0.0
        for symbol, pos in state.positions.items():
            price = state.last_price[symbol]
            if price is None:
                market_value = 0.0
                unrealized = 0.0
            else:
                market_value = pos.qty * price
                unrealized = (price - pos.avg_cost_native) * pos.qty
            total_position_value += market_value
            gross_exposure += abs(market_value)
            net_exposure += market_value
            if pos.qty != 0:
                position_rows.append(
                    RunPosition(
                        run_id=run.run_id,
                        date=day,
                        symbol=symbol,
                        qty=pos.qty,
                        avg_cost_native=pos.avg_cost_native,
                        market_value_base=market_value,
                        unrealized_pnl_base=unrealized,
                    )
                )

        equity = state.cash + total_position_value
        if equity > peak_equity:
            peak_equity = equity
        drawdown = (equity / peak_equity - 1.0) if peak_equity else 0.0

        equity_series.append(equity)
        equity_rows.append(
            RunDailyEquity(
                run_id=run.run_id,
                date=day,
                equity_base=equity,
                cash_base=state.cash,
                gross_exposure_base=gross_exposure,
                net_exposure_base=net_exposure,
                drawdown=drawdown,
                fees_cum_base=0.0,
                taxes_cum_base=0.0,
                borrow_fees_cum_base=0.0,
                margin_interest_cum_base=0.0,
            )
        )

        if include_financing:
            financing_rows.append(
                RunFinancing(
                    run_id=run.run_id,
                    date=day,
                    margin_borrowed_base=0.0,
                    margin_interest_base=0.0,
                    short_notional_base=0.0,
                    borrow_fee_base=0.0,
                )
            )

    current_date: date | None = None
    flags: Dict[str, bool] | None = None
    day_prices: Dict[str, float | None] = {symbol: None for symbol in symbols}

    for dt, is_us, is_in, is_fx, symbol, close in rows:
        if current_date is None:
            current_date = dt
        if dt != current_date:
            process_day(current_date, flags, day_prices)
            current_date = dt
            flags = None
            day_prices = {symbol: None for symbol in symbols}

        flags = {
            "is_us_trading": bool(is_us),
            "is_in_trading": bool(is_in),
            "is_fx_trading": bool(is_fx),
        }
        if symbol is not None:
            day_prices[symbol] = float(close) if close is not None else None

    process_day(current_date, flags, day_prices)

    if equity_rows:
        db.bulk_save_objects(equity_rows)
    if order_rows:
        db.bulk_save_objects(order_rows)
    if fill_rows:
        db.bulk_save_objects(fill_rows)
    if position_rows:
        db.bulk_save_objects(position_rows)
    if financing_rows:
        db.bulk_save_objects(financing_rows)

    metrics = _compute_metrics(equity_series)
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
    return len(equity_rows)
