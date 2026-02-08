from __future__ import annotations

from datetime import date, datetime
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


class RunDailyEquityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    date: date
    equity_base: float
    cash_base: float
    gross_exposure_base: float
    net_exposure_base: float
    drawdown: float
    fees_cum_base: float
    taxes_cum_base: float
    borrow_fees_cum_base: float
    margin_interest_cum_base: float
    equity_by_currency: Dict[str, float] = Field(default_factory=dict)
    cash_by_currency: Dict[str, float] = Field(default_factory=dict)
    fees_cum_by_currency: Dict[str, float] = Field(default_factory=dict)


class RunMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    cagr: Optional[float] = None
    volatility: Optional[float] = None
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    max_drawdown: Optional[float] = None
    turnover: Optional[float] = None
    gross_return: Optional[float] = None
    net_return: Optional[float] = None
    fee_drag: Optional[float] = None
    tax_drag: Optional[float] = None
    borrow_drag: Optional[float] = None
    margin_interest_drag: Optional[float] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
