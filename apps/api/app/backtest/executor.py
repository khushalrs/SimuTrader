"""Backtest execution helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from typing import Any

from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.backtest.buy_and_hold import run_buy_and_hold
from app.backtest.dca import run_dca
from app.backtest.errors import (
    BacktestError,
    ConfigValidationError,
    DataUnavailableError,
    NoTradingDaysError,
    UnsupportedStrategyError,
)
from app.backtest.fixed_weight_rebalance import run_fixed_weight_rebalance
from app.backtest.mean_reversion import run_mean_reversion
from app.backtest.momentum import run_momentum
from app.models.backtests import BacktestRun

logger = logging.getLogger(__name__)

TRANSIENT_EXCEPTIONS = (OperationalError, DBAPIError, OSError, ConnectionError, TimeoutError)


def claim_run(db: Session, run_id, task_id: str | None = None) -> BacktestRun | None:
    claimed_at = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "status": "RUNNING",
        "started_at": claimed_at,
        "finished_at": None,
    }
    if task_id:
        values["execution_task_id"] = task_id
    result = db.execute(
        update(BacktestRun)
        .where(BacktestRun.run_id == run_id, BacktestRun.status == "QUEUED")
        .values(**values)
    )
    db.commit()
    if result.rowcount != 1:
        return None
    return db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()


def _resolve_strategy_type(config_snapshot: dict[str, Any]) -> str:
    strategy_raw = config_snapshot.get("strategy") if config_snapshot else None
    if isinstance(strategy_raw, dict):
        return str(strategy_raw.get("type") or "BUY_AND_HOLD").upper()
    return str(strategy_raw or "BUY_AND_HOLD").upper()


def _build_config_summary(config_snapshot: dict[str, Any]) -> dict[str, Any]:
    universe = config_snapshot.get("universe") or {}
    instruments = universe.get("instruments") or []
    backtest_cfg = config_snapshot.get("backtest") or {}
    return {
        "strategy": _resolve_strategy_type(config_snapshot),
        "instrument_count": len(instruments) if isinstance(instruments, list) else None,
        "start_date": backtest_cfg.get("start_date") or config_snapshot.get("start_date"),
        "end_date": backtest_cfg.get("end_date") or config_snapshot.get("end_date"),
        "missing_bar_policy": (config_snapshot.get("data_policy") or {}).get("missing_bar"),
    }


def _map_exception(exc: Exception) -> BacktestError:
    if isinstance(exc, BacktestError):
        return exc

    message = str(exc)
    upper_message = message.upper()
    if "NO_TRADING_DAYS" in upper_message or "NO TRADING DAYS" in upper_message:
        return NoTradingDaysError(message)
    if (
        "MISSING BAR" in upper_message
        or "MISSING CURRENCY METADATA" in upper_message
        or "CALENDAR VIEWS MISSING" in upper_message
    ):
        return DataUnavailableError(message)
    if isinstance(exc, ValueError):
        return ConfigValidationError(message)
    return BacktestError(
        code="E_INTERNAL",
        public_message="The simulation failed unexpectedly. Please retry.",
        retryable=True,
        internal_message=message,
    )


def is_transient_exception(exc: Exception) -> bool:
    return isinstance(exc, TRANSIENT_EXCEPTIONS)


def execute_run(db: Session, run: BacktestRun) -> BacktestRun:
    config_snapshot = run.config_snapshot or {}
    strategy = "BUY_AND_HOLD"

    try:
        strategy = _resolve_strategy_type(config_snapshot)

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
            raise UnsupportedStrategyError(f"Unsupported strategy '{strategy}'.")

        runner(db, run, config_snapshot)
        run.status = "SUCCEEDED"
        run.error = None
        run.error_code = None
        run.error_message_public = None
        run.error_retryable = None
        run.error_id = None
    except Exception as exc:
        if is_transient_exception(exc):
            raise
        mapped_error = _map_exception(exc)
        error_id = str(uuid4())
        logger.exception(
            "Backtest run failed",
            extra={
                "run_id": str(run.run_id),
                "error_id": error_id,
                "strategy_type": strategy,
                "config_summary": _build_config_summary(config_snapshot),
            },
        )
        run.status = "FAILED"
        run.error = None
        run.error_code = mapped_error.code
        run.error_message_public = mapped_error.public_message
        run.error_retryable = mapped_error.retryable
        run.error_id = error_id
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

    return run
