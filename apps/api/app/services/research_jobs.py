from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.backtests import BacktestRun, RunMetric
from app.models.research import ResearchJob, ResearchJobRun
from app.security import ActorContext, ActorTier
from app.services.research import EvaluationWindow, build_windowed_plan
from app.services.run_dispatch import dispatch_run
from app.settings import get_settings

logger = logging.getLogger(__name__)

TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "ENQUEUE_FAILED"}
TERMINAL_JOB_STATUSES = {"SUCCEEDED", "PARTIAL_FAILED", "FAILED"}
ACTIVE_RUN_STATUSES = {"QUEUED", "RUNNING"}
MINIMIZE_METRICS = {"volatility", "tracking_error"}


@dataclass(frozen=True)
class ResearchAggregate:
    status: str
    n_done: int
    n_total: int
    n_succeeded: int
    n_failed: int
    n_active: int
    n_planned: int
    child_run_ids: list[UUID]
    failures: list[dict]


def aggregate_research_job(job: ResearchJob, db: Session) -> ResearchAggregate:
    plans = (
        db.query(ResearchJobRun)
        .filter(ResearchJobRun.job_id == job.job_id)
        .order_by(ResearchJobRun.ordinal.asc())
        .all()
    )
    run_ids = [plan.run_id for plan in plans if plan.run_id is not None]
    runs = (
        db.query(BacktestRun).filter(BacktestRun.run_id.in_(run_ids)).all()
        if run_ids
        else []
    )
    runs_by_id = {run.run_id: run for run in runs}
    n_succeeded = 0
    n_failed = 0
    n_active = 0
    n_planned_rows = 0
    failures: list[dict] = []
    child_run_ids: list[UUID] = []
    for plan in plans:
        if plan.run_id is None:
            if plan.dispatch_status == "FAILED":
                n_failed += 1
                failures.append(
                    {
                        "run_id": None,
                        "status": "DISPATCH_FAILED",
                        "error_code": "E_RESEARCH_DISPATCH",
                        "error_message_public": "A research child could not be dispatched.",
                    }
                )
            else:
                n_planned_rows += 1
            continue
        child_run_ids.append(plan.run_id)
        run = runs_by_id.get(plan.run_id)
        if run is None:
            n_failed += 1
            failures.append(
                {
                    "run_id": plan.run_id,
                    "status": "MISSING",
                    "error_code": "E_RESEARCH_CHILD_MISSING",
                    "error_message_public": "A research child run could not be found.",
                }
            )
        elif run.status == "SUCCEEDED":
            n_succeeded += 1
        elif run.status in {"FAILED", "ENQUEUE_FAILED"}:
            n_failed += 1
            failures.append(
                {
                    "run_id": run.run_id,
                    "status": run.status,
                    "error_code": run.error_code,
                    "error_message_public": run.error_message_public,
                }
            )
        elif run.status in ACTIVE_RUN_STATUSES:
            n_active += 1

    n_total = int(job.planned_child_count)
    n_done = n_succeeded + n_failed
    n_planned = max(n_total - n_done - n_active, n_planned_rows)
    if job.status == "FAILED" and job.error_code:
        aggregate_status = "FAILED"
    elif n_done >= n_total:
        if n_succeeded == n_total:
            aggregate_status = "SUCCEEDED"
        elif n_succeeded > 0:
            aggregate_status = "PARTIAL_FAILED"
        else:
            aggregate_status = "FAILED"
    elif n_active > 0 or child_run_ids:
        aggregate_status = "RUNNING"
    else:
        aggregate_status = "QUEUED"
    return ResearchAggregate(
        status=aggregate_status,
        n_done=n_done,
        n_total=n_total,
        n_succeeded=n_succeeded,
        n_failed=n_failed,
        n_active=n_active,
        n_planned=n_planned,
        child_run_ids=child_run_ids,
        failures=failures[:50],
    )


def _window_from_dict(value: dict) -> EvaluationWindow:
    return EvaluationWindow(
        start_date=date.fromisoformat(value["start_date"]),
        evaluation_start_date=date.fromisoformat(value["evaluation_start_date"]),
        end_date=date.fromisoformat(value["end_date"]),
    )


