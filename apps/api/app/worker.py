"""Celery worker for async backtests."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from uuid import UUID
from sqlalchemy import update

from app.backtest import claim_run, execute_run
from app.backtest.executor import is_transient_exception
from app.db.session import SessionLocal
from app.models.backtests import BacktestRun

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
    result = db.execute(
        update(BacktestRun)
        .where(
            BacktestRun.status == "RUNNING",
            BacktestRun.started_at.isnot(None),
            BacktestRun.started_at < cutoff,
        )
        .values(
            status="QUEUED",
            started_at=None,
            finished_at=None,
            execution_task_id=None,
        )
    )
    db.commit()
    return int(result.rowcount or 0)


def _release_run_for_retry(db, run_id: UUID) -> None:
    db.execute(
        update(BacktestRun)
        .where(BacktestRun.run_id == run_id)
        .values(
            status="QUEUED",
            started_at=None,
            finished_at=None,
            execution_task_id=None,
        )
    )
    db.commit()


@celery_app.task(bind=True, name="app.backtest.execute_run")
def execute_run_task(self, run_id: str) -> str:
    db = SessionLocal()
    try:
        stale_timeout_seconds = int(os.getenv("STALE_RUN_TIMEOUT_SECONDS", "7200"))
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
        try:
            execute_run(db, run)
        except SoftTimeLimitExceeded:
            run.status = "FAILED"
            run.error_code = "E_INTERNAL"
            run.error_message_public = "The simulation failed unexpectedly. Please retry."
            run.error_retryable = True
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            return run.status
        except Exception as exc:
            if not is_transient_exception(exc):
                raise
            _release_run_for_retry(db, run_uuid)
            max_retries = int(os.getenv("CELERY_TASK_MAX_RETRIES", "3"))
            delay_seconds = int(os.getenv("CELERY_TASK_RETRY_DELAY_SECONDS", "30"))
            raise self.retry(exc=exc, countdown=delay_seconds, max_retries=max_retries) from exc
        return run.status
    finally:
        db.close()
