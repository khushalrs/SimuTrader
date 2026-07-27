from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResearchRangeSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    min_value: float = Field(alias="min")
    max_value: float = Field(alias="max")
    step: float | None = None
    count: int | None = Field(default=None, ge=2, le=1000)
    linspace: int | None = Field(default=None, ge=2, le=1000)

    @model_validator(mode="after")
    def validate_generator(self):
        count_values = [
            self.step is not None,
            self.count is not None,
            self.linspace is not None,
        ]
        if sum(count_values) != 1:
            raise ValueError("range values require exactly one of step, count, or linspace")
        if self.max_value < self.min_value:
            raise ValueError("range max must be >= min")
        if self.step is not None and self.step <= 0.0:
            raise ValueError("range step must be > 0")
        return self


class ResearchGridDimensionIn(BaseModel):
    path: str = Field(min_length=1, max_length=255)
    values: list[Any] | ResearchRangeSpec


class ResearchSweepSpecIn(BaseModel):
    grid: list[ResearchGridDimensionIn] = Field(min_length=1, max_length=20)


class ResearchJobCreate(BaseModel):
    type: Literal["SWEEP"]
    base_run_id: UUID
    spec: ResearchSweepSpecIn


class ResearchJobFailureOut(BaseModel):
    run_id: UUID | None = None
    status: str
    error_code: str | None = None
    error_message_public: str | None = None


class ResearchJobProgressOut(BaseModel):
    n_done: int
    n_total: int
    n_succeeded: int
    n_failed: int
    n_active: int
    n_planned: int
    failures: list[ResearchJobFailureOut] = Field(default_factory=list)


class ResearchJobOut(BaseModel):
    job_id: UUID
    type: str
    base_run_id: UUID
    status: str
    stage: str
    spec: dict[str, Any]
    child_run_ids: list[UUID] = Field(default_factory=list)
    progress: ResearchJobProgressOut
    error_code: str | None = None
    error_message_public: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    finished_at: datetime | None = None


class ResearchResultMetricOut(BaseModel):
    cagr: float | None = None
    volatility: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float | None = None
    turnover: float | None = None
    gross_return: float | None = None
    net_return: float | None = None
    beta: float | None = None
    alpha: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None


class ResearchSweepResultOut(BaseModel):
    params: dict[str, Any]
    run_id: UUID | None = None
    status: str
    metrics: ResearchResultMetricOut | None = None

