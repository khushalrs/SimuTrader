"""Minimal buy-and-hold strategy using the reusable engine core."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from app.backtest.engine import run_engine
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
]:
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

    if has_amount:
        allocation_mode = "AMOUNT"
    elif has_weight:
        allocation_mode = "WEIGHT"
    else:
        allocation_mode = "EQUAL_WEIGHT"

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
    )


def run_buy_and_hold(db: Session, run: BacktestRun, config_snapshot: Dict[str, Any]) -> int:
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
    ) = _extract_config(config_snapshot)
    amount_alloc: dict[str, float] = {inst["symbol"]: inst["amount"] for inst in instruments}

    def target_allocations(ctx):
        allocations: dict[str, float] = {}
        for symbol, amount in amount_alloc.items():
            if ctx.state.positions[symbol].qty == 0:
                allocations[symbol] = amount
        return allocations or None

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
