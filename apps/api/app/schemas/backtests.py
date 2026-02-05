from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BacktestCreate(BaseModel):
    name: Optional[str] = None
    strategy_id: Optional[UUID] = None
    config_snapshot: Dict[str, Any]
    data_snapshot_id: str
    seed: int = Field(default=42, ge=0)


class BacktestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    strategy_id: Optional[UUID] = None
    name: Optional[str] = None
    status: str
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    config_snapshot: Dict[str, Any]
    data_snapshot_id: str
    seed: int
