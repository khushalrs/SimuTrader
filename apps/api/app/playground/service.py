from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.backtests import BacktestRun
from app.playground.presets import GLOBAL_PRESET_DEFINITIONS, global_preset_actor_key
from app.services.config_validation import validate_and_resolve_config

logger = logging.getLogger(__name__)


def find_global_preset_run(db: Session, preset_id: str) -> BacktestRun | None:
    actor_key = global_preset_actor_key(preset_id)
    return (
        db.query(BacktestRun)
        .filter(
            BacktestRun.actor_key == actor_key,
            BacktestRun.status.in_(("QUEUED", "RUNNING", "SUCCEEDED")),
        )
        .order_by(BacktestRun.created_at.desc())
        .first()
    )


def ensure_global_preset_run(db: Session, preset_id: str) -> BacktestRun:
    definition = GLOBAL_PRESET_DEFINITIONS[preset_id]
    existing = find_global_preset_run(db, preset_id)
    if existing:
        return existing

    resolved_config = validate_and_resolve_config(definition["config_snapshot"])
    run = BacktestRun(
        name=definition["name"],
        status="QUEUED",
        actor_tier="guest",
        actor_key=global_preset_actor_key(preset_id),
        config_snapshot=resolved_config,
        data_snapshot_id=definition["data_snapshot_id"],
        seed=int(definition.get("seed", 42)),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def enqueue_global_preset_run(db: Session, preset_id: str) -> BacktestRun:
    run = ensure_global_preset_run(db, preset_id)
    if run.status != "QUEUED":
        return run

    from app.worker import execute_run_task

    try:
        task_result = execute_run_task.delay(str(run.run_id))
        run.execution_task_id = task_result.id
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        error_id = str(uuid4())
        logger.exception(
            "Global preset enqueue failed",
            extra={"preset_id": preset_id, "run_id": str(run.run_id), "error_id": error_id},
        )
        run.status = "ENQUEUE_FAILED"
        run.error_code = "E_ENQUEUE_FAILED"
        run.error_message_public = "The simulation could not be queued. Please retry."
        run.error_retryable = True
        run.error_id = error_id
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run

