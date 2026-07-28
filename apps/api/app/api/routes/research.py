from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.backtest.engine import _compute_metrics
from app.db import get_db
from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric
from app.models.research import ResearchJob, ResearchJobRun
from app.schemas.research import (
    ResearchEquityPointOut,
    ResearchIsOosSpecIn,
    ResearchJobCreate,
    ResearchJobFailureOut,
    ResearchJobOut,
    ResearchJobProgressOut,
    ResearchResultMetricOut,
    ResearchRobustnessOut,
    ResearchSweepResultOut,
    ResearchSweepSpecIn,
    ResearchWalkForwardEquityOut,
    ResearchWalkForwardSpecIn,
)
from app.security import ActorContext, ActorTier, get_current_actor
from app.services.research import (
    build_sweep_plans,
    build_windowed_plan,
    expand_sweep_grid,
    generate_walk_forward_segments,
    split_evaluation_windows,
)
from app.services.research_analytics import build_stitched_walk_forward_equity
from app.services.research_jobs import (
    TERMINAL_JOB_STATUSES,
    aggregate_research_job,
)
from app.services.robustness import (
    ROBUSTNESS_SUMMARY_VERSION,
    compute_research_robustness,
)
from app.settings import get_settings

router = APIRouter(prefix="/research", tags=["research"])
GLOBAL_PRESET_ACTOR_PREFIX = "preset:global:"


