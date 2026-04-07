from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.api.routes import backtests as backtests_routes
from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric, RunTaxEvent
from app.security import ActorContext, ActorTier


@dataclass
class _FakeQuery:
    all_values: list | None = None
    first_value: object | None = None
    _offset: int = 0
    _limit: int | None = None

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def order_by(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def offset(self, value: int):
        self._offset = value
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def all(self):
        values = list(self.all_values or [])
        if self._offset:
            values = values[self._offset :]
        if self._limit is not None:
            values = values[: self._limit]
        return values

    def first(self):
        return self.first_value


class _FakeDB:
    def __init__(self):
        self.backtests: list = []
        self.tax_rows: list = []
        self.metric_queue: list = []
        self.equity_queue: list = []

    def query(self, model):
        if model is BacktestRun:
            first_value = self.backtests[0] if self.backtests else None
            return _FakeQuery(all_values=self.backtests, first_value=first_value)
        if model is RunTaxEvent:
            return _FakeQuery(all_values=self.tax_rows)
        if model is RunMetric:
            next_metric = self.metric_queue.pop(0) if self.metric_queue else None
            return _FakeQuery(first_value=next_metric)
        if model is RunDailyEquity:
            next_equity = self.equity_queue.pop(0) if self.equity_queue else []
            return _FakeQuery(all_values=next_equity)
        raise AssertionError(f"Unexpected model query: {model}")


def test_list_backtests_returns_paginated_actor_runs():
    db = _FakeDB()
    now = datetime.now(timezone.utc)
    db.backtests = [
        BacktestRun(
            run_id=uuid4(),
            status="SUCCEEDED",
            actor_key="guest:test",
            created_at=now,
            config_snapshot={},
            data_snapshot_id="d1",
            seed=42,
        ),
        BacktestRun(
            run_id=uuid4(),
            status="FAILED",
            actor_key="guest:test",
            created_at=now,
            config_snapshot={},
            data_snapshot_id="d2",
            seed=42,
        ),
    ]
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    rows = backtests_routes.list_backtests(limit=1, offset=0, actor=actor, db=db)
    assert len(rows) == 1


def test_get_backtest_taxes_returns_summary(monkeypatch):
    run_id = uuid4()
    db = _FakeDB()
    db.tax_rows = [
        SimpleNamespace(
            tax_event_id=uuid4(),
            date=date(2024, 1, 2),
            symbol="AAA",
            quantity=1.0,
            realized_pnl_base=100.0,
            holding_period_days=30,
            bucket="US_ST",
            tax_rate=0.3,
            tax_due_base=30.0,
            meta={},
        ),
        SimpleNamespace(
            tax_event_id=uuid4(),
            date=date(2024, 1, 3),
            symbol="AAA",
            quantity=1.0,
            realized_pnl_base=-50.0,
            holding_period_days=31,
            bucket="US_ST",
            tax_rate=0.3,
            tax_due_base=0.0,
            meta={},
        ),
    ]
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    monkeypatch.setattr(
        backtests_routes,
        "_get_actor_run",
        lambda rid, _actor, _db: SimpleNamespace(run_id=rid, actor_key=_actor.actor_key),
    )
    out = backtests_routes.get_backtest_taxes(run_id=run_id, actor=actor, db=db)
    assert out.event_count == 2
    assert out.total_realized_pnl_base == 50.0
    assert out.total_tax_due_base == 30.0
    assert out.by_bucket_tax_due_base["US_ST"] == 30.0


def test_compare_backtests_returns_normalized_series(monkeypatch):
    run_a = uuid4()
    run_b = uuid4()
    db = _FakeDB()
    db.metric_queue = [
        SimpleNamespace(
            cagr=0.1,
            volatility=0.2,
            sharpe=1.0,
            max_drawdown=-0.1,
            gross_return=0.12,
            net_return=0.1,
            fee_drag=0.01,
            tax_drag=0.02,
            borrow_drag=0.0,
            margin_interest_drag=0.0,
        ),
        SimpleNamespace(
            cagr=0.2,
            volatility=0.25,
            sharpe=1.2,
            max_drawdown=-0.08,
            gross_return=0.22,
            net_return=0.2,
            fee_drag=0.01,
            tax_drag=0.01,
            borrow_drag=0.0,
            margin_interest_drag=0.0,
        ),
    ]
    db.equity_queue = [
        [
            SimpleNamespace(date=date(2024, 1, 2), equity_base=100.0),
            SimpleNamespace(date=date(2024, 1, 3), equity_base=110.0),
        ],
        [
            SimpleNamespace(date=date(2024, 1, 2), equity_base=50.0),
            SimpleNamespace(date=date(2024, 1, 3), equity_base=60.0),
        ],
    ]
    actor = ActorContext(tier=ActorTier.GUEST, actor_key="guest:test")
    monkeypatch.setattr(
        backtests_routes,
        "_get_actor_run",
        lambda rid, _actor, _db: SimpleNamespace(run_id=rid, actor_key=_actor.actor_key),
    )
    out = backtests_routes.compare_backtests(
        run_id=run_a,
        run_ids=str(run_b),
        actor=actor,
        db=db,
    )
    assert out.base_run_id == run_a
    assert out.run_ids == [run_a, run_b]
    assert len(out.metric_rows) == 2
    assert out.equity_series[0].points[0].value == 1.0
    assert out.equity_series[0].points[1].value == 1.1
    assert out.equity_series[1].points[0].value == 1.0
    assert out.equity_series[1].points[1].value == 1.2
