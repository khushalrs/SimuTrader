from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.backtests import BacktestRun
from app.models.research import ResearchJob, ResearchJobRun
from app.security import ActorContext, ActorTier
from app.services.run_dispatch import dispatch_run
from app.settings import get_settings

logger = logging.getLogger(__name__)

TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "ENQUEUE_FAILED"}
TERMINAL_JOB_STATUSES = {"SUCCEEDED", "PARTIAL_FAILED", "FAILED"}
ACTIVE_RUN_STATUSES = {"QUEUED", "RUNNING"}


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
    n_planned = 0
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
                n_planned += 1
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
            job.stage = "FANOUT"
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
