from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.capabilities import ConfigPathOut, StrategySchemaOut
from app.services.capabilities import get_capabilities, get_strategy_schemas
from app.services.config_paths import get_config_paths


router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
def capabilities() -> dict[str, dict[str, Any]]:
    return get_capabilities()


@router.get(
    "/strategy-schemas",
    response_model=dict[str, StrategySchemaOut],
    response_model_exclude_none=True,
)
def strategy_schemas() -> dict[str, dict[str, Any]]:
    return get_strategy_schemas()


@router.get(
    "/capabilities/config-paths",
    response_model=list[ConfigPathOut],
    response_model_exclude_none=True,
)
def config_paths(
    strategy: str | None = Query(default=None),
    sweepable: bool | None = Query(default=None),
) -> list[dict[str, Any]]:
    try:
        return get_config_paths(strategy=strategy, sweepable=sweepable)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
