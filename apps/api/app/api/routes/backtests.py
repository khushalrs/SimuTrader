from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.backtests import (
    BacktestRun,
    RunDailyEquity,
    RunMetric,
    RunTaxEvent,
)
from app.security import ActorContext, ActorTier, get_current_actor
from app.security.rate_limit import enforce_fixed_window_rate_limit
from app.security.sanitize import sanitize_ascii_printable
from app.services.run_dispatch import dispatch_run
from app.schemas.backtests import (
    BacktestCreate,
    BacktestOut,
    BacktestPreflightOut,
    BacktestPreflightRequest,
    RunCompareMetricRowOut,
    RunCompareOut,
    RunCompareSeriesOut,
    RunFillOut,
    RunNormalizedEquityPointOut,
    RunTaxesOut,
    RunTaxEventOut,
)
from app.settings import get_settings
from app.services.config_validation import validate_and_resolve_config
from app.services.preflight import run_preflight

router = APIRouter(prefix="/backtests", tags=["backtests"])
GLOBAL_PRESET_ACTOR_PREFIX = "preset:global:"
MAX_COMPARE_RUNS = 5
DEFAULT_COMPARE_MAX_POINTS = 300
MAX_COMPARE_MAX_POINTS = 2000


def _sanitize_user_string(value: str | None, *, max_len: int = 255) -> str | None:
    return sanitize_ascii_printable(value, max_len=max_len)


def _to_backtest_out(run: BacktestRun) -> BacktestOut:
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


def _compare_config_info(run: BacktestRun) -> dict:
    config = getattr(run, "config_snapshot", None) or {}
    strategy = config.get("strategy") or "BUY_AND_HOLD"
    if isinstance(strategy, dict):
        strategy_type = str(strategy.get("type") or "BUY_AND_HOLD").upper()
    else:
        strategy_type = str(strategy).upper()
    backtest = config.get("backtest") or {}
    meta = getattr(run, "metrics_meta", {}) or {}
    return {
        "name": getattr(run, "name", None),
        "strategy_type": strategy_type,
        "tax_regime": str((config.get("tax") or {}).get("regime") or "NONE").upper(),
        "base_currency": str(config.get("base_currency") or "USD").upper(),
        "start_date": meta.get("effective_start_date") or backtest.get("start_date"),
        "end_date": meta.get("effective_end_date") or backtest.get("end_date"),
    }


def _metric_float(metrics, field: str) -> float | None:
    value = getattr(metrics, field, None) if metrics is not None else None
    return None if value is None else float(value)


def _delta_vs_base(metrics, base_metrics) -> dict[str, float | None]:
    fields = (
        "cagr",
        "volatility",
        "sharpe",
        "max_drawdown",
        "gross_return",
        "net_return",
        "fee_drag",
        "tax_drag",
        "borrow_drag",
        "margin_interest_drag",
    )
    deltas: dict[str, float | None] = {}
    for field in fields:
        value = _metric_float(metrics, field)
        base_value = _metric_float(base_metrics, field)
        deltas[field] = None if value is None or base_value is None else value - base_value
    return deltas