def _plan_is_terminal(plan: ResearchJobRun, run: BacktestRun | None) -> bool:
    if plan.dispatch_status == "FAILED":
        return True
    return run is not None and run.status in TERMINAL_RUN_STATUSES


def _pick_winner(
    db: Session,
    plans: list[ResearchJobRun],
    metric_name: str,
) -> ResearchJobRun | None:
    candidates: list[tuple[float, int, ResearchJobRun]] = []
    for plan in plans:
        if plan.run_id is None:
            continue
        run, metric = (
            db.query(BacktestRun, RunMetric)
            .outerjoin(RunMetric, RunMetric.run_id == BacktestRun.run_id)
            .filter(BacktestRun.run_id == plan.run_id)
            .first()
            or (None, None)
        )
        if run is None or run.status != "SUCCEEDED" or metric is None:
            continue
        value = getattr(metric, metric_name, None)
        if value is None or not math.isfinite(float(value)):
            continue
        score = -float(value) if metric_name in MINIMIZE_METRICS else float(value)
        candidates.append((score, -int(plan.ordinal), plan))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _mark_job_no_winner(job: ResearchJob, db: Session) -> None:
    now = datetime.now(timezone.utc)
    job.status = "FAILED"
    job.stage = "COMPLETE"
    job.error_code = "E_RESEARCH_NO_WINNER"
    job.error_message_public = (
        "No successful child run produced the requested optimization metric."
    )
    job.finished_at = now
    job.updated_at = now
    db.commit()


def _materialize_dependent_plans(job: ResearchJob, db: Session) -> None:
    if job.type not in {"IS_OOS", "WALK_FORWARD"}:
        return
    plans = (
        db.query(ResearchJobRun)
        .filter(ResearchJobRun.job_id == job.job_id)
        .order_by(ResearchJobRun.ordinal.asc())
        .all()
    )
    run_ids = [plan.run_id for plan in plans if plan.run_id is not None]
    runs_by_id = {
        run.run_id: run
        for run in (
            db.query(BacktestRun).filter(BacktestRun.run_id.in_(run_ids)).all()
            if run_ids
            else []
        )
    }
    metric_name = str((job.spec or {}).get("optimize_metric") or "sharpe")
    next_ordinal = max((plan.ordinal for plan in plans), default=-1) + 1

    if job.type == "IS_OOS":
        if any(plan.role == "OOS" for plan in plans):
            return
        is_plans = [plan for plan in plans if plan.role == "IS"]
        if not is_plans or not all(
            _plan_is_terminal(plan, runs_by_id.get(plan.run_id))
            for plan in is_plans
        ):
            return
        winner = _pick_winner(db, is_plans, metric_name)
        if winner is None:
            _mark_job_no_winner(job, db)
            return
        winner.is_selected = True
        window = _window_from_dict((job.spec or {})["windows"]["oos"])
        plan = build_windowed_plan(
            base_config=job.base_config,
            base_run_id=job.base_run_id,
            params=winner.params_json or {},
            window=window,
            data_snapshot_id=job.data_snapshot_id,
            seed=job.seed,
            ordinal=next_ordinal,
        )
        db.add(
            ResearchJobRun(
                job_id=job.job_id,
                ordinal=plan.ordinal,
                role="OOS",
                params_json=plan.params,
                config_json=plan.config,
                config_hash=plan.config_hash,
                dispatch_status="PLANNED",
            )
        )
        job.stage = "OOS"
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        return

    segments = (job.spec or {}).get("segments") or []
    created = False
    for segment in segments:
        segment_index = int(segment["index"])
        if any(
            plan.role == "TEST" and plan.segment_index == segment_index
            for plan in plans
        ):
            continue
        train_plans = [
            plan
            for plan in plans
            if plan.role == "TRAIN" and plan.segment_index == segment_index
        ]
        if not train_plans or not all(
            _plan_is_terminal(plan, runs_by_id.get(plan.run_id))
            for plan in train_plans
        ):
            continue
        winner = _pick_winner(db, train_plans, metric_name)
        if winner is None:
            _mark_job_no_winner(job, db)
            return
        winner.is_selected = True
        window = _window_from_dict(segment["test"])
        plan = build_windowed_plan(
            base_config=job.base_config,
            base_run_id=job.base_run_id,
            params=winner.params_json or {},
            window=window,
            data_snapshot_id=job.data_snapshot_id,
            seed=job.seed,
            ordinal=next_ordinal,
        )
        db.add(
            ResearchJobRun(
                job_id=job.job_id,
                ordinal=plan.ordinal,
                role="TEST",
                params_json=plan.params,
                config_json=plan.config,
                config_hash=plan.config_hash,
                dispatch_status="PLANNED",
                segment_index=segment_index,
            )
        )
        next_ordinal += 1
        created = True
    if created:
        job.stage = "TEST"
        job.updated_at = datetime.now(timezone.utc)
        db.commit()


