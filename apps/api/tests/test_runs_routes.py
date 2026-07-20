from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routes.backtests import get_backtest_trades, router as backtests_router
from app.api.routes.runs import explain_run, get_run_costs_summary, get_run_fills, get_run_positions
from app.db import get_db
from app.security import ActorContext, ActorTier
from app.security import get_current_actor
from app.models.backtests import BacktestRun, RunDailyEquity, RunFill, RunMetric, RunOrder, RunPosition, RunTaxEvent


@dataclass
class _FakeQuery:
    first_value: object | None = None
    all_values: list | None = None
    scalar_value: object | None = None
    limit_value: int | None = None
    offset_value: int = 0

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def group_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def offset(self, value: int):
        self.offset_value = value
        return self

    def first(self):
        if self.first_value is None and self.all_values:
            return self.all_values[0]
        return self.first_value

    def scalar(self):
        if self.scalar_value is None and self.all_values is not None:
            return len(self.all_values)
        return self.scalar_value

    def all(self):
        values = list(self.all_values or [])
        if self.offset_value:
            values = values[self.offset_value :]
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
        metrics: object | None = None,
        equity_rows: list | None = None,
        tax_rows: list | None = None,
        run_config: dict | None = None,
        run_status: str = "SUCCEEDED",
    ):
        self.run_exists = run_exists
        self.latest_position_date = latest_position_date
        self.positions = positions or []
        self.equity_base = equity_base
        self.fills = fills or []
        self.order_sides = order_sides or []
        self.metrics = metrics
        self.equity_rows = equity_rows or []
        self.tax_rows = tax_rows or []
        self.run_config = run_config or {"tax": {"regime": "US"}}
        self.run_status = run_status

    def query(self, *entities):
        if len(entities) == 1:
            entity = entities[0]
            if "count(" in str(entity):
                return _FakeQuery(all_values=self.fills)
            if entity is BacktestRun.run_id:
                return _FakeQuery(first_value=(uuid4(),) if self.run_exists else None)
            if entity is BacktestRun:
                run_obj = (
                    SimpleNamespace(
                        run_id=uuid4(),
                        actor_key="guest:test",
                        status=self.run_status,
                        config_snapshot=self.run_config,
                    )
                    if self.run_exists
                    else None
                )
                return _FakeQuery(first_value=run_obj)
            if entity is RunMetric:
                return _FakeQuery(first_value=self.metrics)
            if entity is RunPosition:
                return _FakeQuery(all_values=self.positions)
            if entity is RunFill:
                return _FakeQuery(all_values=self.fills)
            if entity is RunDailyEquity:
                return _FakeQuery(all_values=self.equity_rows)
            if entity is RunTaxEvent:
                return _FakeQuery(all_values=self.tax_rows)
            if entity is RunDailyEquity.equity_base:
                first_value = None if self.equity_base is None else (self.equity_base,)
                return _FakeQuery(first_value=first_value)
            if "max(" in str(entity):
                return _FakeQuery(scalar_value=self.latest_position_date)
        if len(entities) == 2 and entities[0] is RunOrder.order_id and entities[1] is RunOrder.side:
            return _FakeQuery(all_values=self.order_sides)
        if len(entities) == 3 and entities[0] is RunFill.symbol:
            totals_by_symbol: dict[str, tuple[float, float]] = {}
            for fill in self.fills:
                commissions, slippage = totals_by_symbol.get(fill.symbol, (0.0, 0.0))
                totals_by_symbol[fill.symbol] = (
                    commissions + float(getattr(fill, "commission_native", 0.0) or 0.0),
                    slippage + float(getattr(fill, "slippage_native", 0.0) or 0.0),
                )
            return _FakeQuery(
                all_values=[
                    (symbol, commissions, slippage)
                    for symbol, (commissions, slippage) in totals_by_symbol.items()
                ]
            )
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


