import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.backtest import execute_run
from app.db import get_db
from app.models.backtests import BacktestRun
from app.schemas.backtests import BacktestCreate, BacktestOut

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("", response_model=BacktestOut, status_code=status.HTTP_201_CREATED)
def create_backtest(payload: BacktestCreate, db: Session = Depends(get_db)) -> BacktestOut:
    run = BacktestRun(
        strategy_id=payload.strategy_id,
        name=payload.name,
        status="QUEUED",
        config_snapshot=payload.config_snapshot,
        data_snapshot_id=payload.data_snapshot_id,
        seed=payload.seed,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    exec_mode = os.getenv("BACKTEST_EXEC_MODE", "sync").strip().lower()
    if exec_mode == "async":
        from app.worker import execute_run_task

        execute_run_task.delay(str(run.run_id))
        return run

    return execute_run(db, run)


@router.get("/{run_id}", response_model=BacktestOut)
def get_backtest(run_id: UUID, db: Session = Depends(get_db)) -> BacktestOut:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run
