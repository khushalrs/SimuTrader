"""Dollar-cost averaging strategy using the reusable engine core."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from app.backtest.engine import DayContext, _parse_cash_buffer_pct, run_engine
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
    base_currency = str(config_snapshot.get("base_currency") or "USD").upper()
    # DCA buffers its own incoming cash and opts out of the engine-level buffer, which
    # would otherwise trim already-held positions on every contribution date.
    cash_buffer_pct = _parse_cash_buffer_pct(config_snapshot.get("execution"))

    def target_allocations(ctx: DayContext):
        nonlocal last_contribution, last_buy
        if ctx.is_warmup:
            return None

        contribution_base = 0.0
        if contrib_enabled and _should_run(last_contribution, ctx.date, contrib_frequency):
            ctx.state.cash_by_currency[base_currency] = (
                ctx.state.cash_by_currency.get(base_currency, 0.0) + contrib_amount
            )
            contribution_base = contrib_amount
            last_contribution = ctx.date

        if not _should_run(last_buy, ctx.date, buy_frequency):
            return None
        ctx.recorder.mark_decision_cycle(
            strategy="DCA",
            frequency=buy_frequency,
        )

        available_cash_base = ctx.cash_base_total + contribution_base
        equity_base = ctx.equity_base + contribution_base
        if available_cash_base <= 0 or equity_base <= 0:
            for symbol, weight in weights.items():
                ctx.recorder.signal(
                    symbol,
                    "target_weight",
                    weight,
                    selected=False,
                )
                ctx.recorder.order_decision(
                    symbol=symbol,
                    requested_target_weight=weight,
                    target_weight=weight,
                    target_qty=None,
                    current_qty=ctx.state.positions[symbol].qty,
                    delta_qty=None,
                    intended_side=None,
                    intended_qty=None,
                    executable_qty=0.0,
                    outcome="REJECTED_CONSTRAINT",
                    reason="Available cash and portfolio equity must both be positive.",
                    meta={},
                )
            last_buy = ctx.date
            return None

        allocations: Dict[str, float] = {}
        investable_cash_base = available_cash_base * (1.0 - cash_buffer_pct)
        for symbol, weight in weights.items():
            ctx.recorder.signal(
                symbol,
                "target_weight",
                weight,
                selected=True,
                meta={"contribution_base": contribution_base},
            )
            target_base = ctx.position_value_base.get(symbol, 0.0) + (
                investable_cash_base * weight
            )
            allocations[symbol] = target_base / equity_base

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
        allocation_kind="BASE_WEIGHT",
        apply_cash_buffer=False,
        missing_bar_policy=missing_bar_policy,
    )
