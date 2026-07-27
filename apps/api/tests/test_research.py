from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.routes import research as research_routes
from app.db import engine, get_db
from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric
from app.models.research import ResearchJob, ResearchJobRun
from app.schemas.research import ResearchJobCreate, ResearchSweepSpecIn
from app.security import ActorContext, ActorTier, get_current_actor
from app.services.research import (
    build_sweep_plans,
    expand_sweep_grid,
    generate_walk_forward_segments,
    split_evaluation_windows,
)
from app.services.research_jobs import advance_research_job
from app.services.run_dispatch import RunDispatchResult


def _base_config() -> dict:
    return {
        "version": 1,
        "strategy": "BUY_AND_HOLD",
        "base_currency": "USD",
        "universe": {
            "instruments": [
                {
                    "symbol": "AAPL",
                    "asset_class": "US_EQUITY",
                    "amount": 1000.0,
                }
            ]
        },
        "backtest": {
            "start_date": "2024-01-02",
            "end_date": "2024-02-02",
            "initial_cash": 10_000.0,
        },
    }


def _equity_row(run_id, day: date, equity: float = 10_000.0) -> RunDailyEquity:
    return RunDailyEquity(
        run_id=run_id,
        date=day,
        equity_base=equity,
        cash_base=equity,
        gross_exposure_base=0.0,
        net_exposure_base=0.0,
        drawdown=0.0,
        fees_cum_base=0.0,
        taxes_cum_base=0.0,
        borrow_fees_cum_base=0.0,
        margin_interest_cum_base=0.0,
        equity_by_currency={"USD": equity},
        cash_by_currency={"USD": equity},
        fees_cum_by_currency={"USD": 0.0},
    )


def test_expand_sweep_grid_cartesian_range_and_deduplication() -> None:
    spec = ResearchSweepSpecIn.model_validate(
        {
            "grid": [
                {
                    "path": "commission.bps",
                    "values": {"min": 0, "max": 10, "step": 5},
                },
                {
                    "path": "slippage.bps",
                    "values": [0, 0, 2],
                },
            ]
        }
    )

    points = expand_sweep_grid(spec, max_points=10)

    assert len(points) == 6
    assert points[0] == {"commission.bps": 0.0, "slippage.bps": 0}
    assert points[-1] == {"commission.bps": 10.0, "slippage.bps": 2}


def test_expand_sweep_grid_rejects_product_above_cap() -> None:
    spec = ResearchSweepSpecIn.model_validate(
        {
            "grid": [
                {"path": "commission.bps", "values": [0, 1, 2]},
                {"path": "slippage.bps", "values": [0, 1]},
            ]
        }
    )

    with pytest.raises(ValueError, match="cap is 5"):
        expand_sweep_grid(spec, max_points=5)


def test_expand_sweep_grid_supports_linspace() -> None:
    spec = ResearchSweepSpecIn.model_validate(
        {
            "grid": [
                {
                    "path": "commission.bps",
                    "values": {"min": 0, "max": 1, "linspace": 3},
                }
            ]
        }
    )

    assert expand_sweep_grid(spec, max_points=3) == [
        {"commission.bps": 0.0},
        {"commission.bps": 0.5},
        {"commission.bps": 1.0},
    ]


def test_build_sweep_plans_is_deterministic_and_validated() -> None:
    base_run_id = uuid4()
    spec = ResearchSweepSpecIn.model_validate(
        {
            "grid": [
                {
                    "path": "execution.commission.bps",
                    "values": [0, 5],
                }
            ]
        }
    )

    first = build_sweep_plans(
        base_config=_base_config(),
        base_run_id=base_run_id,
        spec=spec,
        data_snapshot_id="snapshot",
        seed=42,
        max_points=10,
    )
    second = build_sweep_plans(
        base_config=_base_config(),
        base_run_id=base_run_id,
        spec=spec,
        data_snapshot_id="snapshot",
        seed=42,
        max_points=10,
    )

    assert [item.config_hash for item in first] == [
        item.config_hash for item in second
    ]
    assert [item.params for item in first] == [
        {"execution.commission.bps": 0},
        {"execution.commission.bps": 5},
    ]
    assert first[1].config["commission"]["bps"] == 5


