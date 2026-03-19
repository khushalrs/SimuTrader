from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.runs import get_run_fills, get_run_positions
from app.security import ActorContext, ActorTier
from app.models.backtests import BacktestRun, RunDailyEquity, RunFill, RunOrder, RunPosition


@dataclass
class _FakeQuery:
    first_value: object | None = None
    all_values: list | None = None
    scalar_value: object | None = None
    limit_value: int | None = None

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def first(self):
        return self.first_value

    def scalar(self):
        return self.scalar_value

    def all(self):
        values = list(self.all_values or [])
        if self.limit_value is not None:
            return values[: self.limit_value]
        return values


class _FakeDB:
    def __init__(
        self,
        *,
        run_exists: bool = True,
        latest_position_date: date | None = None,
        positions: list | None = None,
        equity_base: float | None = None,
        fills: list | None = None,
        order_sides: list[tuple] | None = None,
    ):
        self.run_exists = run_exists
        self.latest_position_date = latest_position_date
        self.positions = positions or []
        self.equity_base = equity_base
        self.fills = fills or []
        self.order_sides = order_sides or []

    def query(self, *entities):
        if len(entities) == 1:
            entity = entities[0]
            if entity is BacktestRun.run_id:
                return _FakeQuery(first_value=(uuid4(),) if self.run_exists else None)
            if entity is BacktestRun:
                run_obj = (
                    SimpleNamespace(run_id=uuid4(), actor_key="guest:test")
                    if self.run_exists
                    else None
                )
                return _FakeQuery(first_value=run_obj)
            if entity is RunPosition:
                return _FakeQuery(all_values=self.positions)
            if entity is RunFill:
                return _FakeQuery(all_values=self.fills)
            if entity is RunDailyEquity.equity_base:
                first_value = None if self.equity_base is None else (self.equity_base,)
                return _FakeQuery(first_value=first_value)
            if "max(" in str(entity):
                return _FakeQuery(scalar_value=self.latest_position_date)
        if len(entities) == 2 and entities[0] is RunOrder.order_id and entities[1] is RunOrder.side:
            return _FakeQuery(all_values=self.order_sides)
        raise AssertionError(f"Unexpected query entities: {entities}")


def test_get_run_positions_returns_empty_when_no_positions_exist():
    db = _FakeDB(run_exists=True, latest_position_date=None)
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    result = get_run_positions(run_id=uuid4(), actor=actor, db=db)
    assert result == []


def test_get_run_positions_defaults_to_latest_date_and_computes_weight():
    latest = date(2024, 1, 5)
    db = _FakeDB(
        run_exists=True,
        latest_position_date=latest,
        positions=[
            SimpleNamespace(
                date=latest,
                symbol="AAPL",
                qty=10.0,
                avg_cost_native=100.0,
                market_value_base=500.0,
                unrealized_pnl_base=25.0,
            )
        ],
        equity_base=1000.0,
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    result = get_run_positions(run_id=uuid4(), actor=actor, db=db)
    assert len(result) == 1
    assert result[0].date == latest
    assert result[0].weight == pytest.approx(0.5)


def test_get_run_positions_returns_404_for_missing_run():
    db = _FakeDB(run_exists=False)
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    with pytest.raises(HTTPException) as exc:
        get_run_positions(run_id=uuid4(), actor=actor, db=db)
    assert exc.value.status_code == 404


def test_get_run_fills_returns_404_for_missing_run():
    db = _FakeDB(run_exists=False)
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    with pytest.raises(HTTPException) as exc:
        get_run_fills(run_id=uuid4(), actor=actor, db=db)
    assert exc.value.status_code == 404


def test_get_run_fills_maps_side_from_orders():
    order_id = uuid4()
    db = _FakeDB(
        run_exists=True,
        fills=[
            SimpleNamespace(
                order_id=order_id,
                date=date(2024, 1, 3),
                symbol="MSFT",
                qty=2.0,
                price_native=150.0,
                notional_native=300.0,
                commission_native=1.2,
                slippage_native=0.3,
            )
        ],
        order_sides=[(order_id, "BUY")],
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    result = get_run_fills(run_id=uuid4(), actor=actor, db=db)
    assert len(result) == 1
    assert result[0].side == "BUY"
    assert result[0].price == 150.0