def _get_actor_run(run_id: UUID, actor: ActorContext, db: Session) -> BacktestRun:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.actor_key != actor.actor_key and not str(run.actor_key or "").startswith(
        GLOBAL_PRESET_ACTOR_PREFIX
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _normalize_run_ids(run_ids_raw: str | None) -> list[UUID]:
    if not run_ids_raw:
        return []
    values: list[UUID] = []
    seen: set[UUID] = set()
    for token in [part.strip() for part in run_ids_raw.split(",") if part.strip()]:
        try:
            parsed = UUID(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid run_id '{token}' in run_ids.",
            ) from exc
        if parsed not in seen:
            seen.add(parsed)
            values.append(parsed)
    return values


@router.post("/preflight", response_model=BacktestPreflightOut)
def preflight_backtest(
    payload: BacktestPreflightRequest | dict,
    actor: ActorContext = Depends(get_current_actor),
) -> BacktestPreflightOut:
    settings = get_settings()
    preflight_rate_limit = (
        settings.max_market_requests_per_window_user
        if actor.tier == ActorTier.USER
        else settings.max_market_requests_per_window_guest
    )
    enforce_fixed_window_rate_limit(
        key=f"backtest:preflight:{actor.tier.value}:{actor.actor_key}",
        limit=preflight_rate_limit,
        window_seconds=settings.market_request_window_seconds,
        redis_url=settings.redis_cache_url,
        redis_prefix=settings.redis_cache_prefix,
        detail="Too many preflight requests in a short period. Please retry shortly.",
    )
    raw_config = payload.config_snapshot if isinstance(payload, BacktestPreflightRequest) else payload
    if isinstance(raw_config, dict) and "config_snapshot" in raw_config and "universe" not in raw_config:
        nested = raw_config.get("config_snapshot")
        raw_config = nested if isinstance(nested, dict) else raw_config
    return BacktestPreflightOut.model_validate(run_preflight(raw_config))


def _dispatch_run(
    db: Session,
    config: dict,
    actor: ActorContext,
    name: str | None,
    *,
    response: Response,
    idempotency_key: str | None = None,
    reuse_succeeded_run: bool = False,
    data_snapshot_id: str,
    seed: int = 42,
    strategy_id: UUID | None = None,
) -> BacktestOut:
    result = dispatch_run(
        db,
        config,
        actor,
        name,
        idempotency_key=idempotency_key,
        reuse_succeeded_run=reuse_succeeded_run,
        data_snapshot_id=data_snapshot_id,
        seed=seed,
        strategy_id=strategy_id,
    )
    response.status_code = result.status_code
    return _to_backtest_out(result.run)

@router.post("", response_model=BacktestOut, status_code=status.HTTP_201_CREATED)
def create_backtest(
    payload: BacktestCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    reuse_succeeded_run: bool = Header(default=False, alias="X-Reuse-Succeeded-Run"),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    try:
        resolved_config = validate_and_resolve_config(payload.config_snapshot)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _dispatch_run(
        db,
        resolved_config,
        actor,
        payload.name,
        response=response,
        idempotency_key=idempotency_key,
        reuse_succeeded_run=reuse_succeeded_run,
        data_snapshot_id=payload.data_snapshot_id,
        seed=payload.seed,
        strategy_id=payload.strategy_id,
    )


@router.get("", response_model=list[BacktestOut])
def list_backtests(
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[BacktestOut]:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="limit must be 1..200")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="offset must be >= 0")
    query = db.query(BacktestRun).filter(BacktestRun.actor_key == actor.actor_key)
    if status_filter:
        query = query.filter(BacktestRun.status == str(status_filter).upper())
    runs = query.order_by(BacktestRun.created_at.desc()).offset(offset).limit(limit).all()
    return [_to_backtest_out(run) for run in runs]


@router.get("/{run_id}/trades", response_model=list[RunFillOut])
def get_backtest_trades(
    run_id: UUID,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=5000),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[RunFillOut]:
    from app.api.routes.runs import get_run_fills

    if not isinstance(limit, int):
        limit = int(getattr(limit, "default", 200))
    if not isinstance(offset, int):
        offset = int(getattr(offset, "default", 0))
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be 1..1000",
        )
    if offset < 0 or offset > 5000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be 0..5000",
        )

    return get_run_fills(
        run_id=run_id,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        actor=actor,
        db=db,
    )