def test_split_and_walk_forward_windows_use_observed_dates() -> None:
    dates = [date(2024, 1, 2) + timedelta(days=index) for index in range(10)]
    is_window, oos_window = split_evaluation_windows(dates, 0.6)
    assert is_window.end_date == dates[5]
    assert oos_window.start_date == dates[0]
    assert oos_window.evaluation_start_date == dates[6]

    segments = generate_walk_forward_segments(
        dates,
        train_len=4,
        test_len=2,
        step=2,
        mode="rolling",
    )
    assert len(segments) == 3
    assert segments[0].train.start_date == dates[0]
    assert segments[1].train.start_date == dates[2]
    assert segments[2].test.end_date == dates[9]


def test_research_job_specs_are_type_checked() -> None:
    base_run_id = uuid4()
    split = ResearchJobCreate.model_validate(
        {
            "type": "IS_OOS",
            "base_run_id": str(base_run_id),
            "spec": {"split_pct": 0.6},
        }
    )
    assert split.type == "IS_OOS"
    with pytest.raises(ValueError, match="step must equal test_len"):
        ResearchJobCreate.model_validate(
            {
                "type": "WALK_FORWARD",
                "base_run_id": str(base_run_id),
                "spec": {
                    "train_len": 63,
                    "test_len": 21,
                    "step": 10,
                    "grid": [{"path": "commission.bps", "values": [0, 5]}],
                },
            }
        )


@pytest.fixture
def postgres_session():
    if engine.dialect.name != "postgresql":
        pytest.skip("Research endpoint integration requires PostgreSQL")
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


