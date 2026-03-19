from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.backtest import claim_run, execute_run
from app.db import get_db
from app.models.backtests import BacktestRequestIdempotency, BacktestRun
from app.schemas.backtests import BacktestCreate, BacktestOut
from app.settings import get_settings
from app.services.config_validation import validate_and_resolve_config

router = APIRouter(prefix="/backtests", tags=["backtests"])


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


def _find_idempotent_run(
    db: Session,
    idempotency_key: str,
    now_utc: datetime,
) -> BacktestRun | None:
    row = (
        db.query(BacktestRequestIdempotency)
        .filter(
            BacktestRequestIdempotency.idempotency_key == idempotency_key,
            BacktestRequestIdempotency.expires_at > now_utc,
        )
        .first()
    )
    if not row:
        return None
    return db.query(BacktestRun).filter(BacktestRun.run_id == row.run_id).first()


@router.post("", response_model=BacktestOut, status_code=status.HTTP_201_CREATED)
def create_backtest(
    payload: BacktestCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> BacktestOut:
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    clean_idempotency_key = (idempotency_key or "").strip() or None

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
                BacktestRequestIdempotency.idempotency_key == clean_idempotency_key,
                BacktestRequestIdempotency.expires_at <= now_utc,
            )
            .delete(synchronize_session=False)
        )
        db.commit()

        existing_run = _find_idempotent_run(db, clean_idempotency_key, now_utc)
        if existing_run:
            response.status_code = status.HTTP_202_ACCEPTED
            return _to_backtest_out(existing_run)

    run = BacktestRun(
        strategy_id=payload.strategy_id,
        name=payload.name,
        status="QUEUED",
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
            existing_run = _find_idempotent_run(db, clean_idempotency_key, now_utc)
            if existing_run:
                response.status_code = status.HTTP_202_ACCEPTED
                return _to_backtest_out(existing_run)
        raise

    db.refresh(run)

    if settings.backtest_exec_mode == "async":
        from app.worker import execute_run_task

        execute_run_task.delay(str(run.run_id))
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
        return _to_backtest_out(run)

    return _to_backtest_out(execute_run(db, claimed_run))


@router.get("/{run_id}", response_model=BacktestOut)
def get_backtest(run_id: UUID, db: Session = Depends(get_db)) -> BacktestOut:
    run = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _to_backtest_out(run)
