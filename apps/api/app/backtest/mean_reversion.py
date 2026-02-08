"""Mean reversion strategy using the reusable engine core."""

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
    float,
    float | None,
    int | None,
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
        raise ValueError("strategy_params.lookback_days is required for MEAN_REVERSION")
    lookback_days = int(strategy_params.get("lookback_days"))
    entry_threshold = float(strategy_params.get("entry_threshold"))
    exit_threshold = strategy_params.get("exit_threshold")
    hold_days = strategy_params.get("hold_days")
    rebalance_frequency = str(strategy_params.get("rebalance_frequency") or "DAILY").upper()

    if lookback_days <= 0:
        raise ValueError("lookback_days must be > 0")
    if entry_threshold <= 0:
        raise ValueError("entry_threshold must be > 0")
    if exit_threshold is None and hold_days is None:
        raise ValueError("exit_threshold or hold_days is required")
    if exit_threshold is not None:
        exit_threshold = float(exit_threshold)
        if exit_threshold < 0:
            raise ValueError("exit_threshold must be >= 0")
        if exit_threshold >= entry_threshold:
            raise ValueError("exit_threshold must be < entry_threshold")
    if hold_days is not None:
        hold_days = int(hold_days)
        if hold_days <= 0:
            raise ValueError("hold_days must be > 0")
    if rebalance_frequency not in {"DAILY", "WEEKLY"}:
        raise ValueError(f"Unsupported rebalance_frequency '{rebalance_frequency}'.")

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
        entry_threshold,
        exit_threshold,
        hold_days,
        rebalance_frequency,
    )


def _same_week(a: date, b: date) -> bool:
    return a.isocalendar()[:2] == b.isocalendar()[:2]


def _should_rebalance(last: date | None, current: date, frequency: str) -> bool:
    if last is None:
        return True
    if frequency == "DAILY":
        return current != last
    if frequency == "WEEKLY":
        return not _same_week(current, last)
    return False


def _compute_mean(prices: list[float]) -> float:
    return sum(prices) / len(prices)


def _compute_std(prices: list[float], mean: float) -> float:
    if len(prices) <= 1:
        return 0.0
    variance = sum((price - mean) ** 2 for price in prices) / (len(prices) - 1)
    return variance**0.5


def run_mean_reversion(db: Session, run: BacktestRun, config_snapshot: Dict[str, Any]) -> int:
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
        entry_threshold,
        exit_threshold,
        hold_days,
        rebalance_frequency,
    ) = _extract_config(config_snapshot)

    symbols = [inst["symbol"] for inst in instruments]
    price_history: Dict[str, list[float]] = {symbol: [] for symbol in symbols}
    last_rebalance: date | None = None
    holding_days: Dict[str, int] = {}

    def target_allocations(ctx: DayContext):
        nonlocal last_rebalance

        if len(ctx.state.cash_by_currency) != 1:
            raise ValueError("MEAN_REVERSION currently supports single-currency runs only.")

        for symbol in symbols:
            price = ctx.prices.get(symbol)
            if price is None:
                continue
            price_history[symbol].append(price)

        if not _should_rebalance(last_rebalance, ctx.date, rebalance_frequency):
            return None

        active: list[str] = []
        for symbol in symbols:
            history = price_history[symbol]
            if len(history) < lookback_days:
                continue
            window = history[-lookback_days:]
            mean = _compute_mean(window)
            std = _compute_std(window, mean)
            if std == 0:
                continue
            z_score = (window[-1] - mean) / std

            if symbol in holding_days:
                holding_days[symbol] += 1
                if hold_days is not None:
                    if holding_days[symbol] >= hold_days:
                        del holding_days[symbol]
                        continue
                    active.append(symbol)
                elif exit_threshold is not None:
                    if z_score <= -exit_threshold:
                        active.append(symbol)
                    else:
                        del holding_days[symbol]
                else:
                    active.append(symbol)
                continue

            if z_score <= -entry_threshold:
                active.append(symbol)
                holding_days[symbol] = 0

        if not active:
            last_rebalance = ctx.date
            return {symbol: 0.0 for symbol in symbols}

        total_value = sum(ctx.state.cash_by_currency.values())
        for symbol, pos in ctx.state.positions.items():
            price = ctx.state.last_price.get(symbol)
            if price is None:
                continue
            total_value += pos.qty * price

        if total_value <= 0:
            last_rebalance = ctx.date
            return None

        weight = 1.0 / len(active)
        allocations: Dict[str, float] = {}
        for symbol in symbols:
            allocations[symbol] = total_value * weight if symbol in active else 0.0

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
