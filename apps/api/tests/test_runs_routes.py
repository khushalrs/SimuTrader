from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient

from app.api.routes import runs as runs_routes
from app.api.routes.backtests import get_backtest_trades
from app.api.routes.backtests import router as backtests_router
from app.api.routes.runs import (
    explain_run,
    get_run_costs_summary,
    get_run_exposure,
    get_run_fills,
    get_run_metrics,
    get_run_order_decisions,
    get_run_positions,
    get_run_signals,
    get_run_tax_event_lots,
    get_run_trade_trace,
    run_monte_carlo,
)
from app.db import get_db
from app.models.assets import Asset
from app.models.backtests import (
    BacktestRun,
    RunConstraintEvent,
    RunDailyEquity,
    RunFill,
    RunMetric,
    RunOrder,
    RunOrderDecision,
    RunPosition,
    RunSignalSnapshot,
    RunTaxEvent,
    RunTaxLotConsumption,
)
from app.schemas.backtests import RunMonteCarloRequest
from app.security import ActorContext, ActorTier, get_current_actor


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
        orders: list | None = None,
        order_sides: list[tuple] | None = None,
        metrics: object | None = None,
        equity_rows: list | None = None,
        tax_rows: list | None = None,
        signal_rows: list | None = None,
        order_decision_rows: list | None = None,
        constraint_rows: list | None = None,
        tax_lot_rows: list | None = None,
        run_config: dict | None = None,
        run_status: str = "SUCCEEDED",
        assets: list | None = None,
    ):
        self.run_exists = run_exists
        self.latest_position_date = latest_position_date
        self.positions = positions or []
        self.equity_base = equity_base
        self.fills = fills or []
        self.orders = orders or []
        self.order_sides = order_sides or []
        self.metrics = metrics
        self.equity_rows = equity_rows or []
        self.tax_rows = tax_rows or []
        self.signal_rows = signal_rows or []
        self.order_decision_rows = order_decision_rows or []
        self.constraint_rows = constraint_rows or []
        self.tax_lot_rows = tax_lot_rows or []
        self.run_config = run_config or {"tax": {"regime": "US"}}
        self.run_status = run_status
        self.assets = assets or []

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
                        seed=42,
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
            if entity is RunOrder:
                return _FakeQuery(all_values=self.orders)
            if entity is RunDailyEquity:
                return _FakeQuery(all_values=self.equity_rows)
            if entity is RunTaxEvent:
                return _FakeQuery(all_values=self.tax_rows)
            if entity is RunSignalSnapshot:
                return _FakeQuery(all_values=self.signal_rows)
            if entity is RunOrderDecision:
                return _FakeQuery(all_values=self.order_decision_rows)
            if entity is RunConstraintEvent:
                return _FakeQuery(all_values=self.constraint_rows)
            if entity is RunTaxLotConsumption:
                return _FakeQuery(all_values=self.tax_lot_rows)
            if entity is Asset:
                return _FakeQuery(all_values=self.assets)
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


def test_signal_and_order_decision_routes_return_captured_records() -> None:
    captured_date = date(2024, 1, 2)
    signal = SimpleNamespace(
        date=captured_date,
        symbol="AAPL",
        signal_name="momentum_return",
        value=0.12,
        rank=1,
        selected=True,
        meta={},
    )
    decision = SimpleNamespace(
        date=captured_date,
        symbol="AAPL",
        requested_target_weight=1.0,
        target_weight=0.99,
        target_qty=10.0,
        current_qty=0.0,
        delta_qty=10.0,
        intended_side="BUY",
        intended_qty=10.0,
        executable_qty=10.0,
        outcome="TRIMMED_CASH_BUFFER",
        reason="Target allocation was reduced by the configured cash buffer.",
        meta={"terminal_status": "FILLED"},
    )
    db = _FakeDB(signal_rows=[signal], order_decision_rows=[decision])
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")

    signals = get_run_signals(
        run_id=uuid4(),
        date_value=captured_date,
        symbol=None,
        signal_name=None,
        limit=100,
        actor=actor,
        db=db,
    )
    decisions = get_run_order_decisions(
        run_id=uuid4(),
        date_value=captured_date,
        symbol=None,
        outcome=None,
        limit=100,
        actor=actor,
        db=db,
    )

    assert signals == [signal]
    assert decisions == [decision]


