from datetime import datetime, timedelta, timezone
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backtest import claim_run, execute_run
from app.db import get_db
from app.models.backtests import BacktestRequestIdempotency, BacktestRun
from app.security import ActorContext, ActorTier, get_current_actor
from app.services.redis_store import refresh_run_cache
from app.schemas.backtests import BacktestCreate, BacktestOut
from app.settings import get_settings
from app.services.config_validation import validate_and_resolve_config

router = APIRouter(prefix="/backtests", tags=["backtests"])
logger = logging.getLogger(__name__)


def _to_backtest_out(run: BacktestRun) -> BacktestOut:
    return BacktestOut(
        run_id=run.run_id,
        strategy_id=run.strategy_id,
        name=run.name,
        status=run.status,
        error_code=run.error_code,
        error_message_public=run.error_message_public,
        error_retryable=run.error_retryable,
        error_id=run.error_id,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        config_snapshot=run.config_snapshot,
        data_snapshot_id=run.data_snapshot_id,
        seed=run.seed,
    )


def _find_idempotent_run(
    db: Session,
    actor_key: str,
    idempotency_key: str,
    now_utc: datetime,
) -> BacktestRun | None:
    row = (
        db.query(BacktestRequestIdempotency)
        .filter(
            BacktestRequestIdempotency.actor_key == actor_key,
            BacktestRequestIdempotency.idempotency_key == idempotency_key,
            BacktestRequestIdempotency.expires_at > now_utc,
        )
        .first()
    )
    if not row:
        return None
    return db.query(BacktestRun).filter(BacktestRun.run_id == row.run_id).first()


def _mark_stale_queued_runs(db: Session, stale_after_seconds: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
    stale_runs = (
        db.query(BacktestRun)
        .filter(
            BacktestRun.status == "QUEUED",
            BacktestRun.started_at.is_(None),
            BacktestRun.created_at < cutoff,
        )
        .all()
    )
    for stale_run in stale_runs:
        stale_run.status = "ENQUEUE_FAILED"
        stale_run.error_code = "E_ENQUEUE_STALE"
        stale_run.error_message_public = (
            "This run could not be queued in time. Please retry."
        )
        stale_run.error_retryable = True
        stale_run.error_id = str(uuid4())
        stale_run.finished_at = datetime.now(timezone.utc)
    if stale_runs:
        db.commit()
        for stale_run in stale_runs:
            refresh_run_cache(stale_run)
    return len(stale_runs)


@router.post("", response_model=BacktestOut, status_code=status.HTTP_201_CREATED)
def create_backtest(
    payload: BacktestCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    clean_idempotency_key = (idempotency_key or "").strip() or None
    _mark_stale_queued_runs(db, stale_after_seconds=settings.stale_queued_timeout_seconds)

    try:
        resolved_config = validate_and_resolve_config(payload.config_snapshot)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if clean_idempotency_key:
        # Allow key reuse after dedupe expiry.
        (
            db.query(BacktestRequestIdempotency)
            .filter(
                BacktestRequestIdempotency.actor_key == actor.actor_key,
                BacktestRequestIdempotency.idempotency_key == clean_idempotency_key,
                BacktestRequestIdempotency.expires_at <= now_utc,
            )
            .delete(synchronize_session=False)
        )
        db.commit()

        existing_run = _find_idempotent_run(
            db, actor.actor_key, clean_idempotency_key, now_utc
        )
        if existing_run:
            if existing_run.status in {"QUEUED", "RUNNING"}:
                response.status_code = status.HTTP_202_ACCEPTED
                return _to_backtest_out(existing_run)
            (
                db.query(BacktestRequestIdempotency)
                .filter(
                    BacktestRequestIdempotency.actor_key == actor.actor_key,
                    BacktestRequestIdempotency.idempotency_key == clean_idempotency_key,
                )
                .delete(synchronize_session=False)
            )
            db.commit()

    max_active_runs = (
        settings.max_active_runs_per_user
        if actor.tier == ActorTier.USER
        else settings.max_active_runs_per_guest
    )
    active_run_count = (
        db.query(func.count(BacktestRun.run_id))
        .filter(
            BacktestRun.actor_key == actor.actor_key,
            BacktestRun.status.in_(("QUEUED", "RUNNING")),
        )
        .scalar()
        or 0
    )
    if active_run_count >= max_active_runs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many active runs. Please wait for current runs to finish.",
        )

    run = BacktestRun(
        strategy_id=payload.strategy_id,
        name=payload.name,
        status="QUEUED",
        actor_tier=actor.tier.value,
        actor_key=actor.actor_key,
        config_snapshot=resolved_config,
        data_snapshot_id=payload.data_snapshot_id,
        seed=payload.seed,
    )
    db.add(run)
    db.flush()

    if clean_idempotency_key:
        dedupe_expires_at = now_utc + timedelta(
            seconds=settings.backtest_idempotency_window_seconds
        )
        db.add(
            BacktestRequestIdempotency(
                actor_key=actor.actor_key,
                idempotency_key=clean_idempotency_key,
                run_id=run.run_id,
                expires_at=dedupe_expires_at,
            )
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if clean_idempotency_key:
            existing_run = _find_idempotent_run(
                db, actor.actor_key, clean_idempotency_key, now_utc
            )
            if existing_run:
                if existing_run.status in {"QUEUED", "RUNNING"}:
                    response.status_code = status.HTTP_202_ACCEPTED
                    return _to_backtest_out(existing_run)
        raise

    db.refresh(run)
    refresh_run_cache(run)

    if settings.backtest_exec_mode == "async":
        from app.worker import execute_run_task

        try:
            task_result = execute_run_task.delay(str(run.run_id))
            run.execution_task_id = task_result.id
            db.commit()
            db.refresh(run)
            refresh_run_cache(run)
        except Exception:
            error_id = str(uuid4())
            logger.exception(
                "Backtest enqueue failed",
                extra={
                    "run_id": str(run.run_id),
                    "error_id": error_id,
                    "actor_key": actor.actor_key,
                },
            )
            run.status = "ENQUEUE_FAILED"
            run.error_code = "E_ENQUEUE_FAILED"
            run.error_message_public = (
                "The simulation could not be queued. Please retry."
            )
            run.error_retryable = True
            run.error_id = error_id
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            refresh_run_cache(run)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return _to_backtest_out(run)
        response.status_code = status.HTTP_202_ACCEPTED
        return _to_backtest_out(run)

    if not settings.is_dev_env and not settings.allow_sync_execution:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Synchronous backtest execution is disabled in non-dev environments. "
                "Use BACKTEST_EXEC_MODE=async."
            ),
        )

    claimed_run = claim_run(db, run.run_id)
    if not claimed_run:
        response.status_code = status.HTTP_202_ACCEPTED
        db.refresh(run)
        refresh_run_cache(run)
        return _to_backtest_out(run)

    return _to_backtest_out(execute_run(db, claimed_run))


@router.get("/{run_id}", response_model=BacktestOut)
def get_backtest(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    run = (
        db.query(BacktestRun)
        .filter(BacktestRun.run_id == run_id, BacktestRun.actor_key == actor.actor_key)
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _to_backtest_out(run)
