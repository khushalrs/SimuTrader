from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.routes import runs as runs_routes
from app.db import engine, get_db
from app.models.assets import Asset
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunFill,
    RunMetric,
    RunOrder,
    RunPosition,
    RunTaxEvent,
)
from app.security import ActorContext, ActorTier, get_current_actor


@pytest.fixture
def postgres_session():
    """Real PostgreSQL session whose complete test graph is rolled back."""
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL read-endpoint smoke test requires PostgreSQL")
    try:
        connection = engine.connect()
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL is unavailable: {exc}")
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _seed_complete_run(db: Session) -> tuple[BacktestRun, ActorContext]:
    suffix = uuid4().hex[:12].upper()
    long_symbol = f"PGUS{suffix}"
    short_symbol = f"PGSH{suffix}"
    actor = ActorContext(tier=ActorTier.GUEST, actor_key=f"guest:pg-smoke-{suffix}")
    start = date(2024, 1, 2)
    now = datetime.now(timezone.utc)
    run = BacktestRun(
        run_id=uuid4(),
        name="PostgreSQL read smoke",
        status="SUCCEEDED",
        actor_tier="guest",
        actor_key=actor.actor_key,
        created_at=now,
        started_at=now,
        finished_at=now,
        config_snapshot={
            "version": 1,
            "strategy": "FIXED_WEIGHT_REBALANCE",
            "base_currency": "USD",
            "commission": {"model": "BPS", "bps": 5, "min_fee_native": 1},
            "slippage": {"model": "BPS", "bps": 2},
            "tax": {"regime": "US"},
            "universe": {
                "instruments": [
                    {"symbol": long_symbol, "asset_class": "US_EQUITY"},
                    {"symbol": short_symbol, "asset_class": "US_EQUITY"},
                ]
            },
            "backtest": {
                "start_date": start.isoformat(),
                "end_date": (start + timedelta(days=29)).isoformat(),
                "initial_cash": 10_000,
            },
        },
        data_snapshot_id="postgres-smoke-snapshot",
        seed=42,
    )
    db.add_all(
        [
            Asset(
                symbol=long_symbol,
                name="Postgres Smoke Long",
                asset_class="US_EQUITY",
                currency="USD",
                exchange="TEST",
                data_source="pytest",
                meta={},
            ),
            Asset(
                symbol=short_symbol,
                name="Postgres Smoke Short",
                asset_class="US_EQUITY",
                currency="USD",
                exchange="TEST",
                data_source="pytest",
                meta={},
            ),
            run,
        ]
    )
    db.flush()

    db.add(
        RunMetric(
            run_id=run.run_id,
            cagr=0.12,
            volatility=0.18,
            sharpe=0.8,
            sortino=1.1,
            max_drawdown=-0.08,
            turnover=1.5,
            gross_return=0.11,
            net_return=0.10,
            fee_drag=0.003,
            tax_drag=0.005,
            borrow_drag=0.001,
            margin_interest_drag=0.001,
            meta={"calmar": 1.5, "var_95": -0.02, "cvar_95": -0.03},
        )
    )
    for offset in range(30):
        day = start + timedelta(days=offset)
        equity = 10_000.0 + offset * 40.0
        db.add(
            RunDailyEquity(
                run_id=run.run_id,
                date=day,
                equity_base=equity,
                cash_base=5_000.0,
                gross_exposure_base=5_000.0,
                net_exposure_base=3_000.0,
                drawdown=-0.01 if offset == 10 else 0.0,
                fees_cum_base=12.0 if offset == 29 else offset * 0.4,
                taxes_cum_base=20.0 if offset == 29 else 0.0,
                borrow_fees_cum_base=3.0 if offset == 29 else 0.0,
                margin_interest_cum_base=2.0 if offset == 29 else 0.0,
                equity_by_currency={"USD": equity},
                cash_by_currency={"USD": 5_000.0},
                fees_cum_by_currency={"USD": 12.0 if offset == 29 else offset * 0.4},
            )
        )

    position_date = start + timedelta(days=29)
    db.add_all(
        [
            RunPosition(
                run_id=run.run_id,
                date=position_date,
                symbol=long_symbol,
                qty=30,
                avg_cost_native=100,
                market_value_base=3_600,
                unrealized_pnl_base=600,
            ),
            RunPosition(
                run_id=run.run_id,
                date=position_date,
                symbol=short_symbol,
                qty=-10,
                avg_cost_native=100,
                market_value_base=-1_200,
                unrealized_pnl_base=-200,
            ),
        ]
    )
    buy_order = RunOrder(
        order_id=uuid4(),
        run_id=run.run_id,
        date=start,
        symbol=long_symbol,
        side="BUY",
        qty=30,
        order_type="MARKET",
        status="FILLED",
        meta={},
    )
    sell_order = RunOrder(
        order_id=uuid4(),
        run_id=run.run_id,
        date=start + timedelta(days=1),
        symbol=short_symbol,
        side="SELL",
        qty=10,
        order_type="MARKET",
        status="FILLED",
        meta={},
    )
    fx_order = RunOrder(
        order_id=uuid4(),
        run_id=run.run_id,
        date=start,
        symbol="USDINR",
        side="FX",
        qty=100,
        order_type="MARKET",
        status="FILLED",
        meta={"kind": "FX_SWEEP"},
    )
    db.add_all([buy_order, sell_order, fx_order])
    db.flush()
    db.add_all(
        [
            RunFill(
                order_id=buy_order.order_id,
                run_id=run.run_id,
                date=start,
                symbol=long_symbol,
                qty=30,
                price_native=100,
                commission_native=5,
                slippage_native=2,
                notional_native=3_000,
                meta={},
            ),
            RunFill(
                order_id=sell_order.order_id,
                run_id=run.run_id,
                date=start + timedelta(days=1),
                symbol=short_symbol,
                qty=10,
                price_native=100,
                commission_native=4,
                slippage_native=1,
                notional_native=1_000,
                meta={},
            ),
            RunFill(
                order_id=fx_order.order_id,
                run_id=run.run_id,
                date=start,
                symbol="USDINR",
                qty=100,
                price_native=80,
                commission_native=0,
                slippage_native=0.5,
                notional_native=1.25,
                meta={"kind": "FX_SWEEP"},
            ),
            RunTaxEvent(
                tax_event_id=uuid4(),
                run_id=run.run_id,
                date=start + timedelta(days=15),
                symbol=long_symbol,
                quantity=5,
                realized_pnl_base=200,
                holding_period_days=15,
                bucket="US_ST",
                tax_rate=0.25,
                tax_due_base=50,
                meta={},
            ),
        ]
    )
    db.flush()
    return run, actor


