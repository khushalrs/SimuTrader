from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.backtests import BacktestRun, RunMetric
from app.models.research import ResearchJob, ResearchJobRun
from app.schemas.research import (
    ResearchJobCreate,
    ResearchJobFailureOut,
    ResearchJobOut,
    ResearchJobProgressOut,
    ResearchResultMetricOut,
    ResearchSweepResultOut,
)
from app.security import ActorContext, ActorTier, get_current_actor
from app.services.research import build_sweep_plans
from app.services.research_jobs import (
    TERMINAL_JOB_STATUSES,
    aggregate_research_job,
)
from app.settings import get_settings

router = APIRouter(prefix="/research", tags=["research"])
GLOBAL_PRESET_ACTOR_PREFIX = "preset:global:"


def _get_actor_job(
    job_id: UUID,
    actor: ActorContext,
    db: Session,
) -> ResearchJob:
    job = (
        db.query(ResearchJob)
        .filter(
            ResearchJob.job_id == job_id,
            ResearchJob.actor_key == actor.actor_key,
        )
        .first()
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research job not found",
        )
    return job


def _get_research_base_run(
    run_id: UUID,
    actor: ActorContext,
    db: Session,
) -> BacktestRun:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.actor_key != actor.actor_key and not str(run.actor_key or "").startswith(
        GLOBAL_PRESET_ACTOR_PREFIX
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _job_out(job: ResearchJob, db: Session) -> ResearchJobOut:
    aggregate = aggregate_research_job(job, db)
    return ResearchJobOut(
        job_id=job.job_id,
        type=job.type,
        base_run_id=job.base_run_id,
        status=aggregate.status,
        stage=job.stage,
        spec=job.spec or {},
        child_run_ids=aggregate.child_run_ids,
        progress=ResearchJobProgressOut(
            n_done=aggregate.n_done,
            n_total=aggregate.n_total,
            n_succeeded=aggregate.n_succeeded,
            n_failed=aggregate.n_failed,
            n_active=aggregate.n_active,
            n_planned=aggregate.n_planned,
            failures=[
                ResearchJobFailureOut.model_validate(item)
                for item in aggregate.failures
            ],
        ),
        error_code=job.error_code,
        error_message_public=job.error_message_public,
        created_at=job.created_at,
        started_at=job.started_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
    )


@router.post(
    "/jobs",
    response_model=ResearchJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_research_job(
    payload: ResearchJobCreate,
    response: Response,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ResearchJobOut:
    base_run = _get_research_base_run(payload.base_run_id, actor, db)
    settings = get_settings()
    active_job_cap = (
        settings.max_active_research_jobs_user
        if actor.tier == ActorTier.USER
        else settings.max_active_research_jobs_guest
    )
    active_job_count = (
        db.query(func.count(ResearchJob.job_id))
        .filter(
            ResearchJob.actor_key == actor.actor_key,
            ResearchJob.status.notin_(TERMINAL_JOB_STATUSES),
        )
        .scalar()
        or 0
    )
    if active_job_count >= active_job_cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many active research jobs. Wait for the current job to finish.",
        )
    child_cap = (
        settings.max_research_children_per_job_user
        if actor.tier == ActorTier.USER
        else settings.max_research_children_per_job_guest
    )
    try:
        plans = build_sweep_plans(
            base_config=base_run.config_snapshot or {},
            base_run_id=base_run.run_id,
            spec=payload.spec,
            data_snapshot_id=base_run.data_snapshot_id,
            seed=base_run.seed,
            max_points=child_cap,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    job = ResearchJob(
        base_run_id=base_run.run_id,
        type=payload.type,
        base_config=base_run.config_snapshot or {},
        spec=payload.spec.model_dump(mode="json", by_alias=True),
        status="QUEUED",
        stage="FANOUT",
        planned_child_count=len(plans),
        actor_tier=actor.tier.value,
        actor_key=actor.actor_key,
        data_snapshot_id=base_run.data_snapshot_id,
        seed=base_run.seed,
        strategy_id=base_run.strategy_id,
    )
    db.add(job)
    db.flush()
    db.add_all(
        [
            ResearchJobRun(
                job_id=job.job_id,
                ordinal=plan.ordinal,
                role="SWEEP",
                params_json=plan.params,
                config_json=plan.config,
                config_hash=plan.config_hash,
                dispatch_status="PLANNED",
            )
            for plan in plans
        ]
    )
    db.commit()
    db.refresh(job)

    from app.worker import advance_research_job_task

    try:
        advance_research_job_task.delay(str(job.job_id))
    except Exception:
        job.status = "FAILED"
        job.stage = "COMPLETE"
        job.error_code = "E_RESEARCH_ENQUEUE_FAILED"
        job.error_message_public = "The research job could not be queued."
        job.finished_at = datetime.now(timezone.utc)
        job.updated_at = job.finished_at
        db.commit()
        db.refresh(job)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return _job_out(job, db)


@router.get("/jobs/{job_id}", response_model=ResearchJobOut)
def get_research_job(
    job_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ResearchJobOut:
    return _job_out(_get_actor_job(job_id, actor, db), db)


@router.get("/jobs", response_model=list[ResearchJobOut])
def list_research_jobs(
    status_filter: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[ResearchJobOut]:
    query = db.query(ResearchJob).filter(ResearchJob.actor_key == actor.actor_key)
    if status_filter:
        query = query.filter(ResearchJob.status == status_filter.upper())
    jobs = (
        query.order_by(ResearchJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_job_out(job, db) for job in jobs]


@router.get(
    "/jobs/{job_id}/results",
    response_model=list[ResearchSweepResultOut],
)
def get_research_job_results(
    job_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[ResearchSweepResultOut]:
    job = _get_actor_job(job_id, actor, db)
    rows = (
        db.query(ResearchJobRun, BacktestRun, RunMetric)
        .outerjoin(BacktestRun, BacktestRun.run_id == ResearchJobRun.run_id)
        .outerjoin(RunMetric, RunMetric.run_id == BacktestRun.run_id)
        .filter(ResearchJobRun.job_id == job.job_id)
        .order_by(ResearchJobRun.ordinal.asc())
        .all()
    )
    result: list[ResearchSweepResultOut] = []
    for plan, run, metrics in rows:
        metric_out = (
            ResearchResultMetricOut(
                cagr=metrics.cagr,
                volatility=metrics.volatility,
                sharpe=metrics.sharpe,
                sortino=metrics.sortino,
                max_drawdown=metrics.max_drawdown,
                turnover=metrics.turnover,
                gross_return=metrics.gross_return,
                net_return=metrics.net_return,
                beta=metrics.beta,
                alpha=metrics.alpha,
                tracking_error=metrics.tracking_error,
                information_ratio=metrics.information_ratio,
            )
            if metrics is not None
            else None
        )
        result.append(
            ResearchSweepResultOut(
                params=plan.params_json or {},
                run_id=run.run_id if run is not None else None,
                status=(
                    run.status
                    if run is not None
                    else (
                        "DISPATCH_FAILED"
                        if plan.dispatch_status == "FAILED"
                        else "PLANNED"
                    )
                ),
                metrics=metric_out,
            )
        )
    return result
