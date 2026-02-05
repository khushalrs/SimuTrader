"""Backtest execution helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.backtest.buy_and_hold import run_buy_and_hold
from app.models.backtests import BacktestRun


def execute_run(db: Session, run: BacktestRun) -> BacktestRun:
    run.status = "RUNNING"
    run.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        run_buy_and_hold(db, run, run.config_snapshot)
        run.status = "SUCCEEDED"
        run.error = None
    except Exception as exc:
        run.status = "FAILED"
        run.error = str(exc)
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

    return run