def test_tax_lots_and_trade_trace_assemble_provenance() -> None:
    captured_date = date(2024, 1, 2)
    decision_id = uuid4()
    order_id = uuid4()
    event_id = uuid4()
    signal = SimpleNamespace(
        date=captured_date,
        symbol="AAPL",
        signal_name="momentum_return",
        value=0.12,
        rank=1,
        selected=True,
        meta={},
    )
    decision = SimpleNamespace(
        decision_id=decision_id,
        order_id=order_id,
        date=captured_date,
        symbol="AAPL",
        requested_target_weight=1.0,
        target_weight=0.5,
        target_qty=5.0,
        current_qty=0.0,
        delta_qty=5.0,
        intended_side="BUY",
        intended_qty=5.0,
        executable_qty=5.0,
        outcome="FILLED",
        reason=None,
        meta={},
    )
    constraint = SimpleNamespace(
        constraint_id=uuid4(),
        decision_id=decision_id,
        date=captured_date,
        symbol="AAPL",
        constraint_name="max_weight",
        bound_value=0.5,
        pre_clamp_value=1.0,
        applied_value=0.5,
        reason="Target exceeded max weight.",
        meta={},
    )
    order = SimpleNamespace(
        order_id=order_id,
        date=captured_date,
        symbol="AAPL",
        side="BUY",
        qty=5.0,
        order_type="MKT",
        limit_price=None,
        status="FILLED",
        meta={},
    )
    fill = SimpleNamespace(
        fill_id=uuid4(),
        order_id=order_id,
        date=captured_date,
        symbol="AAPL",
        qty=5.0,
        price_native=100.0,
        commission_native=1.0,
        slippage_native=0.5,
        notional_native=500.0,
        meta={},
    )
    tax_event = SimpleNamespace(
        tax_event_id=event_id,
        date=captured_date,
        symbol="AAPL",
        quantity=5.0,
        realized_pnl_base=20.0,
        holding_period_days=30,
        bucket="US_ST",
        tax_rate=0.3,
        tax_due_base=6.0,
        meta={},
    )
    lot = SimpleNamespace(
        consumption_id=uuid4(),
        tax_event_id=event_id,
        date=captured_date,
        symbol="AAPL",
        lot_opened_on=date(2023, 12, 1),
        lot_unit_cost_native=96.0,
        qty_consumed=5.0,
        holding_days=30,
        bucket="US_ST",
        realized_pnl_base=20.0,
    )
    db = _FakeDB(
        signal_rows=[signal],
        order_decision_rows=[decision],
        constraint_rows=[constraint],
        orders=[order],
        fills=[fill],
        tax_rows=[tax_event],
        tax_lot_rows=[lot],
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")

    lots = get_run_tax_event_lots(
        run_id=uuid4(),
        event_id=event_id,
        actor=actor,
        db=db,
    )
    trace = get_run_trade_trace(
        run_id=uuid4(),
        date_value=captured_date,
        symbol="aapl",
        actor=actor,
        db=db,
    )

    assert lots == [lot]
    assert trace.symbol == "AAPL"
    assert trace.signals[0].signal_name == "momentum_return"
    assert trace.decisions[0].decision_id == decision_id
    assert trace.constraints[0].decision_id == decision_id
    assert trace.orders[0].order_id == order_id
    assert trace.fills[0].order_id == order_id
    assert trace.tax_events[0].tax_event_id == event_id
    assert trace.tax_events[0].lots[0].lot_opened_on == date(2023, 12, 1)


def test_run_monte_carlo_uses_finished_run_equity_and_cache(
    monkeypatch,
) -> None:
    start = date(2024, 1, 2)
    db = _FakeDB(
        metrics=SimpleNamespace(
            meta={
                "initial_cash_base": 100.0,
                "risk_free_rate_annual": 0.0,
            }
        ),
        equity_rows=[
            SimpleNamespace(
                date=start + timedelta(days=index),
                equity_base=value,
            )
            for index, value in enumerate([101.0, 99.0, 103.0, 104.0])
        ],
    )
    cached_payloads: list[dict] = []
    monkeypatch.setattr(runs_routes, "get_cached_monte_carlo", lambda *_args: None)
    monkeypatch.setattr(
        runs_routes,
        "set_cached_monte_carlo",
        lambda _run_id, _identity, payload: cached_payloads.append(payload),
    )

    response = Response()
    result = run_monte_carlo(
        run_id=uuid4(),
        payload=RunMonteCarloRequest(method="bootstrap", n=100),
        response=response,
        actor=ActorContext(tier=ActorTier.GUEST, actor_key="guest:test"),
        db=db,
    )

    assert response.headers["X-Cache"] == "MISS"
    assert result.horizon == 4
    assert len(result.paths) == 30
    assert cached_payloads[0]["seed"] == result.seed


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


def test_get_run_exposure_groups_long_short_and_unknown_country():
    first = date(2024, 1, 3)
    second = date(2024, 1, 4)
    db = _FakeDB(
        equity_rows=[
            SimpleNamespace(
                date=first,
                equity_base=1000.0,
                equity_by_currency={"USD": 800.0, "INR": 16000.0},
            ),
            SimpleNamespace(
                date=second,
                equity_base=1100.0,
                equity_by_currency={"USD": 1100.0},
            ),
        ],
        positions=[
            SimpleNamespace(
                date=first,
                symbol="AAPL",
                qty=5.0,
                market_value_base=600.0,
            ),
            SimpleNamespace(
                date=first,
                symbol="RELIANCE",
                qty=-2.0,
                market_value_base=-200.0,
            ),
            SimpleNamespace(
                date=first,
                symbol="MYSTERY",
                qty=1.0,
                market_value_base=50.0,
            ),
        ],
        assets=[
            SimpleNamespace(
                symbol="AAPL", asset_class="US_EQUITY", currency="USD"
            ),
            SimpleNamespace(
                symbol="RELIANCE", asset_class="IN_EQUITY", currency="INR"
            ),
        ],
    )
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")

    result = get_run_exposure(
        run_id=uuid4(), actor=actor, db=db, start=None, end=None, limit=2000
    )

    assert len(result) == 2
    assert result[0].long_base == pytest.approx(650.0)
    assert result[0].short_base == pytest.approx(200.0)
    assert result[0].gross_base == pytest.approx(850.0)
    assert result[0].net_base == pytest.approx(450.0)
    assert result[0].leverage == pytest.approx(0.85)
    assert result[0].equity_native_by_currency == {
        "USD": 800.0,
        "INR": 16000.0,
    }
    assert result[0].exposure_base_by_currency["USD"].long_base == pytest.approx(600.0)
    assert result[0].exposure_base_by_currency["INR"].short_base == pytest.approx(200.0)
    assert result[0].exposure_base_by_currency["UNKNOWN"].long_base == pytest.approx(50.0)
    assert result[0].by_asset_class["US_EQUITY"].net_base == pytest.approx(600.0)
    assert result[0].by_country["IN"].short_base == pytest.approx(200.0)
    assert result[0].by_country["UNKNOWN"].long_base == pytest.approx(50.0)
    assert result[1].gross_base == 0.0
    assert result[1].by_country == {}


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
            SimpleNamespace(
                order_id=None,
                date=date(2024, 1, 4),
                symbol="USDINR",
                qty=40000.0,
                price_native=80.0,
                notional_native=500.0,
                commission_native=0.0,
                slippage_native=0.5,
                meta={"kind": "FX_SWEEP"},
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
    assert result.slippage_native == pytest.approx({"USD": 0.8, "INR": 3.0})
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
    start = date(2024, 1, 2)
    order_id = uuid4()
    db = _FakeDB(
        metrics=SimpleNamespace(
            run_id=uuid4(),
            turnover=1.8,
            gross_return=0.42,
            net_return=0.35,
            fee_drag=0.01,
            tax_drag=0.04,
            borrow_drag=0.01,
            margin_interest_drag=0.01,
        ),
        fills=[
            SimpleNamespace(
                fill_id=uuid4(),
                order_id=order_id,
                date=start,
                symbol="AAPL",
                qty=50.0,
                notional_native=5000.0,
                meta={},
            ),
            SimpleNamespace(
                fill_id=uuid4(),
                order_id=None,
                date=start + timedelta(days=1),
                symbol="MSFT",
                qty=10.0,
                notional_native=3000.0,
                meta={},
            ),
        ],
        order_sides=[(order_id, "BUY")],
        equity_rows=[
            SimpleNamespace(date=start + timedelta(days=index), equity_base=1000.0 + index * 10.0)
            for index in range(23)
        ],
        positions=[
            SimpleNamespace(
                date=start + timedelta(days=22),
                symbol="AAPL",
                qty=50.0,
                market_value_base=6000.0,
            ),
            SimpleNamespace(
                date=start + timedelta(days=22),
                symbol="MSFT",
                qty=10.0,
                market_value_base=3500.0,
            ),
        ],
        tax_rows=[
            SimpleNamespace(
                date=start + timedelta(days=10),
                symbol="AAPL",
                realized_pnl_base=1000.0,
                tax_due_base=200.0,
                bucket="US_ST",
            )
        ],
        run_config={
            "tax": {"regime": "US"},
            "base_currency": "USD",
            "universe": {
                "instruments": [
                    {"symbol": "AAPL", "asset_class": "US_EQUITY"},
                    {"symbol": "MSFT", "asset_class": "US_EQUITY"},
                ]
            },
        },
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
        "headline",
        "summary",
        "best_period",
        "worst_period",
        "largest_position",
        "largest_trade",
        "largest_tax_event",
    }
    assert result.total_drag == pytest.approx(-0.07)
    assert result.drag_breakdown["taxes"] == pytest.approx(-0.04)
    assert result.dominant_drag == "taxes"
    assert result.trade_count == 2
    assert result.tax_regime == "US"
    assert result.best_period is not None
    assert result.worst_period is not None
    assert result.largest_position.symbol == "AAPL"
    assert result.largest_trade.symbol == "AAPL"
    assert "42.00% gross and 35.00% net" in result.summary
    assert "Taxes were the largest drag." in result.summary
    assert result.largest_trade.side == "BUY"
    assert result.largest_trade.notional_base == pytest.approx(5000.0)
    assert result.largest_tax_event.tax_due_base == pytest.approx(200.0)

    metrics_result = get_run_metrics(run_id=uuid4(), actor=actor, db=db)
    assert metrics_result.explanation == result.summary


def test_html_report_is_self_contained_and_uses_json_report(monkeypatch):
    run_id = uuid4()
    monkeypatch.setattr(
        runs_routes,
        "get_run_report_json",
        lambda **_kwargs: {
            "run": {
                "run_id": str(run_id),
                "name": "Offline report",
                "status": "SUCCEEDED",
                "data_snapshot_id": "snapshot-1",
                "seed": 42,
                "config_snapshot": {
                    "strategy": "BUY_AND_HOLD",
                    "base_currency": "USD",
                    "backtest": {
                        "start_date": "2024-01-01",
                        "end_date": "2024-12-31",
                    },
                },
            },
            "metrics": {
                "net_return": 0.1234,
                "cagr": 0.1,
                "sharpe": 1.2,
                "max_drawdown": -0.08,
            },
            "explanation": {
                "headline": "Net return 12.34%.",
                "summary": "The run earned 12.34% net.",
                "drag_breakdown": {"fees": -0.002},
            },
            "costs": {
                "fees_total_base": 20.0,
                "taxes_total_base": 10.0,
                "borrow_fees_base": 0.0,
                "margin_interest_base": 0.0,
            },
            "taxes": {"event_count": 1},
            "latest_equity": {"equity_base": 11234.0},
        },
    )

    response = runs_routes.get_run_report_html(
        run_id=run_id,
        actor=ActorContext(tier=ActorTier.GUEST, actor_key="guest:test"),
        db=object(),
    )
    html = response.body.decode()

    assert response.media_type == "text/html"
    assert "Offline report" in html
    assert "12.34%" in html
    assert "<style>" in html
    assert "<svg" in html
    assert 'href="http' not in html and 'src="http' not in html
    assert "<link" not in html and "<script" not in html
