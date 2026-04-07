from datetime import date, datetime, timedelta, timezone
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backtest import claim_run, execute_run
from app.db import get_db
from app.models.backtests import (
    BacktestRequestIdempotency,
    BacktestRun,
    RunDailyEquity,
    RunMetric,
    RunTaxEvent,
)
from app.security import ActorContext, ActorTier, get_current_actor
from app.services.redis_store import refresh_run_cache
from app.schemas.backtests import (
    BacktestCreate,
    BacktestOut,
    RunCompareMetricRowOut,
    RunCompareOut,
    RunCompareSeriesOut,
    RunNormalizedEquityPointOut,
    RunTaxesOut,
    RunTaxEventOut,
)
from app.settings import get_settings
from app.services.config_validation import validate_and_resolve_config

router = APIRouter(prefix="/backtests", tags=["backtests"])
logger = logging.getLogger(__name__)
GLOBAL_PRESET_ACTOR_PREFIX = "preset:global:"


def _sanitize_user_string(value: str | None, *, max_len: int = 255) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in str(value) if ord(ch) >= 32 or ch in "\t\r\n").strip()
    if not cleaned:
        return None
    return cleaned[:max_len]


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


def _find_idempotent_run(
    db: Session,
    actor_key: str,
    idempotency_key: str,
    now_utc: datetime,
) -> BacktestRun | None:
    row = (
        db.query(BacktestRequestIdempotency)
        .filter(
            BacktestRequestIdempotency.actor_key == actor_key,
            BacktestRequestIdempotency.idempotency_key == idempotency_key,
            BacktestRequestIdempotency.expires_at > now_utc,
        )
        .first()
    )
    if not row:
        return None
    return db.query(BacktestRun).filter(BacktestRun.run_id == row.run_id).first()


def _find_reusable_run(
    db: Session,
    actor_key: str,
    resolved_config: dict,
    data_snapshot_id: str,
    seed: int,
) -> BacktestRun | None:
    return (
        db.query(BacktestRun)
        .filter(
            BacktestRun.actor_key == actor_key,
            BacktestRun.config_snapshot == resolved_config,
            BacktestRun.data_snapshot_id == data_snapshot_id,
            BacktestRun.seed == seed,
            BacktestRun.status.in_(("QUEUED", "RUNNING", "SUCCEEDED")),
        )
        .order_by(BacktestRun.created_at.desc())
        .first()
    )