def test_all_run_read_endpoints_execute_against_postgres(
    postgres_session: Session, monkeypatch
) -> None:
    run, actor = _seed_complete_run(postgres_session)
    monkeypatch.setattr(runs_routes, "get_cached_run_status", lambda *_args: None)
    monkeypatch.setattr(runs_routes, "set_cached_run_status", lambda *_args: None)
    monkeypatch.setattr(runs_routes, "set_cached_run_summary", lambda *_args: None)
    monkeypatch.setattr(runs_routes, "get_cached_top_holdings", lambda *_args: None)
    monkeypatch.setattr(runs_routes, "set_cached_top_holdings", lambda *_args: None)

    app = FastAPI()
    app.include_router(runs_routes.router)
    app.dependency_overrides[get_current_actor] = lambda: actor

    def override_db():
        yield postgres_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    prefix = f"/runs/{run.run_id}"

    json_paths = [
        "",
        "/status",
        "/equity",
        "/exposure",
        "/metrics",
        "/explain",
        "/positions",
        "/fills",
        "/costs_summary",
        "/report.json",
        "/top-holdings",
    ]
    responses = {path: client.get(f"{prefix}{path}") for path in json_paths}
    failures = {
        path: (response.status_code, response.text[:500])
        for path, response in responses.items()
        if response.status_code != 200
    }
    assert failures == {}

    costs = responses["/costs_summary"].json()
    assert costs["commissions_native"] == pytest.approx({"USD": 9.0})
    assert costs["slippage_native"] == pytest.approx({"USD": 3.5})
    assert costs["fees_total_base"] == pytest.approx(12.0)
    exposure = responses["/exposure"].json()[-1]
    assert exposure["long_base"] == pytest.approx(3_600)
    assert exposure["short_base"] == pytest.approx(1_200)
    assert exposure["by_asset_class"]["US_EQUITY"]["gross_base"] == pytest.approx(4_800)
    report = responses["/report.json"].json()
    assert len(report["equity_curve"]) == 30
    assert len(report["trades"]) == 3
    assert len(report["tax_events"]) == 1

    html = client.get(f"{prefix}/report.html")
    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/html")
    assert "Portfolio path" in html.text
    assert "Tax events (1)" in html.text

    for export in ("equity", "fills", "taxes"):
        response = client.get(f"{prefix}/export/{export}.csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
