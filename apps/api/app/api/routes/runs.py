import csv
import io
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
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
    RunTaxEvent,
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
    RunExplainOut,
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


def _strategy_type(config: dict | None) -> str:
    strategy = (config or {}).get("strategy") or "BUY_AND_HOLD"
    if isinstance(strategy, dict):
        return str(strategy.get("type") or "BUY_AND_HOLD").upper()
    return str(strategy).upper()


def _tax_regime(config: dict | None) -> str:
    return str(((config or {}).get("tax") or {}).get("regime") or "NONE").upper()


def _metric_value(metrics: RunMetric | None, field: str) -> float | None:
    value = getattr(metrics, field, None) if metrics is not None else None
    return None if value is None else float(value)


def _latest_equity(run_id: UUID, db: Session) -> RunDailyEquity | None:
    return (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
        .order_by(RunDailyEquity.date.desc())
        .first()
    )


def _run_explanation(run: BacktestRun, db: Session) -> RunExplainOut:
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run.run_id).first()
    if not metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics not found")

    gross_return = _metric_value(metrics, "gross_return")
    net_return = _metric_value(metrics, "net_return")
    total_drag = (
        net_return - gross_return
        if gross_return is not None and net_return is not None
        else None
    )
    drag_breakdown = {
        "fees": -abs(float(metrics.fee_drag or 0.0)),
        "taxes": -abs(float(metrics.tax_drag or 0.0)),
        "borrow": -abs(float(metrics.borrow_drag or 0.0)),
        "margin_interest": -abs(float(metrics.margin_interest_drag or 0.0)),
    }
    dominant_drag = max(drag_breakdown, key=lambda key: abs(drag_breakdown[key]))
    if abs(drag_breakdown[dominant_drag]) <= 1e-12:
        dominant_drag = None

    trade_count = (
        db.query(func.count(RunFill.fill_id))
        .filter(RunFill.run_id == run.run_id)
        .scalar()
        or 0
    )
    tax_regime = _tax_regime(run.config_snapshot)

    def pct(value: float | None) -> str:
        return "unknown" if value is None else f"{value * 100:.0f}%"

    if dominant_drag:
        summary = (
            f"The run earned {pct(gross_return)} gross and {pct(net_return)} net. "
            f"{dominant_drag.replace('_', ' ').capitalize()} were the largest drag."
        )
    else:
        summary = f"The run earned {pct(gross_return)} gross and {pct(net_return)} net."

    return RunExplainOut(
        gross_return=gross_return,
        net_return=net_return,
        total_drag=total_drag,
        drag_breakdown=drag_breakdown,
        dominant_drag=dominant_drag,
        trade_count=int(trade_count),
        turnover=_metric_value(metrics, "turnover"),
        tax_regime=tax_regime,
        summary=summary,
    )


def _csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _tax_summary(run_id: UUID, db: Session) -> dict:
    rows = db.query(RunTaxEvent).filter(RunTaxEvent.run_id == run_id).all()
    return {
        "event_count": len(rows),
        "total_realized_pnl_base": sum(float(row.realized_pnl_base or 0.0) for row in rows),
        "total_tax_due_base": sum(float(row.tax_due_base or 0.0) for row in rows),
    }


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
    
    # Generate dynamic natural language explanation based on drags
    net_ret = metrics.net_return or 0.0
    fee_drag = metrics.fee_drag or 0.0
    tax_drag = metrics.tax_drag or 0.0
    borrow_drag = metrics.borrow_drag or 0.0
    margin_drag = metrics.margin_interest_drag or 0.0

    drags = [
        ("transaction fees", fee_drag),
        ("tax liabilities", tax_drag),
        ("short borrow fees", borrow_drag),
        ("margin financing interest charges", margin_drag),
    ]
    largest_name, largest_val = max(drags, key=lambda x: x[1])

    if net_ret > 0:
        performance = f"positive net return of +{net_ret*100:.1f}%"
    else:
        performance = f"net loss of {net_ret*100:.1f}%"

    if largest_val > 0.001:
        explanation_str = f"Your {performance} was achieved after overcoming a gross-to-net drag, led primarily by {largest_name} (-{largest_val*100:.1f}%)."
    else:
        explanation_str = f"Your strategy achieved a {performance} with minimal cost drag from transaction fees, taxes, or financing friction."

    out = RunMetricOut.model_validate(metrics)
    out.explanation = explanation_str
    return out


