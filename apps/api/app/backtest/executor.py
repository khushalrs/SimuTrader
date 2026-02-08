"""Backtest execution helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.backtest.buy_and_hold import run_buy_and_hold
from app.backtest.dca import run_dca
from app.backtest.fixed_weight_rebalance import run_fixed_weight_rebalance
from app.backtest.mean_reversion import run_mean_reversion
from app.backtest.momentum import run_momentum
from app.models.backtests import BacktestRun


def execute_run(db: Session, run: BacktestRun) -> BacktestRun:
    run.status = "RUNNING"
    run.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        strategy_raw = run.config_snapshot.get("strategy") if run.config_snapshot else None
        if isinstance(strategy_raw, dict):
            strategy = str(strategy_raw.get("type") or "BUY_AND_HOLD").upper()
        else:
            strategy = str(strategy_raw or "BUY_AND_HOLD").upper()

        if strategy == "BUY_AND_HOLD":
            runner = run_buy_and_hold
        elif strategy == "DCA":
            runner = run_dca
        elif strategy == "FIXED_WEIGHT_REBALANCE":
            runner = run_fixed_weight_rebalance
        elif strategy == "MOMENTUM":
            runner = run_momentum
        elif strategy == "MEAN_REVERSION":
            runner = run_mean_reversion
        else:
            raise ValueError(f"Unsupported strategy '{strategy}'.")

        runner(db, run, run.config_snapshot)
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
