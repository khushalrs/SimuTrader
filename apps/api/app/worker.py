"""Celery worker for async backtests."""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from uuid import UUID, uuid4

from app.backtest import claim_run, execute_run
from app.backtest.executor import is_transient_exception
from app.db.session import SessionLocal
from app.models.backtests import BacktestRun
from app.services.redis_store import (
    refresh_run_cache,
    release_run_lock,
    try_acquire_run_lock,
)
from app.settings import get_settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "simutrader",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT_SECONDS", "3600")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", "3300")),
    task_reject_on_worker_lost=True,
)

def _recover_stale_running_runs(db, stale_after_seconds: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
    stale_runs = (
        db.query(BacktestRun)
        .filter(
            BacktestRun.status == "RUNNING",
            BacktestRun.started_at.isnot(None),
            BacktestRun.started_at < cutoff,
        )
        .all()
    )
    if not stale_runs:
        return 0
    for run in stale_runs:
        run.status = "QUEUED"
        run.started_at = None
        run.finished_at = None
        run.execution_task_id = None
        run.error_code = None
        run.error_message_public = None
        run.error_retryable = None
        run.error_id = None
    db.commit()
    for run in stale_runs:
        refresh_run_cache(run)
    return len(stale_runs)


def _recover_stale_queued_runs(db, stale_after_seconds: int) -> int:
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
    if not stale_runs:
        return 0
    now = datetime.now(timezone.utc)
    for run in stale_runs:
        run.status = "ENQUEUE_FAILED"
        run.error_code = "E_ENQUEUE_STALE"
        run.error_message_public = "This run could not be queued in time. Please retry."
        run.error_retryable = True
        run.error_id = str(uuid4())
        run.finished_at = now
    db.commit()
    for run in stale_runs:
        refresh_run_cache(run)
    return len(stale_runs)


def _release_run_for_retry(db, run_id: UUID) -> None:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        return
    run.status = "QUEUED"
    run.started_at = None
    run.finished_at = None
    run.execution_task_id = None
    run.error_code = None
    run.error_message_public = None
    run.error_retryable = None
    run.error_id = None
    db.commit()
    refresh_run_cache(run)


@celery_app.task(bind=True, name="app.backtest.execute_run")
def execute_run_task(self, run_id: str) -> str:
    db = SessionLocal()
    settings = get_settings()
    lock_token = try_acquire_run_lock(run_id, settings.redis_lock_timeout_seconds)
    claimed_run_uuid: UUID | None = None
    try:
        stale_timeout_seconds = settings.stale_run_timeout_seconds
        stale_queued_timeout_seconds = settings.stale_queued_timeout_seconds
        _recover_stale_queued_runs(db, stale_after_seconds=stale_queued_timeout_seconds)
        _recover_stale_running_runs(db, stale_after_seconds=stale_timeout_seconds)

        try:
            run_uuid = UUID(run_id)
        except ValueError:
            return "INVALID"
        run = claim_run(db, run_uuid, task_id=self.request.id)
        if not run:
            exists = db.query(BacktestRun.run_id).filter(BacktestRun.run_id == run_uuid).first()
            if not exists:
                return "MISSING"
            return "SKIPPED_ALREADY_CLAIMED"
        claimed_run_uuid = run_uuid
        try:
            execute_run(db, run)
        except SoftTimeLimitExceeded:
            run.status = "FAILED"
            run.error_code = "E_INTERNAL"
            run.error_message_public = "The simulation failed unexpectedly. Please retry."
            run.error_retryable = True
            run.error_id = str(uuid4())
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            refresh_run_cache(run)
            return run.status
        except Exception as exc:
            if not is_transient_exception(exc):
                raise
            _release_run_for_retry(db, run_uuid)
            max_retries = int(os.getenv("CELERY_TASK_MAX_RETRIES", "3"))
            delay_seconds = int(os.getenv("CELERY_TASK_RETRY_DELAY_SECONDS", "30"))
            raise self.retry(exc=exc, countdown=delay_seconds, max_retries=max_retries) from exc
        return run.status
    except Exception:
        if claimed_run_uuid is not None:
            failed_run = db.query(BacktestRun).filter(BacktestRun.run_id == claimed_run_uuid).first()
            if failed_run and failed_run.status == "RUNNING":
                error_id = str(uuid4())
                logger.exception(
                    "Backtest worker failed unexpectedly",
                    extra={"run_id": str(claimed_run_uuid), "error_id": error_id},
                )
                failed_run.status = "FAILED"
                failed_run.error_code = "E_INTERNAL"
                failed_run.error_message_public = (
                    "The simulation failed unexpectedly. Please retry."
                )
                failed_run.error_retryable = True
                failed_run.error_id = error_id
                failed_run.finished_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(failed_run)
                refresh_run_cache(failed_run)
        raise
    finally:
        release_run_lock(run_id, lock_token)
        db.close()
