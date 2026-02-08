from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.backtests import BacktestRun, RunDailyEquity, RunMetric
from app.schemas.backtests import BacktestOut, RunDailyEquityOut, RunMetricOut

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=BacktestOut)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> BacktestOut:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{run_id}/equity", response_model=list[RunDailyEquityOut])
def get_run_equity(
    run_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> list[RunDailyEquityOut]:
    run = db.query(BacktestRun.run_id).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be >= start_date",
        )
    rows = (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
    )
    if start_date:
        rows = rows.filter(RunDailyEquity.date >= start_date)
    if end_date:
        rows = rows.filter(RunDailyEquity.date <= end_date)
    rows = (
        rows.order_by(RunDailyEquity.date.asc())
        .all()
    )
    return rows


@router.get("/{run_id}/metrics", response_model=RunMetricOut)
def get_run_metrics(run_id: UUID, db: Session = Depends(get_db)) -> RunMetricOut:
    run = db.query(BacktestRun.run_id).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics not found")
    return metrics