@router.get("/{run_id}/explain", response_model=RunExplainOut)
def explain_run(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunExplainOut:
    run = _get_actor_run(run_id, actor, db)
    if not _is_terminal_status(run.status):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run is not complete")
    return _run_explanation(run, db)


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
    offset: int = Query(default=0, ge=0, le=5000),
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

    fill_rows = db.query(
        func.coalesce(func.sum(RunFill.commission_native), 0.0),
        func.coalesce(func.sum(RunFill.slippage_native), 0.0),
    ).filter(RunFill.run_id == run_id)
    if start:
        fill_rows = fill_rows.filter(RunFill.date >= start)
    if end:
        fill_rows = fill_rows.filter(RunFill.date <= end)
    commissions, slippage = fill_rows.first()

    equity_rows = db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run_id)
    if start:
        equity_rows = equity_rows.filter(RunDailyEquity.date >= start)
    if end:
        equity_rows = equity_rows.filter(RunDailyEquity.date <= end)
    latest_equity = equity_rows.order_by(RunDailyEquity.date.desc()).first()
    total_costs = float(latest_equity.fees_cum_base if latest_equity else 0.0)
    return RunCostsSummaryOut(
        commissions=float(commissions or 0.0),
        slippage=float(slippage or 0.0),
        total_costs=total_costs,
    )


@router.get("/{run_id}/export/equity.csv")
def export_run_equity_csv(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _get_actor_run(run_id, actor, db)
    rows = (
        db.query(RunDailyEquity)
        .filter(RunDailyEquity.run_id == run_id)
        .order_by(RunDailyEquity.date.asc())
        .all()
    )
    return _csv_response(
        "equity.csv",
        [
            "date",
            "equity_base",
            "cash_base",
            "gross_exposure_base",
            "net_exposure_base",
            "drawdown",
            "fees_cum_base",
            "taxes_cum_base",
            "borrow_fees_cum_base",
            "margin_interest_cum_base",
        ],
        [
            [
                row.date,
                row.equity_base,
                row.cash_base,
                row.gross_exposure_base,
                row.net_exposure_base,
                row.drawdown,
                row.fees_cum_base,
                row.taxes_cum_base,
                row.borrow_fees_cum_base,
                row.margin_interest_cum_base,
            ]
            for row in rows
        ],
    )


@router.get("/{run_id}/export/fills.csv")
def export_run_fills_csv(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _get_actor_run(run_id, actor, db)
    fills = (
        db.query(RunFill)
        .filter(RunFill.run_id == run_id)
        .order_by(RunFill.date.asc())
        .all()
    )
    order_ids = {fill.order_id for fill in fills if fill.order_id is not None}
    side_lookup: dict[UUID, str] = {}
    if order_ids:
        side_rows = (
            db.query(RunOrder.order_id, RunOrder.side)
            .filter(RunOrder.order_id.in_(order_ids))
            .all()
        )
        side_lookup = {order_id: side for order_id, side in side_rows}
    return _csv_response(
        "fills.csv",
        ["date", "symbol", "side", "qty", "price", "notional", "commission", "slippage"],
        [
            [
                row.date,
                row.symbol,
                side_lookup.get(row.order_id) if row.order_id else None,
                row.qty,
                row.price_native,
                row.notional_native,
                row.commission_native,
                row.slippage_native,
            ]
            for row in fills
        ],
    )


@router.get("/{run_id}/export/taxes.csv")
def export_run_taxes_csv(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    _get_actor_run(run_id, actor, db)
    rows = (
        db.query(RunTaxEvent)
        .filter(RunTaxEvent.run_id == run_id)
        .order_by(RunTaxEvent.date.asc(), RunTaxEvent.tax_event_id.asc())
        .all()
    )
    return _csv_response(
        "taxes.csv",
        [
            "date",
            "symbol",
            "quantity",
            "realized_pnl_base",
            "holding_period_days",
            "bucket",
            "tax_rate",
            "tax_due_base",
        ],
        [
            [
                row.date,
                row.symbol,
                row.quantity,
                row.realized_pnl_base,
                row.holding_period_days,
                row.bucket,
                row.tax_rate,
                row.tax_due_base,
            ]
            for row in rows
        ],
    )


@router.get("/{run_id}/report.json")
def get_run_report_json(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> dict:
    run = _get_actor_run(run_id, actor, db)
    metrics = db.query(RunMetric).filter(RunMetric.run_id == run_id).first()
    latest_equity = _latest_equity(run_id, db)
    return {
        "run": _to_backtest_out(run).model_dump(mode="json"),
        "metrics": RunMetricOut.model_validate(metrics).model_dump(mode="json") if metrics else None,
        "explanation": _run_explanation(run, db).model_dump(mode="json") if metrics else None,
        "costs": get_run_costs_summary(run_id=run_id, actor=actor, db=db).model_dump(mode="json"),
        "taxes": _tax_summary(run_id, db),
        "latest_equity": RunDailyEquityOut.model_validate(latest_equity).model_dump(mode="json")
        if latest_equity
        else None,
    }


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