def _metric_out(metrics: RunMetric | None) -> ResearchResultMetricOut | None:
    if metrics is None:
        return None
    return ResearchResultMetricOut(
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


def _degradation(
    source: RunMetric | None,
    target: RunMetric | None,
) -> dict[str, float | None] | None:
    if source is None or target is None:
        return None
    result: dict[str, float | None] = {}
    for name in ("sharpe", "cagr"):
        source_value = getattr(source, name)
        target_value = getattr(target, name)
        result[f"{name}_ratio"] = (
            float(target_value) / float(source_value)
            if source_value is not None
            and target_value is not None
            and abs(float(source_value)) > 1e-12
            else None
        )
        result[f"{name}_delta"] = (
            float(target_value) - float(source_value)
            if source_value is not None and target_value is not None
            else None
        )
    return result


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
    plan_rows: list[dict] = []
    resolved_spec = payload.spec.model_dump(mode="json", by_alias=True)
    planned_child_count = 0
    stage = "FANOUT"
    try:
        if isinstance(payload.spec, ResearchSweepSpecIn):
            plans = build_sweep_plans(
                base_config=base_run.config_snapshot or {},
                base_run_id=base_run.run_id,
                spec=payload.spec,
                data_snapshot_id=base_run.data_snapshot_id,
                seed=base_run.seed,
                max_points=child_cap,
            )
            planned_child_count = len(plans)
            plan_rows = [
                {"plan": plan, "role": "SWEEP", "segment_index": None}
                for plan in plans
            ]
        else:
            equity_dates = [
                item[0]
                for item in (
                    db.query(RunDailyEquity.date)
                    .filter(RunDailyEquity.run_id == base_run.run_id)
                    .order_by(RunDailyEquity.date.asc())
                    .all()
                )
            ]
            if isinstance(payload.spec, ResearchIsOosSpecIn):
                is_window, oos_window = split_evaluation_windows(
                    equity_dates,
                    payload.spec.split_pct,
                )
                params = (
                    expand_sweep_grid(
                        ResearchSweepSpecIn(grid=payload.spec.grid),
                        max_points=child_cap - 1,
                        base_config=base_run.config_snapshot or {},
                    )
                    if payload.spec.grid
                    else [{}]
                )
                planned_child_count = len(params) + (1 if payload.spec.grid else 1)
                if planned_child_count > child_cap:
                    raise ValueError(
                        f"Research job requires {planned_child_count} child runs; "
                        f"cap is {child_cap}."
                    )
                resolved_spec["windows"] = {
                    "is": {
                        "start_date": is_window.start_date.isoformat(),
                        "evaluation_start_date": (
                            is_window.evaluation_start_date.isoformat()
                        ),
                        "end_date": is_window.end_date.isoformat(),
                    },
                    "oos": {
                        "start_date": oos_window.start_date.isoformat(),
                        "evaluation_start_date": (
                            oos_window.evaluation_start_date.isoformat()
                        ),
                        "end_date": oos_window.end_date.isoformat(),
                    },
                }
                is_plans = [
                    build_windowed_plan(
                        base_config=base_run.config_snapshot or {},
                        base_run_id=base_run.run_id,
                        params=point,
                        window=is_window,
                        data_snapshot_id=base_run.data_snapshot_id,
                        seed=base_run.seed,
                        ordinal=index,
                    )
                    for index, point in enumerate(params)
                ]
                plan_rows = [
                    {"plan": plan, "role": "IS", "segment_index": None}
                    for plan in is_plans
                ]
                if not payload.spec.grid:
                    oos_plan = build_windowed_plan(
                        base_config=base_run.config_snapshot or {},
                        base_run_id=base_run.run_id,
                        params={},
                        window=oos_window,
                        data_snapshot_id=base_run.data_snapshot_id,
                        seed=base_run.seed,
                        ordinal=1,
                    )
                    plan_rows.append(
                        {
                            "plan": oos_plan,
                            "role": "OOS",
                            "segment_index": None,
                        }
                    )
                    plan_rows[0]["is_selected"] = True
                stage = "IS"
            elif isinstance(payload.spec, ResearchWalkForwardSpecIn):
                segments = generate_walk_forward_segments(
                    equity_dates,
                    train_len=payload.spec.train_len,
                    test_len=payload.spec.test_len,
                    step=int(payload.spec.step),
                    mode=payload.spec.mode,
                )
                max_grid_points = child_cap // (len(segments) + 1)
                params = expand_sweep_grid(
                    ResearchSweepSpecIn(grid=payload.spec.grid),
                    max_points=max_grid_points,
                    base_config=base_run.config_snapshot or {},
                )
                planned_child_count = len(segments) * (len(params) + 1)
                if planned_child_count > child_cap:
                    raise ValueError(
                        f"Research job requires {planned_child_count} child runs; "
                        f"cap is {child_cap}."
                    )
                resolved_spec["segments"] = [
                    {
                        "index": segment.index,
                        "train": {
                            "start_date": segment.train.start_date.isoformat(),
                            "evaluation_start_date": (
                                segment.train.evaluation_start_date.isoformat()
                            ),
                            "end_date": segment.train.end_date.isoformat(),
                        },
                        "test": {
                            "start_date": segment.test.start_date.isoformat(),
                            "evaluation_start_date": (
                                segment.test.evaluation_start_date.isoformat()
                            ),
                            "end_date": segment.test.end_date.isoformat(),
                        },
                    }
                    for segment in segments
                ]
                ordinal = 0
                for segment in segments:
                    for point in params:
                        plan_rows.append(
                            {
                                "plan": build_windowed_plan(
                                    base_config=base_run.config_snapshot or {},
                                    base_run_id=base_run.run_id,
                                    params=point,
                                    window=segment.train,
                                    data_snapshot_id=base_run.data_snapshot_id,
                                    seed=base_run.seed,
                                    ordinal=ordinal,
                                ),
                                "role": "TRAIN",
                                "segment_index": segment.index,
                            }
                        )
                        ordinal += 1
                stage = "TRAIN"
            else:  # pragma: no cover - guarded by request validation
                raise ValueError("Unsupported research job type.")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    job = ResearchJob(
        base_run_id=base_run.run_id,
        type=payload.type,
        base_config=base_run.config_snapshot or {},
        spec=resolved_spec,
        status="QUEUED",
        stage=stage,
        planned_child_count=planned_child_count,
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
                ordinal=item["plan"].ordinal,
                role=item["role"],
                params_json=item["plan"].params,
                config_json=item["plan"].config,
                config_hash=item["plan"].config_hash,
                dispatch_status="PLANNED",
                segment_index=item["segment_index"],
                is_selected=bool(item.get("is_selected", False)),
            )
            for item in plan_rows
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
    metrics_by_plan_id = {
        plan.job_run_id: metrics
        for plan, _run, metrics in rows
        if metrics is not None
    }
    for plan, run, metrics in rows:
        backtest = (plan.config_json or {}).get("backtest") or {}
        comparison_plan = None
        if plan.role == "OOS":
            comparison_plan = next(
                (
                    candidate
                    for candidate, _candidate_run, _candidate_metrics in rows
                    if candidate.role == "IS" and candidate.is_selected
                ),
                None,
            )
        elif plan.role == "TEST":
            comparison_plan = next(
                (
                    candidate
                    for candidate, _candidate_run, _candidate_metrics in rows
                    if candidate.role == "TRAIN"
                    and candidate.segment_index == plan.segment_index
                    and candidate.is_selected
                ),
                None,
            )
        result.append(
            ResearchSweepResultOut(
                params=plan.params_json or {},
                run_id=run.run_id if run is not None else None,
                role=plan.role,
                segment_index=plan.segment_index,
                is_selected=bool(plan.is_selected),
                start_date=backtest.get("start_date"),
                evaluation_start_date=backtest.get("evaluation_start_date"),
                end_date=backtest.get("end_date"),
                status=(
                    run.status
                    if run is not None
                    else (
                        "DISPATCH_FAILED"
                        if plan.dispatch_status == "FAILED"
                        else "PLANNED"
                    )
                ),
                metrics=_metric_out(metrics),
                degradation=_degradation(
                    metrics_by_plan_id.get(comparison_plan.job_run_id)
                    if comparison_plan is not None
                    else None,
                    metrics,
                ),
            )
        )
    return result


@router.get(
    "/jobs/{job_id}/equity",
    response_model=ResearchWalkForwardEquityOut,
)
def get_walk_forward_equity(
    job_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ResearchWalkForwardEquityOut:
    job = _get_actor_job(job_id, actor, db)
    if job.type != "WALK_FORWARD":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stitched equity is only available for WALK_FORWARD jobs.",
        )
    stitched = build_stitched_walk_forward_equity(db, job)
    metric_out = None
    if stitched.values and stitched.starting_capital is not None:
        computed = _compute_metrics(
            stitched.values,
            [0.0] * len(stitched.values),
            initial_cash=stitched.starting_capital,
        )
        metric_out = ResearchResultMetricOut(
            cagr=computed["cagr"],
            volatility=computed["volatility"],
            sharpe=computed["sharpe"],
            sortino=computed["sortino"],
            max_drawdown=computed["max_drawdown"],
            turnover=computed["turnover"],
            gross_return=computed["gross_return"],
            net_return=computed["net_return"],
        )
    return ResearchWalkForwardEquityOut(
        job_id=job.job_id,
        stitching_method="segment_return_rebase",
        points=[
            ResearchEquityPointOut(
                date=day,
                equity_base=value,
                **{
                    "return": (
                        value / float(stitched.starting_capital) - 1.0
                        if stitched.starting_capital
                        else 0.0
                    )
                },
            )
            for day, value in zip(stitched.dates, stitched.values)
        ],
        metrics=metric_out,
        is_return=stitched.is_return,
        oos_return=stitched.oos_return,
        walk_forward_efficiency=stitched.walk_forward_efficiency,
    )


@router.get(
    "/jobs/{job_id}/robustness",
    response_model=ResearchRobustnessOut,
)
def get_research_job_robustness(
    job_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ResearchRobustnessOut:
    job = _get_actor_job(job_id, actor, db)
    aggregate = aggregate_research_job(job, db)
    if aggregate.status not in TERMINAL_JOB_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Robustness is available after the research job finishes.",
        )
    if (
        job.robustness_summary is None
        or job.robustness_computed_at is None
        or job.robustness_summary.get("summary_version")
        != ROBUSTNESS_SUMMARY_VERSION
    ):
        summary, computed_at = compute_research_robustness(db, job)
        job.robustness_summary = summary
        job.robustness_computed_at = computed_at
        job.updated_at = computed_at
        db.commit()
        db.refresh(job)
    return ResearchRobustnessOut(
        job_id=job.job_id,
        computed_at=job.robustness_computed_at,
        **(job.robustness_summary or {}),
    )
