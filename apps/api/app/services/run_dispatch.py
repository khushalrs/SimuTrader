from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backtest import claim_run, execute_run
from app.models.backtests import BacktestRequestIdempotency, BacktestRun
from app.security import ActorContext, ActorTier
from app.security.rate_limit import enforce_fixed_window_rate_limit, rate_limit_exceeded
from app.security.sanitize import sanitize_ascii_printable
from app.services.redis_store import refresh_run_cache
from app.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunDispatchResult:
    run: BacktestRun
    status_code: int
    reused: bool


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


def _find_reusable_run(
    db: Session,
    actor_key: str,
    resolved_config: dict,
    data_snapshot_id: str,
    seed: int,
) -> BacktestRun | None:
    return (
        db.query(BacktestRun)
        .filter(
            BacktestRun.actor_key == actor_key,
            BacktestRun.config_snapshot == resolved_config,
            BacktestRun.data_snapshot_id == data_snapshot_id,
            BacktestRun.seed == seed,
            BacktestRun.status.in_(("QUEUED", "RUNNING", "SUCCEEDED")),
        )
        .order_by(BacktestRun.created_at.desc())
        .first()
    )


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


def dispatch_run(
    db: Session,
    config: dict,
    actor: ActorContext,
    name: str | None,
    *,
    idempotency_key: str | None = None,
    reuse_succeeded_run: bool = False,
    data_snapshot_id: str,
    seed: int = 42,
    strategy_id: UUID | None = None,
    enforce_actor_limits: bool = True,
) -> RunDispatchResult:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    clean_idempotency_key = (idempotency_key or "").strip() or None
    clean_name = sanitize_ascii_printable(name, max_len=255)
    clean_data_snapshot_id = sanitize_ascii_printable(
        data_snapshot_id,
        max_len=128,
    )
    if not clean_data_snapshot_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="data_snapshot_id must be a non-empty string.",
        )
    _mark_stale_queued_runs(
        db,
        stale_after_seconds=settings.stale_queued_timeout_seconds,
    )

    if clean_idempotency_key:
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
            db,
            actor.actor_key,
            clean_idempotency_key,
            now_utc,
        )
        if existing_run:
            if existing_run.status in {"QUEUED", "RUNNING"}:
                return RunDispatchResult(
                    run=existing_run,
                    status_code=status.HTTP_202_ACCEPTED,
                    reused=True,
                )
            (
                db.query(BacktestRequestIdempotency)
                .filter(
                    BacktestRequestIdempotency.actor_key == actor.actor_key,
                    BacktestRequestIdempotency.idempotency_key
                    == clean_idempotency_key,
                )
                .delete(synchronize_session=False)
            )
            db.commit()

    if reuse_succeeded_run:
        reusable = _find_reusable_run(
            db=db,
            actor_key=actor.actor_key,
            resolved_config=config,
            data_snapshot_id=clean_data_snapshot_id,
            seed=seed,
        )
        if reusable:
            return RunDispatchResult(
                run=reusable,
                status_code=(
                    status.HTTP_202_ACCEPTED
                    if reusable.status in {"QUEUED", "RUNNING"}
                    else status.HTTP_200_OK
                ),
                reused=True,
            )

    if enforce_actor_limits:
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
            raise rate_limit_exceeded(
                detail="Too many active runs. Please wait for current runs to finish.",
                retry_after_seconds=settings.backtest_create_window_seconds,
            )
        create_rate_limit = (
            settings.max_backtest_creates_per_window_user
            if actor.tier == ActorTier.USER
            else settings.max_backtest_creates_per_window_guest
        )
        enforce_fixed_window_rate_limit(
            key=f"backtest:create:{actor.tier.value}:{actor.actor_key}",
            limit=create_rate_limit,
            window_seconds=settings.backtest_create_window_seconds,
            redis_url=settings.redis_cache_url,
            redis_prefix=settings.redis_cache_prefix,
            detail="Too many backtest creations in a short period. Please retry shortly.",
        )

    run = BacktestRun(
        strategy_id=strategy_id,
        name=clean_name,
        status="QUEUED",
        actor_tier=actor.tier.value,
        actor_key=actor.actor_key,
        config_snapshot=config,
        data_snapshot_id=clean_data_snapshot_id,
        seed=seed,
    )
    db.add(run)
    db.flush()

    if clean_idempotency_key:
        db.add(
            BacktestRequestIdempotency(
                actor_key=actor.actor_key,
                idempotency_key=clean_idempotency_key,
                run_id=run.run_id,
                expires_at=now_utc
                + timedelta(seconds=settings.backtest_idempotency_window_seconds),
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if clean_idempotency_key:
            existing_run = _find_idempotent_run(
                db,
                actor.actor_key,
                clean_idempotency_key,
                now_utc,
            )
            if existing_run:
                return RunDispatchResult(
                    run=existing_run,
                    status_code=(
                        status.HTTP_202_ACCEPTED
                        if existing_run.status in {"QUEUED", "RUNNING"}
                        else status.HTTP_200_OK
                    ),
                    reused=True,
                )
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
            return RunDispatchResult(
                run=run,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                reused=False,
            )
        return RunDispatchResult(
            run=run,
            status_code=status.HTTP_202_ACCEPTED,
            reused=False,
        )

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
        db.refresh(run)
        refresh_run_cache(run)
        return RunDispatchResult(
            run=run,
            status_code=status.HTTP_202_ACCEPTED,
            reused=False,
        )
    return RunDispatchResult(
        run=execute_run(db, claimed_run),
        status_code=status.HTTP_201_CREATED,
        reused=False,
    )
