from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.capabilities import get_capabilities, get_strategy_schemas


router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
def capabilities() -> dict[str, dict[str, Any]]:
    return get_capabilities()


@router.get("/strategy-schemas")
def strategy_schemas() -> dict[str, dict[str, Any]]:
    return get_strategy_schemas()
