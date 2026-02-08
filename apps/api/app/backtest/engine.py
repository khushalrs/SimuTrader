"""Reusable backtest engine core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from typing import Any, Callable, Dict, Iterable
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
    cash_by_currency: Dict[str, float]
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


@dataclass
class CommissionSpec:
    model: str
    bps: float
    min_fee_native: float


@dataclass
class SlippageSpec:
    model: str
    bps: float


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


def _fetch_symbol_currencies(con, symbols: list[str]) -> Dict[str, str]:
    placeholders = ",".join(["?"] * len(symbols))
    rows = con.execute(
        f"""
        SELECT symbol, min(currency) AS currency
        FROM prices
        WHERE symbol IN ({placeholders})
        GROUP BY symbol
        """,
        symbols,
    ).fetchall()
    mapping = {symbol: currency for symbol, currency in rows}
    missing = [symbol for symbol in symbols if symbol not in mapping]
    if missing:
        raise ValueError(f"Missing currency metadata for symbols: {missing}")
    return mapping


def _normalize_missing_bar_policy(policy: str) -> str:
    policy_norm = str(policy or "").strip().upper()
    if not policy_norm:
        return "FAIL"
    if policy_norm not in {"FAIL", "FORWARD_FILL"}:
        raise ValueError(f"Unsupported missing_bar policy '{policy}'.")
    return policy_norm


def _normalize_fill_price_policy(policy: str) -> str:
    policy_norm = str(policy or "").strip().upper()
    if not policy_norm:
        return "CLOSE"
    if policy_norm not in {"CLOSE"}:
        raise ValueError(f"Unsupported fill_price_policy '{policy}'.")
    return policy_norm


def _parse_commission(config: Dict[str, Any] | None) -> CommissionSpec:
    config = config or {}
    model = str(config.get("model") or "BPS").upper()
    if model != "BPS":
        raise ValueError(f"Unsupported commission model '{model}'.")
    bps = float(config.get("bps") or 0.0)
    min_fee = float(config.get("min_fee_native") or 0.0)
    if bps < 0 or min_fee < 0:
        raise ValueError("commission bps and min_fee_native must be >= 0")
    return CommissionSpec(model=model, bps=bps, min_fee_native=min_fee)


def _parse_slippage(config: Dict[str, Any] | None) -> SlippageSpec:
    config = config or {}
    model = str(config.get("model") or "BPS").upper()
    if model != "BPS":
        raise ValueError(f"Unsupported slippage model '{model}'.")
    bps = float(config.get("bps") or 0.0)
    if bps < 0:
        raise ValueError("slippage bps must be >= 0")
    return SlippageSpec(model=model, bps=bps)


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
    initial_cash_by_currency: Dict[str, float] | None,
    target_allocations_fn: TargetAllocator,
    commission_cfg: Dict[str, Any] | None,
    slippage_cfg: Dict[str, Any] | None,
    fill_price_policy: str,
    allocation_mode: str,
    missing_bar_policy: str = "FAIL",
    include_financing: bool = True,
) -> int:
    symbols = [inst["symbol"] for inst in instruments]
    policy = _normalize_missing_bar_policy(missing_bar_policy)
    _ = _normalize_fill_price_policy(fill_price_policy)
    commission = _parse_commission(commission_cfg)
    slippage = _parse_slippage(slippage_cfg)
    allocation_mode = str(allocation_mode or "").upper()

    con = get_duckdb_conn()
    try:
        _ensure_calendar_views(con)
        symbol_currencies = _fetch_symbol_currencies(con, symbols)
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

    currencies = sorted({str(currency).upper() for currency in symbol_currencies.values()})
    multi_currency = len(currencies) > 1
    if multi_currency and allocation_mode != "AMOUNT":
        raise ValueError(
            "Multi-currency runs require explicit amount allocations per instrument."
        )

    if initial_cash_by_currency:
        cash_by_currency = {
            currency: float(initial_cash_by_currency.get(currency, 0.0))
            for currency in currencies
        }
        missing_cash = [currency for currency in currencies if currency not in initial_cash_by_currency]
        if missing_cash:
            raise ValueError(
                f"initial_cash_by_currency missing values for currencies: {missing_cash}"
            )
    else:
        if multi_currency:
            raise ValueError(
                "initial_cash_by_currency is required when the universe spans multiple currencies."
            )
        currency = currencies[0] if currencies else "USD"
        cash_by_currency = {currency: float(initial_cash)}

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
        cash_by_currency=cash_by_currency,
        positions={symbol: PositionState() for symbol in symbols},
        last_price={symbol: None for symbol in symbols},
    )

    equity_rows: list[RunDailyEquity] = []
    order_rows: list[RunOrder] = []
    fill_rows: list[RunFill] = []
    position_rows: list[RunPosition] = []
    financing_rows: list[RunFinancing] = []
    fees_cum_by_currency: Dict[str, float] = {currency: 0.0 for currency in currencies}
    equity_series_by_currency: Dict[str, list[float]] = {
        currency: [] for currency in currencies
    }
    peak_equity_by_currency: Dict[str, float] = {
        currency: cash_by_currency[currency] for currency in currencies
    }

    def process_day(
        day: date | None,
        flags: Dict[str, bool] | None,
        day_prices: Dict[str, float | None],
    ) -> None:
        if day is None:
            return
        if flags is None:
            flags = {"is_us_trading": False, "is_in_trading": False, "is_fx_trading": False}

        market_open = {
            symbol: calendar_policy.is_market_open(flags, symbol_calendars[symbol])
            for symbol in symbols
        }

        prices: Dict[str, float | None] = {}
        for symbol in symbols:
            is_open = market_open.get(symbol)
            price = day_prices.get(symbol)
            if is_open:
                if price is None:
                    if policy == "FAIL":
                        raise ValueError(
                            f"Missing bar for {symbol} on {day}. "
                            "Set data_policy.missing_bar=FORWARD_FILL to allow forward fill."
                        )
                    if state.last_price[symbol] is None:
                        raise ValueError(
                            f"Missing bar for {symbol} on {day} with no prior value to forward-fill."
                        )
                    price = state.last_price[symbol]
                state.last_price[symbol] = price
                prices[symbol] = price
            else:
                prices[symbol] = None

        ctx = DayContext(
            date=day,
            flags=flags,
            prices=prices,
            market_open=market_open,
            state=state,
        )
        target_allocations = target_allocations_fn(ctx)

        if target_allocations:
            orders = _targets_to_orders(state, target_allocations, prices, market_open)
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

                currency = str(symbol_currencies[order.symbol]).upper()
                price = order.price
                exec_price = price
                slippage_native = 0.0
                if slippage.bps:
                    slip_rate = slippage.bps / 10000.0
                    if order.side == "BUY":
                        exec_price = price * (1.0 + slip_rate)
                    else:
                        exec_price = price * (1.0 - slip_rate)
                    slippage_native = abs(exec_price - price) * order.qty

                notional = order.qty * exec_price
                commission_native = 0.0
                if commission.bps or commission.min_fee_native:
                    commission_native = max(
                        notional * (commission.bps / 10000.0),
                        commission.min_fee_native,
                    )

                pos = state.positions[order.symbol]
                cash_bucket = state.cash_by_currency[currency]
                if order.side == "BUY":
                    total_cost = notional + commission_native
                    if total_cost > cash_bucket + 1e-9:
                        raise ValueError(
                            f"insufficient cash for {order.symbol} in {currency}: "
                            f"need {total_cost:.2f}, have {cash_bucket:.2f}"
                        )
                    new_qty = pos.qty + order.qty
                    if new_qty > 0:
                        pos.avg_cost_native = (
                            (pos.avg_cost_native * pos.qty) + notional
                        ) / new_qty
                    pos.qty = new_qty
                    state.cash_by_currency[currency] = cash_bucket - total_cost
                else:
                    if order.qty > pos.qty + 1e-9:
                        raise ValueError(
                            f"insufficient shares to sell {order.symbol}: want {order.qty:.6f}, "
                            f"have {pos.qty:.6f}"
                        )
                    pos.qty -= order.qty
                    state.cash_by_currency[currency] = cash_bucket + notional - commission_native
                    if pos.qty == 0:
                        pos.avg_cost_native = 0.0

                fees_cum_by_currency[currency] += commission_native + slippage_native

                fill_rows.append(
                    RunFill(
                        fill_id=uuid4(),
                        order_id=order_id,
                        run_id=run.run_id,
                        date=day,
                        symbol=order.symbol,
                        qty=order.qty,
                        price_native=exec_price,
                        commission_native=commission_native,
                        slippage_native=slippage_native,
                        notional_native=notional,
                        meta={},
                    )
                )

        equity_by_currency: Dict[str, float] = {
            currency: state.cash_by_currency[currency] for currency in currencies
        }
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
            currency = str(symbol_currencies[symbol]).upper()
            equity_by_currency[currency] += market_value

            if not multi_currency:
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

        if multi_currency:
            equity = 0.0
            cash_value = 0.0
            drawdown = 0.0
            fees_cum_value = 0.0
        else:
            primary = currencies[0]
            equity = equity_by_currency[primary]
            cash_value = state.cash_by_currency[primary]
            if equity > peak_equity_by_currency[primary]:
                peak_equity_by_currency[primary] = equity
            drawdown = (
                equity / peak_equity_by_currency[primary] - 1.0
                if peak_equity_by_currency[primary]
                else 0.0
            )
            fees_cum_value = fees_cum_by_currency[primary]

        for currency in currencies:
            equity_series_by_currency[currency].append(equity_by_currency[currency])
            if equity_by_currency[currency] > peak_equity_by_currency[currency]:
                peak_equity_by_currency[currency] = equity_by_currency[currency]

        equity_rows.append(
            RunDailyEquity(
                run_id=run.run_id,
                date=day,
                equity_base=equity,
                cash_base=cash_value,
                gross_exposure_base=gross_exposure,
                net_exposure_base=net_exposure,
                drawdown=drawdown,
                fees_cum_base=fees_cum_value,
                taxes_cum_base=0.0,
                borrow_fees_cum_base=0.0,
                margin_interest_cum_base=0.0,
                equity_by_currency=equity_by_currency,
                cash_by_currency=dict(state.cash_by_currency),
                fees_cum_by_currency=dict(fees_cum_by_currency),
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

    symbol_set = set(symbols)

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
        if symbol is not None and symbol in symbol_set:
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

    if multi_currency:
        per_currency = {
            currency: _compute_metrics(series)
            for currency, series in equity_series_by_currency.items()
        }
        metrics = {
            "cagr": None,
            "volatility": None,
            "sharpe": None,
            "max_drawdown": None,
            "gross_return": None,
            "net_return": None,
            "fee_drag": None,
            "tax_drag": None,
            "borrow_drag": None,
            "margin_interest_drag": None,
        }
        metrics_meta = {"per_currency": per_currency, "currencies": currencies}
    else:
        metrics = _compute_metrics(equity_series_by_currency[currencies[0]])
        metrics_meta = {}

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
            meta=metrics_meta,
        )
    )
    return len(equity_rows)