@router.get("/{run_id}/taxes", response_model=RunTaxesOut)
def get_backtest_taxes(
    run_id: UUID,
    start: date | None = None,
    end: date | None = None,
    limit: int = 1000,
    offset: int = 0,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunTaxesOut:
    _get_actor_run(run_id, actor, db)
    if limit < 1 or limit > 5000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="limit must be 1..5000")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="offset must be >= 0")
    if start and end and end < start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end must be >= start")

    def _tax_query():
        q = db.query(RunTaxEvent).filter(RunTaxEvent.run_id == run_id)
        if start:
            q = q.filter(RunTaxEvent.date >= start)
        if end:
            q = q.filter(RunTaxEvent.date <= end)
        return q

    event_count = (
        _tax_query().with_entities(func.count(RunTaxEvent.tax_event_id)).scalar() or 0
    )
    total_realized, total_tax_due = _tax_query().with_entities(
        func.coalesce(func.sum(RunTaxEvent.realized_pnl_base), 0.0),
        func.coalesce(func.sum(RunTaxEvent.tax_due_base), 0.0),
    ).first()
    bucket_rows = (
        _tax_query().with_entities(
            RunTaxEvent.bucket,
            func.coalesce(func.sum(RunTaxEvent.tax_due_base), 0.0),
        )
        .group_by(RunTaxEvent.bucket)
        .all()
    )
    by_bucket = {
        str(bucket or "UNKNOWN"): float(tax_due or 0.0)
        for bucket, tax_due in bucket_rows
    }

    paged = (
        _tax_query().order_by(RunTaxEvent.date.asc(), RunTaxEvent.tax_event_id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    events = [
        RunTaxEventOut(
            date=row.date,
            symbol=row.symbol,
            quantity=row.quantity,
            realized_pnl_base=row.realized_pnl_base,
            holding_period_days=row.holding_period_days,
            bucket=row.bucket,
            tax_rate=row.tax_rate,
            tax_due_base=row.tax_due_base,
            meta=row.meta or {},
        )
        for row in paged
    ]

    return RunTaxesOut(
        run_id=run_id,
        event_count=int(event_count),
        total_realized_pnl_base=float(total_realized or 0.0),
        total_tax_due_base=float(total_tax_due or 0.0),
        by_bucket_tax_due_base=by_bucket,
        events=events,
    )


@router.get("/{run_id}/compare", response_model=RunCompareOut)
def compare_backtests(
    run_id: UUID,
    run_ids: str | None = None,
    start: date | None = None,
    end: date | None = None,
    max_points: int = DEFAULT_COMPARE_MAX_POINTS,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunCompareOut:
    if start and end and end < start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="end must be >= start")
    if max_points < 10 or max_points > MAX_COMPARE_MAX_POINTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"max_points must be 10..{MAX_COMPARE_MAX_POINTS}",
        )
    _get_actor_run(run_id, actor, db)
    compare_ids = [run_id]
    for parsed in _normalize_run_ids(run_ids):
        if parsed not in compare_ids:
            compare_ids.append(parsed)
    if len(compare_ids) > MAX_COMPARE_RUNS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"compare supports at most {MAX_COMPARE_RUNS} runs including base run.",
        )

    authorized_runs: list[BacktestRun] = []
    for rid in compare_ids:
        authorized_runs.append(_get_actor_run(rid, actor, db))

    metric_rows: list[RunCompareMetricRowOut] = []
    equity_series: list[RunCompareSeriesOut] = []

    metrics_by_run: dict[UUID, RunMetric | None] = {}
    for run_row in authorized_runs:
        metrics = db.query(RunMetric).filter(RunMetric.run_id == run_row.run_id).first()
        metrics_by_run[run_row.run_id] = metrics
        setattr(run_row, "metrics_meta", getattr(metrics, "meta", {}) if metrics else {})

    base_metrics = metrics_by_run.get(run_id)
    for run_row in authorized_runs:
        metrics = metrics_by_run.get(run_row.run_id)
        info = _compare_config_info(run_row)
        metric_rows.append(
            RunCompareMetricRowOut(
                run_id=run_row.run_id,
                name=info["name"],
                strategy_type=info["strategy_type"],
                tax_regime=info["tax_regime"],
                base_currency=info["base_currency"],
                start_date=info["start_date"],
                end_date=info["end_date"],
                cagr=metrics.cagr if metrics else None,
                volatility=metrics.volatility if metrics else None,
                sharpe=metrics.sharpe if metrics else None,
                max_drawdown=metrics.max_drawdown if metrics else None,
                gross_return=metrics.gross_return if metrics else None,
                net_return=metrics.net_return if metrics else None,
                fee_drag=metrics.fee_drag if metrics else None,
                tax_drag=metrics.tax_drag if metrics else None,
                borrow_drag=metrics.borrow_drag if metrics else None,
                margin_interest_drag=metrics.margin_interest_drag if metrics else None,
                delta_vs_base=_delta_vs_base(metrics, base_metrics),
            )
        )

        rows_query = db.query(RunDailyEquity).filter(RunDailyEquity.run_id == run_row.run_id)
        if start:
            rows_query = rows_query.filter(RunDailyEquity.date >= start)
        if end:
            rows_query = rows_query.filter(RunDailyEquity.date <= end)
        rows = rows_query.order_by(RunDailyEquity.date.asc()).limit(max_points).all()
        points: list[RunNormalizedEquityPointOut] = []
        base_equity = None
        for row in rows:
            value = float(row.equity_base or 0.0)
            if base_equity is None and abs(value) > 1e-12:
                base_equity = value
            normalized = value / base_equity if base_equity else 0.0
            points.append(RunNormalizedEquityPointOut(date=row.date, value=normalized))
        equity_series.append(RunCompareSeriesOut(run_id=run_row.run_id, points=points))

    return RunCompareOut(
        base_run_id=run_id,
        run_ids=compare_ids,
        metric_rows=metric_rows,
        equity_series=equity_series,
    )


@router.get("/{run_id}", response_model=BacktestOut)
def get_backtest(
    run_id: UUID,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    run = (
        db.query(BacktestRun)
        .filter(BacktestRun.run_id == run_id, BacktestRun.actor_key == actor.actor_key)
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _to_backtest_out(run)
