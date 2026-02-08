"""Fixed-weight rebalance strategy using the reusable engine core."""

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
            raise ValueError(f"target weight for {symbol} must be > 0")
        weights[symbol] = weight_val
        total += weight_val
    if total <= 0:
        raise ValueError("target_weights sum must be > 0")
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
    float,
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
    target_weights = strategy_params.get("target_weights")
    if not target_weights:
        instrument_weights = {
            inst.get("symbol"): inst.get("weight")
            for inst in instruments
            if inst.get("weight") is not None
        }
        if instrument_weights:
            target_weights = instrument_weights
    if not target_weights:
        raise ValueError(
            "strategy_params.target_weights is required for FIXED_WEIGHT_REBALANCE"
        )
    target_weights = _normalize_weights(target_weights)

    rebalance_frequency = str(strategy_params.get("rebalance_frequency") or "MONTHLY").upper()
    if rebalance_frequency not in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"}:
        raise ValueError(f"Unsupported rebalance_frequency '{rebalance_frequency}'.")
    drift_threshold = float(strategy_params.get("drift_threshold") or 0.0)
    if drift_threshold < 0 or drift_threshold > 1:
        raise ValueError("drift_threshold must be between 0 and 1")

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
        target_weights,
        rebalance_frequency,
        drift_threshold,
    )


def _same_week(a: date, b: date) -> bool:
    return a.isocalendar()[:2] == b.isocalendar()[:2]


def _same_month(a: date, b: date) -> bool:
    return a.year == b.year and a.month == b.month


def _same_quarter(a: date, b: date) -> bool:
    return a.year == b.year and (a.month - 1) // 3 == (b.month - 1) // 3


def run_fixed_weight_rebalance(
    db: Session, run: BacktestRun, config_snapshot: Dict[str, Any]
) -> int:
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
        target_weights,
        rebalance_frequency,
        drift_threshold,
    ) = _extract_config(config_snapshot)

    instrument_symbols = {inst["symbol"] for inst in instruments}
    weight_symbols = set(target_weights.keys())
    if instrument_symbols != weight_symbols:
        missing = instrument_symbols - weight_symbols
        extra = weight_symbols - instrument_symbols
        if missing:
            raise ValueError(f"target_weights missing symbols: {sorted(missing)}")
        if extra:
            raise ValueError(f"target_weights has unknown symbols: {sorted(extra)}")

    last_rebalance: date | None = None

    def _is_rebalance_day(current: date) -> bool:
        nonlocal last_rebalance
        if last_rebalance is None:
            last_rebalance = current
            return True
        if rebalance_frequency == "DAILY":
            last_rebalance = current
            return True
        if rebalance_frequency == "WEEKLY" and not _same_week(current, last_rebalance):
            last_rebalance = current
            return True
        if rebalance_frequency == "MONTHLY" and not _same_month(current, last_rebalance):
            last_rebalance = current
            return True
        if rebalance_frequency == "QUARTERLY" and not _same_quarter(current, last_rebalance):
            last_rebalance = current
            return True
        return False

    def target_allocations(ctx: DayContext):
        if not _is_rebalance_day(ctx.date):
            return None
        if len(ctx.state.cash_by_currency) > 1:
            raise ValueError(
                "FIXED_WEIGHT_REBALANCE requires a single currency; "
                "provide initial_cash_by_currency and target amounts for multi-currency runs."
            )

        total_value = sum(ctx.state.cash_by_currency.values())
        for symbol, pos in ctx.state.positions.items():
            price = ctx.prices.get(symbol)
            if price is None:
                price = ctx.state.last_price.get(symbol)
            if price is None:
                continue
            total_value += pos.qty * price

        if total_value <= 0:
            return None

        if drift_threshold > 0:
            max_drift = 0.0
            for symbol, weight in target_weights.items():
                price = ctx.prices.get(symbol)
                if price is None:
                    price = ctx.state.last_price.get(symbol)
                if price is None:
                    continue
                current_value = ctx.state.positions[symbol].qty * price
                current_weight = current_value / total_value if total_value else 0.0
                max_drift = max(max_drift, abs(current_weight - weight))
            if max_drift < drift_threshold:
                return None

        return {symbol: total_value * weight for symbol, weight in target_weights.items()}

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