def test_research_crud_results_and_bounded_fanout(
    postgres_session: Session,
    monkeypatch,
) -> None:
    actor = ActorContext(
        tier=ActorTier.GUEST,
        actor_key=f"guest:research-{uuid4().hex}",
    )
    now = datetime.now(timezone.utc)
    base_run = BacktestRun(
        run_id=uuid4(),
        name="Research base",
        status="SUCCEEDED",
        actor_tier=actor.tier.value,
        actor_key=actor.actor_key,
        created_at=now,
        started_at=now,
        finished_at=now,
        config_snapshot=_base_config(),
        data_snapshot_id="research-test-snapshot",
        seed=42,
    )
    postgres_session.add(base_run)
    postgres_session.flush()

    import app.worker as worker_module

    queued_jobs: list[str] = []
    monkeypatch.setattr(
        worker_module.advance_research_job_task,
        "delay",
        lambda job_id: queued_jobs.append(job_id),
    )

    app = FastAPI()
    app.include_router(research_routes.router)
    app.dependency_overrides[get_current_actor] = lambda: actor

    def override_db():
        yield postgres_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    response = client.post(
        "/research/jobs",
        json={
            "type": "SWEEP",
            "base_run_id": str(base_run.run_id),
            "spec": {
                "grid": [
                    {
                        "path": "execution.commission.bps",
                        "values": [0, 5, 10],
                    }
                ]
            },
        },
    )
    assert response.status_code == 202, response.text
    payload = response.json()
    job_id = payload["job_id"]
    assert payload["status"] == "QUEUED"
    assert payload["progress"] == {
        "n_done": 0,
        "n_total": 3,
        "n_succeeded": 0,
        "n_failed": 0,
        "n_active": 0,
        "n_planned": 3,
        "failures": [],
    }
    assert queued_jobs == [job_id]
    assert client.get("/research/jobs").status_code == 200
    planned_results = client.get(f"/research/jobs/{job_id}/results").json()
    assert [row["status"] for row in planned_results] == [
        "PLANNED",
        "PLANNED",
        "PLANNED",
    ]

    def fake_dispatch(
        db,
        config,
        dispatch_actor,
        name,
        **_kwargs,
    ):
        run = BacktestRun(
            run_id=uuid4(),
            name=name,
            status="QUEUED",
            actor_tier=dispatch_actor.tier.value,
            actor_key=dispatch_actor.actor_key,
            config_snapshot=config,
            data_snapshot_id=base_run.data_snapshot_id,
            seed=base_run.seed,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return RunDispatchResult(run=run, status_code=202, reused=False)

    monkeypatch.setattr(
        "app.services.research_jobs.dispatch_run",
        fake_dispatch,
    )
    job_uuid = UUID(job_id)
    first_aggregate = advance_research_job(postgres_session, job_uuid)
    assert first_aggregate.n_active == 2
    plans = (
        postgres_session.query(ResearchJobRun)
        .filter(ResearchJobRun.job_id == job_uuid)
        .order_by(ResearchJobRun.ordinal)
        .all()
    )
    assert [plan.run_id is not None for plan in plans] == [True, True, False]

    first_run = (
        postgres_session.query(BacktestRun)
        .filter(BacktestRun.run_id == plans[0].run_id)
        .first()
    )
    first_run.status = "SUCCEEDED"
    postgres_session.commit()
    second_aggregate = advance_research_job(postgres_session, job_uuid)
    assert second_aggregate.n_succeeded == 1
    assert second_aggregate.n_active == 2
    postgres_session.refresh(plans[2])
    assert plans[2].run_id is not None

    for plan in plans[1:]:
        postgres_session.refresh(plan)
        run = (
            postgres_session.query(BacktestRun)
            .filter(BacktestRun.run_id == plan.run_id)
            .first()
        )
        run.status = "SUCCEEDED"
    for plan in plans:
        postgres_session.add(
            RunMetric(
                run_id=plan.run_id,
                sharpe=float(plan.ordinal),
                cagr=0.1 + plan.ordinal * 0.01,
                meta={},
            )
        )
    postgres_session.commit()
    final_aggregate = advance_research_job(postgres_session, job_uuid)
    assert final_aggregate.status == "SUCCEEDED"

    detail = client.get(f"/research/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["progress"]["n_succeeded"] == 3
    results = client.get(f"/research/jobs/{job_id}/results")
    assert results.status_code == 200
    assert [row["metrics"]["sharpe"] for row in results.json()] == [0.0, 1.0, 2.0]

    other_actor = ActorContext(
        tier=ActorTier.GUEST,
        actor_key=f"guest:other-{uuid4().hex}",
    )
    app.dependency_overrides[get_current_actor] = lambda: other_actor
    assert client.get(f"/research/jobs/{job_id}").status_code == 404


def test_is_oos_winner_and_walk_forward_stitching(
    postgres_session: Session,
    monkeypatch,
) -> None:
    actor = ActorContext(
        tier=ActorTier.GUEST,
        actor_key=f"guest:research-rb23-{uuid4().hex}",
    )
    now = datetime.now(timezone.utc)
    base_run = BacktestRun(
        run_id=uuid4(),
        name="RB2/RB3 base",
        status="SUCCEEDED",
        actor_tier=actor.tier.value,
        actor_key=actor.actor_key,
        created_at=now,
        started_at=now,
        finished_at=now,
        config_snapshot=_base_config(),
        data_snapshot_id="research-rb23-snapshot",
        seed=42,
    )
    postgres_session.add(base_run)
    dates = [date(2024, 1, 2) + timedelta(days=index) for index in range(12)]
    postgres_session.add_all(
        [_equity_row(base_run.run_id, day) for day in dates]
    )
    postgres_session.commit()

    import app.worker as worker_module

    monkeypatch.setattr(
        worker_module.advance_research_job_task,
        "delay",
        lambda _job_id: None,
    )

    app = FastAPI()
    app.include_router(research_routes.router)
    app.dependency_overrides[get_current_actor] = lambda: actor

    def override_db():
        yield postgres_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    plain = client.post(
        "/research/jobs",
        json={
            "type": "IS_OOS",
            "base_run_id": str(base_run.run_id),
            "spec": {"split_pct": 0.5},
        },
    )
    assert plain.status_code == 202, plain.text
    plain_job_id = UUID(plain.json()["job_id"])
    plain_plans = (
        postgres_session.query(ResearchJobRun)
        .filter(ResearchJobRun.job_id == plain_job_id)
        .order_by(ResearchJobRun.ordinal.asc())
        .all()
    )
    assert [plan.role for plan in plain_plans] == ["IS", "OOS"]
    assert (
        plain_plans[1].config_json["backtest"]["evaluation_start_date"]
        == dates[6].isoformat()
    )
    plain_job = (
        postgres_session.query(ResearchJob)
        .filter(ResearchJob.job_id == plain_job_id)
        .first()
    )
    plain_job.status = "FAILED"
    plain_job.error_code = "E_TEST_DONE"
    postgres_session.commit()

    split = client.post(
        "/research/jobs",
        json={
            "type": "IS_OOS",
            "base_run_id": str(base_run.run_id),
            "spec": {
                "split_pct": 0.5,
                "optimize_metric": "sharpe",
                "grid": [
                    {"path": "commission.bps", "values": [1, 5]},
                ],
            },
        },
    )
    assert split.status_code == 202, split.text
    split_job_id = UUID(split.json()["job_id"])
    assert split.json()["progress"]["n_total"] == 3

    def fake_dispatch(db, config, dispatch_actor, name, **_kwargs):
        child = BacktestRun(
            run_id=uuid4(),
            name=name,
            status="SUCCEEDED",
            actor_tier=dispatch_actor.tier.value,
            actor_key=dispatch_actor.actor_key,
            config_snapshot=config,
            data_snapshot_id=base_run.data_snapshot_id,
            seed=base_run.seed,
            created_at=now,
            started_at=now,
            finished_at=now,
        )
        db.add(child)
        db.flush()
        score = float((config.get("commission") or {}).get("bps") or 0.0)
        db.add(
            RunMetric(
                run_id=child.run_id,
                sharpe=score,
                cagr=score / 100.0,
                net_return=0.1,
                meta={"initial_cash_base": 100.0},
            )
        )
        db.commit()
        return RunDispatchResult(run=child, status_code=200, reused=False)

    monkeypatch.setattr(
        "app.services.research_jobs.dispatch_run",
        fake_dispatch,
    )
    advance_research_job(postgres_session, split_job_id)
    split_aggregate = advance_research_job(postgres_session, split_job_id)
    assert split_aggregate.n_succeeded == 3
    split_results = client.get(
        f"/research/jobs/{split_job_id}/results"
    ).json()
    selected = [row for row in split_results if row["is_selected"]]
    assert selected[0]["params"] == {"commission.bps": 5}
    oos = next(row for row in split_results if row["role"] == "OOS")
    assert oos["params"] == {"commission.bps": 5}
    assert oos["degradation"]["sharpe_ratio"] == pytest.approx(1.0)

    walk = client.post(
        "/research/jobs",
        json={
            "type": "WALK_FORWARD",
            "base_run_id": str(base_run.run_id),
            "spec": {
                "train_len": 4,
                "test_len": 2,
                "step": 2,
                "mode": "rolling",
                "optimize_metric": "sharpe",
                "grid": [
                    {"path": "commission.bps", "values": [1, 5]},
                ],
            },
        },
    )
    assert walk.status_code == 202, walk.text
    walk_job_id = UUID(walk.json()["job_id"])
    assert walk.json()["progress"]["n_total"] == 12
    advance_research_job(postgres_session, walk_job_id)
    walk_aggregate = advance_research_job(postgres_session, walk_job_id)
    assert walk_aggregate.n_succeeded == 12

    test_plans = (
        postgres_session.query(ResearchJobRun)
        .filter(
            ResearchJobRun.job_id == walk_job_id,
            ResearchJobRun.role == "TEST",
        )
        .order_by(ResearchJobRun.segment_index.asc())
        .all()
    )
    assert len(test_plans) == 4
    for plan in test_plans:
        evaluation_start = date.fromisoformat(
            plan.config_json["backtest"]["evaluation_start_date"]
        )
        postgres_session.add_all(
            [
                _equity_row(plan.run_id, evaluation_start, 100.0),
                _equity_row(
                    plan.run_id,
                    evaluation_start + timedelta(days=1),
                    110.0,
                ),
            ]
        )
    postgres_session.commit()

    equity = client.get(f"/research/jobs/{walk_job_id}/equity")
    assert equity.status_code == 200, equity.text
    payload = equity.json()
    assert len(payload["points"]) == 8
    assert payload["oos_return"] == pytest.approx(0.4641)
    assert payload["is_return"] == pytest.approx(0.4641)
    assert payload["walk_forward_efficiency"] == pytest.approx(1.0)
