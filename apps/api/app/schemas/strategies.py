from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    config: Dict[str, Any]


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    config: Dict[str, Any]
