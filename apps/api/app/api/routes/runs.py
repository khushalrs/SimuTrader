from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunFill,
    RunMetric,
    RunOrder,
    RunPosition,
)
from app.schemas.backtests import (
    BacktestOut,
    RunCostsSummaryOut,
    RunDailyEquityOut,
    RunFillOut,
    RunMetricOut,
    RunPositionOut,
)

router = APIRouter(prefix="/runs", tags=["runs"])


def _to_backtest_out(run: BacktestRun) -> BacktestOut:
    # Explicitly map only safe/public run fields.
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


@router.get("/{run_id}", response_model=BacktestOut)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> BacktestOut:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _to_backtest_out(run)


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


@router.get("/{run_id}/positions", response_model=list[RunPositionOut])
def get_run_positions(
    run_id: UUID,
    date_value: date | None = Query(default=None, alias="date"),
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[RunPositionOut]:
    run = db.query(BacktestRun.run_id).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be > 0",
        )

    target_date = date_value
    if target_date is None:
        target_date = (
            db.query(func.max(RunPosition.date))
            .filter(RunPosition.run_id == run_id)
            .scalar()
        )
        if target_date is None:
            return []

    rows = (
        db.query(RunPosition)
        .filter(RunPosition.run_id == run_id, RunPosition.date == target_date)
        .order_by(RunPosition.market_value_base.desc(), RunPosition.symbol.asc())
        .limit(limit)
        .all()
    )
    if not rows:
        return []

    equity_row = (
        db.query(RunDailyEquity.equity_base)
        .filter(RunDailyEquity.run_id == run_id, RunDailyEquity.date == target_date)
        .first()
    )
    equity_base = equity_row[0] if equity_row else None

    results: list[RunPositionOut] = []
    for row in rows:
        weight = None
        if equity_base and abs(equity_base) > 1e-12:
            weight = row.market_value_base / equity_base
        results.append(
            RunPositionOut(
                date=row.date,
                symbol=row.symbol,
                qty=row.qty,
                avg_cost_native=row.avg_cost_native,
                market_value_base=row.market_value_base,
                unrealized_pnl_base=row.unrealized_pnl_base,
                weight=weight,
            )
        )
    return results


@router.get("/{run_id}/fills", response_model=list[RunFillOut])
def get_run_fills(
    run_id: UUID,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> list[RunFillOut]:
    run = db.query(BacktestRun.run_id).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if start and end and end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be >= start",
        )

    rows = db.query(RunFill).filter(RunFill.run_id == run_id)
    if start:
        rows = rows.filter(RunFill.date >= start)
    if end:
        rows = rows.filter(RunFill.date <= end)
    fills = rows.order_by(RunFill.date.asc()).all()

    if not fills:
        return []

    order_ids = {fill.order_id for fill in fills if fill.order_id is not None}
    side_lookup: dict[UUID, str] = {}
    if order_ids:
        side_rows = (
            db.query(RunOrder.order_id, RunOrder.side)
            .filter(RunOrder.order_id.in_(order_ids))
            .all()
        )
        side_lookup = {order_id: side for order_id, side in side_rows}

    return [
        RunFillOut(
            date=fill.date,
            symbol=fill.symbol,
            side=side_lookup.get(fill.order_id) if fill.order_id else None,
            qty=fill.qty,
            price=fill.price_native,
            notional=fill.notional_native,
            commission=fill.commission_native,
            slippage=fill.slippage_native,
        )
        for fill in fills
    ]


@router.get("/{run_id}/costs_summary", response_model=RunCostsSummaryOut)
def get_run_costs_summary(
    run_id: UUID,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> RunCostsSummaryOut:
    run = db.query(BacktestRun.run_id).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if start and end and end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be >= start",
        )

    rows = db.query(RunFill).filter(RunFill.run_id == run_id)
    if start:
        rows = rows.filter(RunFill.date >= start)
    if end:
        rows = rows.filter(RunFill.date <= end)
    fills = rows.all()
    commissions = sum(fill.commission_native for fill in fills)
    slippage = sum(fill.slippage_native for fill in fills)
    return RunCostsSummaryOut(
        commissions=commissions,
        slippage=slippage,
        total_costs=commissions + slippage,
    )
