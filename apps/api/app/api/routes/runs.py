from datetime import date, datetime
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
from app.security import ActorContext, get_current_actor
from app.services.redis_store import (
    get_cached_run_status,
    get_cached_top_holdings,
    set_cached_run_status,
    set_cached_run_summary,
    set_cached_top_holdings,
)
from app.schemas.backtests import (
    BacktestOut,
    BacktestStatusOut,
    RunCostsSummaryOut,
    RunDailyEquityOut,
    RunFillOut,
    RunMetricOut,
    RunPositionOut,
)

router = APIRouter(prefix="/runs", tags=["runs"])
GLOBAL_PRESET_ACTOR_PREFIX = "preset:global:"


def _parse_datetime(value: str | None):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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


def _get_actor_run(run_id: UUID, actor: ActorContext, db: Session) -> BacktestRun:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.actor_key != actor.actor_key and not str(run.actor_key or "").startswith(
        GLOBAL_PRESET_ACTOR_PREFIX
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _is_terminal_status(status_value: str) -> bool:
    return status_value in {"SUCCEEDED", "FAILED", "ENQUEUE_FAILED"}


@router.get("/{run_id}", response_model=BacktestOut)
def get_run(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    run = _get_actor_run(run_id, actor, db)
    set_cached_run_summary(run)
    set_cached_run_status(run)
    return _to_backtest_out(run)


@router.get("/{run_id}/status", response_model=BacktestStatusOut)
def get_run_status(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestStatusOut:
    cached = get_cached_run_status(actor.actor_key, str(run_id))
    if cached:
        return BacktestStatusOut(
            run_id=run_id,
            status=cached.status,
            started_at=_parse_datetime(cached.started_at),
            finished_at=_parse_datetime(cached.finished_at),
            error_code=cached.error_code,
            error_message_public=cached.error_message_public,
        )
    run = _get_actor_run(run_id, actor, db)
    set_cached_run_status(run)
    set_cached_run_summary(run)
    return BacktestStatusOut(
        run_id=run.run_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_code=run.error_code,
        error_message_public=run.error_message_public,
    )


@router.get("/{run_id}/equity", response_model=list[RunDailyEquityOut])
def get_run_equity(
    run_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=2000, ge=1, le=10000),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunDailyEquityOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return []
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
        .limit(limit)
        .all()
    )
    return rows


@router.get("/{run_id}/metrics", response_model=RunMetricOut)
def get_run_metrics(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunMetricOut:
    _get_actor_run(run_id, actor, db)
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics not found")
    return metrics


@router.get("/{run_id}/positions", response_model=list[RunPositionOut])
def get_run_positions(
    run_id: UUID,
    date_value: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=50, ge=1, le=200),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunPositionOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return []
    if not isinstance(limit, int):
        limit = int(getattr(limit, "default", 50))

    target_date = date_value
    if hasattr(target_date, "default"):
        target_date = target_date.default
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
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=100000),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunFillOut]:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return []
    if not isinstance(limit, int):
        limit = int(getattr(limit, "default", 200))
    if not isinstance(offset, int):
        offset = int(getattr(offset, "default", 0))
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
    fills = rows.order_by(RunFill.date.asc()).offset(offset).limit(limit).all()

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
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunCostsSummaryOut:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        return RunCostsSummaryOut(commissions=0.0, slippage=0.0, total_costs=0.0)
    if start and end and end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be >= start",
        )

    rows = db.query(
        func.coalesce(func.sum(RunFill.commission_native), 0.0),
        func.coalesce(func.sum(RunFill.slippage_native), 0.0),
    ).filter(RunFill.run_id == run_id)
    if start:
        rows = rows.filter(RunFill.date >= start)
    if end:
        rows = rows.filter(RunFill.date <= end)
    commissions, slippage = rows.first()
    return RunCostsSummaryOut(
        commissions=float(commissions or 0.0),
        slippage=float(slippage or 0.0),
        total_costs=float((commissions or 0.0) + (slippage or 0.0)),
    )


@router.get("/{run_id}/top-holdings", response_model=list[RunPositionOut])
def get_run_top_holdings(
    run_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunPositionOut]:
    cached = get_cached_top_holdings(actor.actor_key, str(run_id), limit)
    if cached is not None:
        return [RunPositionOut.model_validate(item) for item in cached]
    rows = get_run_positions(
        run_id=run_id,
        date_value=None,
        limit=limit,
        actor=actor,
        db=db,
    )
    payload = [row.model_dump(mode="json") for row in rows]
    set_cached_top_holdings(actor.actor_key, str(run_id), limit, payload)
    return rows
