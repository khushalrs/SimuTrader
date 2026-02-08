"""Dollar-cost averaging strategy using the reusable engine core."""

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


def _normalize_weights(raw: Dict[str, Any]) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    total = 0.0
    for symbol, weight in raw.items():
        weight_val = float(weight)
        if weight_val <= 0:
            raise ValueError(f"weight for {symbol} must be > 0")
        weights[symbol] = weight_val
        total += weight_val
    if total <= 0:
        raise ValueError("weights sum must be > 0")
    for symbol in weights:
        weights[symbol] = weights[symbol] / total
    return weights


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
    Dict[str, float],
    str,
    bool,
    float,
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
    instrument_weights: Dict[str, float] = {}
    instrument_amounts: Dict[str, float] = {}
    for idx, inst in enumerate(instruments, start=1):
        symbol = inst.get("symbol")
        asset_class = inst.get("asset_class")
        weight = inst.get("weight")
        amount = inst.get("amount")
        if not symbol:
            raise ValueError(f"instrument #{idx} missing symbol")
        if not asset_class:
            raise ValueError(f"instrument #{idx} missing asset_class")
        if symbol in seen_symbols:
            raise ValueError(f"duplicate symbol '{symbol}' in instruments")
        parsed.append({"symbol": symbol, "asset_class": asset_class})
        seen_symbols.add(symbol)
        if weight is not None:
            instrument_weights[symbol] = float(weight)
        if amount is not None:
            instrument_amounts[symbol] = float(amount)

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
    buy_frequency = str(strategy_params.get("buy_frequency") or "MONTHLY").upper()
    if buy_frequency not in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}:
        raise ValueError(f"Unsupported buy_frequency '{buy_frequency}'.")

    weighting_mode = str(strategy_params.get("weighting") or "EQUAL").upper()
    target_weights = strategy_params.get("target_weights") or {}
    if weighting_mode == "TARGET_WEIGHTS":
        if not target_weights:
            raise ValueError("strategy_params.target_weights is required for TARGET_WEIGHTS")
        weights = _normalize_weights(target_weights)
    elif weighting_mode == "INSTRUMENT_WEIGHTS":
        if instrument_weights:
            weights = _normalize_weights(instrument_weights)
        elif instrument_amounts:
            weights = _normalize_weights(instrument_amounts)
        else:
            raise ValueError(
                "instrument weights or amounts are required for INSTRUMENT_WEIGHTS"
            )
    else:
        if target_weights:
            weights = _normalize_weights(target_weights)
        elif instrument_weights:
            weights = _normalize_weights(instrument_weights)
        elif instrument_amounts:
            weights = _normalize_weights(instrument_amounts)
        else:
            equal_weight = 1.0 / len(parsed)
            weights = {inst["symbol"]: equal_weight for inst in parsed}

    contrib_cfg = backtest_cfg.get("contributions") or config.get("contributions") or {}
    contrib_enabled = bool(contrib_cfg.get("enabled"))
    contrib_amount = float(contrib_cfg.get("amount") or 0.0)
    contrib_frequency = str(contrib_cfg.get("frequency") or "MONTHLY").upper()
    if contrib_enabled:
        if contrib_amount <= 0:
            raise ValueError("contributions.amount must be > 0 when enabled")
        if contrib_frequency not in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}:
            raise ValueError(f"Unsupported contributions.frequency '{contrib_frequency}'.")

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
        weights,
        buy_frequency,
        contrib_enabled,
        contrib_amount,
        contrib_frequency,
    )


def _same_week(a: date, b: date) -> bool:
    return a.isocalendar()[:2] == b.isocalendar()[:2]


def _same_month(a: date, b: date) -> bool:
    return a.year == b.year and a.month == b.month


def _same_quarter(a: date, b: date) -> bool:
    return a.year == b.year and (a.month - 1) // 3 == (b.month - 1) // 3


def _should_run(last: date | None, current: date, frequency: str) -> bool:
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


def run_dca(db: Session, run: BacktestRun, config_snapshot: Dict[str, Any]) -> int:
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
        weights,
        buy_frequency,
        contrib_enabled,
        contrib_amount,
        contrib_frequency,
    ) = _extract_config(config_snapshot)

    last_contribution: date | None = None
    last_buy: date | None = None

    def target_allocations(ctx: DayContext):
        nonlocal last_contribution, last_buy

        if len(ctx.state.cash_by_currency) != 1:
            raise ValueError("DCA currently supports single-currency runs only.")

        currency = next(iter(ctx.state.cash_by_currency.keys()))

        if contrib_enabled and _should_run(last_contribution, ctx.date, contrib_frequency):
            ctx.state.cash_by_currency[currency] += contrib_amount
            last_contribution = ctx.date

        if not _should_run(last_buy, ctx.date, buy_frequency):
            return None

        available_cash = ctx.state.cash_by_currency[currency]
        if available_cash <= 0:
            last_buy = ctx.date
            return None

        allocations: Dict[str, float] = {}
        for symbol, weight in weights.items():
            price = ctx.prices.get(symbol)
            if price is None:
                price = ctx.state.last_price.get(symbol)
            if price is None:
                continue
            current_value = ctx.state.positions[symbol].qty * price
            allocations[symbol] = current_value + (available_cash * weight)

        if allocations:
            last_buy = ctx.date
            return allocations
        return None

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
