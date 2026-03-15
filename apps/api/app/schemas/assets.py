from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    symbol: str
    name: Optional[str] = None
    asset_class: str
    currency: str
    exchange: Optional[str] = None
    is_active: bool
    data_source: str
    meta: Dict[str, Any]


class AssetCoverageOut(BaseModel):
    symbol: str
    first_date: str
    last_date: str
    rows: int


class AssetDetailOut(AssetOut):
    coverage: AssetCoverageOut | None = None