def test_get_backtest_trades_alias_maps_to_fills():
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
    result = get_backtest_trades(run_id=uuid4(), actor=actor, db=db)
    assert len(result) == 1
    assert result[0].symbol == "MSFT"
    assert result[0].side == "BUY"


def test_get_backtest_trades_rejects_unbounded_pagination():
    app = FastAPI()
    app.include_router(backtests_router)
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")

    def _override_get_db():
        yield _FakeDB(run_exists=True)

    app.dependency_overrides[get_current_actor] = lambda: actor
    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    run_id = uuid4()

    limit_res = client.get(f"/backtests/{run_id}/trades", params={"limit": "100000000"})
    offset_res = client.get(f"/backtests/{run_id}/trades", params={"offset": "-5"})

    assert limit_res.status_code == 422
    assert offset_res.status_code == 422


def test_cost_summary_groups_native_costs_and_uses_persisted_cumulative_costs():
    latest = date(2024, 1, 5)
    db = _FakeDB(
        run_config={
            "universe": {
                "instruments": [
                    {"symbol": "MSFT", "asset_class": "US_EQUITY"},
                    {"symbol": "RELIANCE", "asset_class": "IN_EQUITY"},
                ]
            }
        },
        fills=[
            SimpleNamespace(
                order_id=None,
                date=date(2024, 1, 3),
                symbol="MSFT",
                qty=2.0,
                price_native=150.0,
                notional_native=300.0,
                commission_native=1.2,
                slippage_native=0.3,
            ),
            SimpleNamespace(
                order_id=None,
                date=date(2024, 1, 4),
                symbol="RELIANCE",
                qty=1.0,
                price_native=2500.0,
                notional_native=2500.0,
                commission_native=12.0,
                slippage_native=3.0,
            ),
        ],
        equity_rows=[
            SimpleNamespace(
                date=latest,
                fees_cum_base=9.5,
                taxes_cum_base=4.25,
                borrow_fees_cum_base=1.5,
                margin_interest_cum_base=0.75,
            )
        ],
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")

    result = get_run_costs_summary(run_id=uuid4(), actor=actor, db=db)

    assert result.commissions_native == pytest.approx({"USD": 1.2, "INR": 12.0})
    assert result.slippage_native == pytest.approx({"USD": 0.3, "INR": 3.0})
    assert result.fees_total_base == pytest.approx(9.5)
    assert result.taxes_total_base == pytest.approx(4.25)
    assert result.borrow_fees_base == pytest.approx(1.5)
    assert result.margin_interest_base == pytest.approx(0.75)


def test_cost_summary_returns_zero_contract_for_non_terminal_run():
    db = _FakeDB(run_status="RUNNING")
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")

    result = get_run_costs_summary(run_id=uuid4(), actor=actor, db=db)

    assert result.model_dump() == {
        "commissions_native": {},
        "slippage_native": {},
        "fees_total_base": 0.0,
        "taxes_total_base": 0.0,
        "borrow_fees_base": 0.0,
        "margin_interest_base": 0.0,
    }


def test_explanation_endpoint_returns_stable_keys():
    db = _FakeDB(
        metrics=SimpleNamespace(
            turnover=1.8,
            gross_return=0.42,
            net_return=0.35,
            fee_drag=0.01,
            tax_drag=0.04,
            borrow_drag=0.01,
            margin_interest_drag=0.01,
        ),
        fills=[SimpleNamespace(fill_id=uuid4()), SimpleNamespace(fill_id=uuid4())],
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")

    result = explain_run(run_id=uuid4(), actor=actor, db=db)
    payload = result.model_dump()

    assert set(payload) == {
        "gross_return",
        "net_return",
        "total_drag",
        "drag_breakdown",
        "dominant_drag",
        "trade_count",
        "turnover",
        "tax_regime",
        "summary",
    }
    assert result.total_drag == pytest.approx(-0.07)
    assert result.drag_breakdown["taxes"] == pytest.approx(-0.04)
    assert result.dominant_drag == "taxes"
    assert result.trade_count == 2
    assert result.tax_regime == "US"
