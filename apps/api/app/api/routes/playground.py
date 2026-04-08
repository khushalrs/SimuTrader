from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.playground.presets import GLOBAL_PRESET_DEFINITIONS
from app.playground.service import enqueue_global_preset_run
from app.schemas.backtests import BacktestOut

router = APIRouter(prefix="/playground", tags=["playground"])


def _to_backtest_out(run) -> BacktestOut:
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


@router.post("/presets/{preset_id}/run", response_model=BacktestOut)
def get_or_create_global_preset_run(
    preset_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> BacktestOut:
    if preset_id not in GLOBAL_PRESET_DEFINITIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found")

    run = enqueue_global_preset_run(db, preset_id)
    if run.status == "SUCCEEDED":
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_202_ACCEPTED
    return _to_backtest_out(run)

