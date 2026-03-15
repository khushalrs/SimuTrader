from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class MarketBarOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str
    symbol: str
    currency: str
    exchange: str | None = None


class MarketCoverageOut(BaseModel):
    symbol: str
    first_date: str
    last_date: str
    rows: int
    missing_ratio: float | None = None


class MarketSnapshotOut(BaseModel):
    symbol: str
    last_date: str
    last_close: float
    return_1w: float | None = None
    return_1m: float | None = None
    return_3m: float | None = None
    return_1y: float | None = None
    recent_vol_20d: float | None = None
    median_vol_1y: float | None = None
    meta: dict[str, Any] = {}
