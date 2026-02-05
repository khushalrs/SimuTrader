"""Celery worker for async backtests."""

from __future__ import annotations

import os

from celery import Celery
from uuid import UUID

from app.backtest import execute_run
from app.db.session import SessionLocal
from app.models.backtests import BacktestRun

celery_app = Celery(
    "simutrader",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)


@celery_app.task(name="app.backtest.execute_run")
def execute_run_task(run_id: str) -> str:
    db = SessionLocal()
    try:
        try:
            run_uuid = UUID(run_id)
        except ValueError:
            return "INVALID"
        run = db.query(BacktestRun).filter(BacktestRun.run_id == run_uuid).first()
        if not run:
            return "MISSING"
        execute_run(db, run)
        return run.status
    finally:
        db.close()