def _persist_aggregate_status(
    job: ResearchJob,
    aggregate: ResearchAggregate,
    db: Session,
) -> None:
    now = datetime.now(timezone.utc)
    job.status = aggregate.status
    job.updated_at = now
    if aggregate.status == "RUNNING" and job.started_at is None:
        job.started_at = now
    if aggregate.status in TERMINAL_JOB_STATUSES:
        job.stage = "COMPLETE"
        job.finished_at = job.finished_at or now
    db.commit()


def advance_research_job(db: Session, job_id: UUID) -> ResearchAggregate | None:
    job = db.query(ResearchJob).filter(ResearchJob.job_id == job_id).first()
    if not job:
        return None
    _materialize_dependent_plans(job, db)
    db.refresh(job)
    aggregate = aggregate_research_job(job, db)
    if aggregate.status in TERMINAL_JOB_STATUSES:
        _persist_aggregate_status(job, aggregate, db)
        return aggregate

    settings = get_settings()
    tier = ActorTier(str(job.actor_tier))
    inflight_limit = (
        settings.max_research_inflight_per_job_user
        if tier == ActorTier.USER
        else settings.max_research_inflight_per_job_guest
    )
    actor_active_limit = (
        settings.max_active_runs_per_user
        if tier == ActorTier.USER
        else settings.max_active_runs_per_guest
    )
    actor_active_count = (
        db.query(func.count(BacktestRun.run_id))
        .filter(
            BacktestRun.actor_key == job.actor_key,
            BacktestRun.status.in_(tuple(ACTIVE_RUN_STATUSES)),
        )
        .scalar()
        or 0
    )
    available_slots = max(
        min(
            inflight_limit - aggregate.n_active,
            actor_active_limit - int(actor_active_count),
        ),
        0,
    )
    actor = ActorContext(tier=tier, actor_key=job.actor_key)
    while available_slots > 0:
        plan = (
            db.query(ResearchJobRun)
            .filter(
                ResearchJobRun.job_id == job.job_id,
                ResearchJobRun.run_id.is_(None),
                ResearchJobRun.dispatch_status == "PLANNED",
            )
            .order_by(ResearchJobRun.ordinal.asc())
            .first()
        )
        if plan is None:
            break
        try:
            result = dispatch_run(
                db,
                plan.config_json,
                actor,
                f"Research {str(job.job_id)[:8]} · point {plan.ordinal + 1}",
                idempotency_key=f"research:v1:{plan.config_hash}",
                reuse_succeeded_run=True,
                data_snapshot_id=job.data_snapshot_id,
                seed=job.seed,
                strategy_id=job.strategy_id,
                enforce_actor_limits=False,
            )
            plan.run_id = result.run.run_id
            plan.dispatch_status = "DISPATCHED"
            job.status = "RUNNING"
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
            db.commit()
            if result.run.status in ACTIVE_RUN_STATUSES:
                available_slots -= 1
        except HTTPException as exc:
            logger.warning(
                "Research child dispatch rejected",
                extra={
                    "job_id": str(job.job_id),
                    "ordinal": plan.ordinal,
                    "status_code": exc.status_code,
                },
            )
            plan.dispatch_status = "FAILED"
            db.commit()
        except Exception:
            logger.exception(
                "Research child dispatch failed",
                extra={"job_id": str(job.job_id), "ordinal": plan.ordinal},
            )
            db.rollback()
            plan = (
                db.query(ResearchJobRun)
                .filter(ResearchJobRun.job_run_id == plan.job_run_id)
                .first()
            )
            if plan:
                plan.dispatch_status = "FAILED"
                db.commit()

    aggregate = aggregate_research_job(job, db)
    _persist_aggregate_status(job, aggregate, db)
    return aggregate
