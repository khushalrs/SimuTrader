"""Momentum strategy using the reusable engine core."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from app.backtest.engine import DayContext, run_engine
from app.models.backtests import BacktestRun


def _parse_date(value: Any, field_name: str) -> date:
    if value is None:
        raise ValueError(f"Missing {field_name} in config_snapshot")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _extract_config(
    config: Dict[str, Any],
) -> Tuple[
    list[dict[str, Any]],
    Dict[str, str] | None,
    date,
    date,
    float,
    Dict[str, float] | None,
    str,
    Dict[str, Any],
    Dict[str, Any],
    str,
    int,
    int,
    int,
    str,
]:
    universe = config.get("universe") or {}
    instruments = list(universe.get("instruments") or [])

    if not instruments:
        symbol = config.get("symbol")
        asset_class = config.get("asset_class")
        if symbol or asset_class:
            instruments = [
                {
                    "symbol": symbol,
                    "asset_class": asset_class,
                }
            ]

    if not instruments:
        raise ValueError(
            "config_snapshot missing instruments (expected universe.instruments or top-level symbol)"
        )

    parsed: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for idx, inst in enumerate(instruments, start=1):
        symbol = inst.get("symbol")
        asset_class = inst.get("asset_class")
        if not symbol:
            raise ValueError(f"instrument #{idx} missing symbol")
        if not asset_class:
            raise ValueError(f"instrument #{idx} missing asset_class")
        if symbol in seen_symbols:
            raise ValueError(f"duplicate symbol '{symbol}' in instruments")
        parsed.append({"symbol": symbol, "asset_class": asset_class})
        seen_symbols.add(symbol)

    calendars_map = universe.get("calendars")
    backtest_cfg = config.get("backtest") or {}
    start_date = _parse_date(backtest_cfg.get("start_date") or config.get("start_date"), "start_date")
    end_date = _parse_date(backtest_cfg.get("end_date") or config.get("end_date"), "end_date")
    initial_cash = float(backtest_cfg.get("initial_cash") or config.get("initial_cash") or 10000.0)
    initial_cash_by_currency = backtest_cfg.get("initial_cash_by_currency") or config.get(
        "initial_cash_by_currency"
    )
    data_policy = config.get("data_policy") or {}
    missing_bar_policy = str(data_policy.get("missing_bar") or "FAIL").upper()
    commission_cfg = config.get("commission") or {}
    slippage_cfg = config.get("slippage") or {}
    fill_price_policy = str(config.get("fill_price_policy") or "CLOSE").upper()

    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    strategy_params = config.get("strategy_params") or {}
    if "lookback_days" not in strategy_params:
        raise ValueError("strategy_params.lookback_days is required for MOMENTUM")
    lookback_days = int(strategy_params.get("lookback_days"))
    skip_days = int(strategy_params.get("skip_days") or 1)
    top_k = int(strategy_params.get("top_k"))
    rebalance_frequency = str(strategy_params.get("rebalance_frequency") or "MONTHLY").upper()
    weighting = str(strategy_params.get("weighting") or "EQUAL").upper()

    if lookback_days <= 0:
        raise ValueError("lookback_days must be > 0")
    if skip_days < 0:
        raise ValueError("skip_days must be >= 0")
    if top_k <= 0:
        raise ValueError("top_k must be > 0")
    if rebalance_frequency not in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}:
        raise ValueError(f"Unsupported rebalance_frequency '{rebalance_frequency}'.")
    if weighting != "EQUAL":
        raise ValueError("Only EQUAL weighting is supported for MOMENTUM.")

    allocation_mode = "WEIGHT"

    return (
        parsed,
        calendars_map,
        start_date,
        end_date,
        initial_cash,
        initial_cash_by_currency,
        missing_bar_policy,
        commission_cfg,
        slippage_cfg,
        fill_price_policy,
        allocation_mode,
        lookback_days,
        skip_days,
        top_k,
        rebalance_frequency,
    )


def _same_week(a: date, b: date) -> bool:
    return a.isocalendar()[:2] == b.isocalendar()[:2]


def _same_month(a: date, b: date) -> bool:
    return a.year == b.year and a.month == b.month


def _same_quarter(a: date, b: date) -> bool:
    return a.year == b.year and (a.month - 1) // 3 == (b.month - 1) // 3


def _should_rebalance(last: date | None, current: date, frequency: str) -> bool:
    if last is None:
        return True
    if frequency == "DAILY":
        return current != last
    if frequency == "WEEKLY":
        return not _same_week(current, last)
    if frequency == "MONTHLY":
        return not _same_month(current, last)
    if frequency == "QUARTERLY":
        return not _same_quarter(current, last)
    return False


def run_momentum(db: Session, run: BacktestRun, config_snapshot: Dict[str, Any]) -> int:
    (
        instruments,
        calendars_map,
        start_date,
        end_date,
        initial_cash,
        initial_cash_by_currency,
        missing_bar_policy,
        commission_cfg,
        slippage_cfg,
        fill_price_policy,
        allocation_mode,
        lookback_days,
        skip_days,
        top_k,
        rebalance_frequency,
    ) = _extract_config(config_snapshot)

    symbols = [inst["symbol"] for inst in instruments]
    price_history: Dict[str, list[float]] = {symbol: [] for symbol in symbols}
    last_rebalance: date | None = None

    def target_allocations(ctx: DayContext):
        nonlocal last_rebalance

        if len(ctx.state.cash_by_currency) != 1:
            raise ValueError("MOMENTUM currently supports single-currency runs only.")

        for symbol in symbols:
            price = ctx.prices.get(symbol)
            if price is None:
                continue
            price_history[symbol].append(price)

        if not _should_rebalance(last_rebalance, ctx.date, rebalance_frequency):
            return None

        returns: list[tuple[str, float]] = []
        min_len = lookback_days + skip_days + 1
        for symbol, history in price_history.items():
            if len(history) < min_len:
                continue
            end_idx = len(history) - 1 - skip_days
            start_idx = end_idx - lookback_days
            if start_idx < 0:
                continue
            start_price = history[start_idx]
            end_price = history[end_idx]
            if start_price <= 0:
                continue
            returns.append((symbol, end_price / start_price - 1.0))

        if len(returns) < top_k:
            return None

        returns.sort(key=lambda item: item[1], reverse=True)
        winners = {symbol for symbol, _ in returns[:top_k]}

        total_value = sum(ctx.state.cash_by_currency.values())
        for symbol, pos in ctx.state.positions.items():
            price = ctx.state.last_price.get(symbol)
            if price is None:
                continue
            total_value += pos.qty * price

        if total_value <= 0:
            return None

        weight = 1.0 / len(winners)
        allocations: Dict[str, float] = {}
        for symbol in symbols:
            allocations[symbol] = total_value * 0.99 * weight if symbol in winners else 0.0

        last_rebalance = ctx.date
        return allocations

    return run_engine(
        db=db,
        run=run,
        instruments=instruments,
        calendars_map=calendars_map,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        initial_cash_by_currency=initial_cash_by_currency,
        target_allocations_fn=target_allocations,
        include_financing=True,
        commission_cfg=commission_cfg,
        slippage_cfg=slippage_cfg,
        fill_price_policy=fill_price_policy,
        allocation_mode=allocation_mode,
        missing_bar_policy=missing_bar_policy,
    )
