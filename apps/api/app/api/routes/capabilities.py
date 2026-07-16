from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.capabilities import get_capabilities


router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
def capabilities() -> dict[str, dict[str, Any]]:
    return get_capabilities()
