from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.playground.presets import GLOBAL_PRESET_DEFINITIONS
from app.playground.service import enqueue_global_preset_run
from app.schemas.backtests import BacktestOut, PlaygroundPresetOut

router = APIRouter(prefix="/playground", tags=["playground"])


def _preset_description(strategy_type: str) -> str:
    descriptions = {
        "BUY_AND_HOLD": "Long-horizon portfolio compounding with explicit execution costs.",
        "FIXED_WEIGHT_REBALANCE": "Scheduled target-weight rebalancing with financing and risk controls.",
        "DCA": "Incremental cash deployment without rebalancing existing holdings.",
        "MOMENTUM": "Top-k relative-strength rotation with turnover and execution friction.",
        "MEAN_REVERSION": "Counter-trend entries with threshold or holding-period exits.",
    }
    return descriptions.get(strategy_type, "Preconfigured backtest scenario.")


@router.get("/presets", response_model=list[PlaygroundPresetOut])
def list_playground_presets() -> list[PlaygroundPresetOut]:
    presets: list[PlaygroundPresetOut] = []
    for preset_id, definition in GLOBAL_PRESET_DEFINITIONS.items():
        config = definition["config_snapshot"]
        strategy = config.get("strategy") or "BUY_AND_HOLD"
        strategy_type = (
            str(strategy.get("type") or "BUY_AND_HOLD").upper()
            if isinstance(strategy, dict)
            else str(strategy).upper()
        )
        instruments = ((config.get("universe") or {}).get("instruments") or [])
        presets.append(
            PlaygroundPresetOut(
                id=preset_id,
                name=str(definition["name"]),
                description=_preset_description(strategy_type),
                strategy_type=strategy_type,
                base_currency=str(config.get("base_currency") or "USD").upper(),
                symbols=[str(instrument.get("symbol") or "") for instrument in instruments],
                asset_classes=sorted(
                    {
                        str(instrument.get("asset_class") or "UNKNOWN")
                        for instrument in instruments
                    }
                ),
                data_snapshot_id=str(definition["data_snapshot_id"]),
                config_snapshot=config,
            )
        )
    return presets


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