def _mark_stale_queued_runs(db: Session, stale_after_seconds: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
    stale_runs = (
        db.query(BacktestRun)
        .filter(
            BacktestRun.status == "QUEUED",
            BacktestRun.started_at.is_(None),
            BacktestRun.created_at < cutoff,
        )
        .all()
    )
    for stale_run in stale_runs:
        stale_run.status = "ENQUEUE_FAILED"
        stale_run.error_code = "E_ENQUEUE_STALE"
        stale_run.error_message_public = (
            "This run could not be queued in time. Please retry."
        )
        stale_run.error_retryable = True
        stale_run.error_id = str(uuid4())
        stale_run.finished_at = datetime.now(timezone.utc)
    if stale_runs:
        db.commit()
        for stale_run in stale_runs:
            refresh_run_cache(stale_run)
    return len(stale_runs)


@router.post("", response_model=BacktestOut, status_code=status.HTTP_201_CREATED)
def create_backtest(
    payload: BacktestCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    reuse_succeeded_run: bool = Header(default=False, alias="X-Reuse-Succeeded-Run"),
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BacktestOut:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    clean_idempotency_key = (idempotency_key or "").strip() or None
    payload.name = _sanitize_user_string(payload.name, max_len=255)
    clean_data_snapshot_id = _sanitize_user_string(payload.data_snapshot_id, max_len=128)
    if not clean_data_snapshot_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="data_snapshot_id must be a non-empty string.",
        )
    payload.data_snapshot_id = clean_data_snapshot_id
    _mark_stale_queued_runs(db, stale_after_seconds=settings.stale_queued_timeout_seconds)

    try:
        resolved_config = validate_and_resolve_config(payload.config_snapshot)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if clean_idempotency_key:
        # Allow key reuse after dedupe expiry.
        (
            db.query(BacktestRequestIdempotency)
            .filter(
                BacktestRequestIdempotency.actor_key == actor.actor_key,
                BacktestRequestIdempotency.idempotency_key == clean_idempotency_key,
                BacktestRequestIdempotency.expires_at <= now_utc,
            )
            .delete(synchronize_session=False)
        )
        db.commit()

        existing_run = _find_idempotent_run(
            db, actor.actor_key, clean_idempotency_key, now_utc
        )
        if existing_run:
            if existing_run.status in {"QUEUED", "RUNNING"}:
                response.status_code = status.HTTP_202_ACCEPTED
                return _to_backtest_out(existing_run)
            (
                db.query(BacktestRequestIdempotency)
                .filter(
                    BacktestRequestIdempotency.actor_key == actor.actor_key,
                    BacktestRequestIdempotency.idempotency_key == clean_idempotency_key,
                )
                .delete(synchronize_session=False)
            )
            db.commit()

    if reuse_succeeded_run:
        reusable = _find_reusable_run(
            db=db,
            actor_key=actor.actor_key,
            resolved_config=resolved_config,
            data_snapshot_id=payload.data_snapshot_id,
            seed=payload.seed,
        )
        if reusable:
            if reusable.status in {"QUEUED", "RUNNING"}:
                response.status_code = status.HTTP_202_ACCEPTED
            else:
                response.status_code = status.HTTP_200_OK
            return _to_backtest_out(reusable)

    max_active_runs = (
        settings.max_active_runs_per_user
        if actor.tier == ActorTier.USER
        else settings.max_active_runs_per_guest
    )
    active_run_count = (
        db.query(func.count(BacktestRun.run_id))
        .filter(
            BacktestRun.actor_key == actor.actor_key,
            BacktestRun.status.in_(("QUEUED", "RUNNING")),
        )
        .scalar()
        or 0
    )
    if active_run_count >= max_active_runs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many active runs. Please wait for current runs to finish.",
        )

    rate_limit_count = (
        settings.max_backtest_creates_per_window_user
        if actor.tier == ActorTier.USER
        else settings.max_backtest_creates_per_window_guest
    )
    window_start = now_utc - timedelta(seconds=settings.backtest_create_window_seconds)
    recent_create_count = (
        db.query(func.count(BacktestRun.run_id))
        .filter(
            BacktestRun.actor_key == actor.actor_key,
            BacktestRun.created_at >= window_start,
        )
        .scalar()
        or 0
    )
    if recent_create_count >= rate_limit_count:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many backtest creations in a short period. Please retry shortly.",
        )

    run = BacktestRun(
        strategy_id=payload.strategy_id,
        name=payload.name,
        status="QUEUED",
        actor_tier=actor.tier.value,
        actor_key=actor.actor_key,
        config_snapshot=resolved_config,
        data_snapshot_id=payload.data_snapshot_id,
        seed=payload.seed,
    )
    db.add(run)
    db.flush()

    if clean_idempotency_key:
        dedupe_expires_at = now_utc + timedelta(
            seconds=settings.backtest_idempotency_window_seconds
        )
        db.add(
            BacktestRequestIdempotency(
                actor_key=actor.actor_key,
                idempotency_key=clean_idempotency_key,
                run_id=run.run_id,
                expires_at=dedupe_expires_at,
            )
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if clean_idempotency_key:
            existing_run = _find_idempotent_run(
                db, actor.actor_key, clean_idempotency_key, now_utc
            )
            if existing_run:
                if existing_run.status in {"QUEUED", "RUNNING"}:
                    response.status_code = status.HTTP_202_ACCEPTED
                    return _to_backtest_out(existing_run)
        raise

    db.refresh(run)
    refresh_run_cache(run)

    if settings.backtest_exec_mode == "async":
        from app.worker import execute_run_task

        try:
            task_result = execute_run_task.delay(str(run.run_id))
            run.execution_task_id = task_result.id
            db.commit()
            db.refresh(run)
            refresh_run_cache(run)
        except Exception:
            error_id = str(uuid4())
            logger.exception(
                "Backtest enqueue failed",
                extra={
                    "run_id": str(run.run_id),
                    "error_id": error_id,
                    "actor_key": actor.actor_key,
                },
            )
            run.status = "ENQUEUE_FAILED"
            run.error_code = "E_ENQUEUE_FAILED"
            run.error_message_public = (
                "The simulation could not be queued. Please retry."
            )
            run.error_retryable = True
            run.error_id = error_id
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            refresh_run_cache(run)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return _to_backtest_out(run)
        response.status_code = status.HTTP_202_ACCEPTED
        return _to_backtest_out(run)

    if not settings.is_dev_env and not settings.allow_sync_execution:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Synchronous backtest execution is disabled in non-dev environments. "
                "Use BACKTEST_EXEC_MODE=async."
            ),
        )

    claimed_run = claim_run(db, run.run_id)
    if not claimed_run:
        response.status_code = status.HTTP_202_ACCEPTED
        db.refresh(run)
        refresh_run_cache(run)
        return _to_backtest_out(run)

    return _to_backtest_out(execute_run(db, claimed_run))


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

    query = db.query(RunTaxEvent).filter(RunTaxEvent.run_id == run_id)
    if start:
        query = query.filter(RunTaxEvent.date >= start)
    if end:
        query = query.filter(RunTaxEvent.date <= end)

    all_rows = query.order_by(RunTaxEvent.date.asc(), RunTaxEvent.tax_event_id.asc()).all()
    paged = all_rows[offset : offset + limit]

    by_bucket: dict[str, float] = {}
    total_realized = 0.0
    total_tax_due = 0.0
    for row in all_rows:
        total_realized += float(row.realized_pnl_base or 0.0)
        total_tax_due += float(row.tax_due_base or 0.0)
        bucket = str(row.bucket or "UNKNOWN")
        by_bucket[bucket] = by_bucket.get(bucket, 0.0) + float(row.tax_due_base or 0.0)

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
        event_count=len(all_rows),
        total_realized_pnl_base=total_realized,
        total_tax_due_base=total_tax_due,
        by_bucket_tax_due_base=by_bucket,
        events=events,
    )


@router.get("/{run_id}/compare", response_model=RunCompareOut)
def compare_backtests(
    run_id: UUID,
    run_ids: str | None = None,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> RunCompareOut:
    _get_actor_run(run_id, actor, db)
    compare_ids = [run_id]
    for parsed in _normalize_run_ids(run_ids):
        if parsed not in compare_ids:
            compare_ids.append(parsed)

    authorized_runs: list[BacktestRun] = []
    for rid in compare_ids:
        authorized_runs.append(_get_actor_run(rid, actor, db))

    metric_rows: list[RunCompareMetricRowOut] = []
    equity_series: list[RunCompareSeriesOut] = []

    for run_row in authorized_runs:
        metrics = db.query(RunMetric).filter(RunMetric.run_id == run_row.run_id).first()
        metric_rows.append(
            RunCompareMetricRowOut(
                run_id=run_row.run_id,
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
            )
        )

        rows = (
            db.query(RunDailyEquity)
            .filter(RunDailyEquity.run_id == run_row.run_id)
            .order_by(RunDailyEquity.date.asc())
            .all()
        )
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
