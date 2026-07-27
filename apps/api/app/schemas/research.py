from __future__ import annotations

from datetime import date, datetime
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


ResearchOptimizeMetric = Literal[
    "sharpe",
    "cagr",
    "sortino",
    "max_drawdown",
    "volatility",
    "net_return",
    "alpha",
    "tracking_error",
    "information_ratio",
]


class ResearchSweepSpecIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid: list[ResearchGridDimensionIn] = Field(min_length=1, max_length=20)
    optimize_metric: ResearchOptimizeMetric = "sharpe"


class ResearchIsOosSpecIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    split_pct: float = Field(default=0.7, gt=0.0, lt=1.0)
    grid: list[ResearchGridDimensionIn] | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )
    optimize_metric: ResearchOptimizeMetric = "sharpe"


class ResearchWalkForwardSpecIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    train_len: int = Field(gt=0)
    test_len: int = Field(gt=0)
    step: int | None = Field(default=None, gt=0)
    mode: Literal["anchored", "rolling"] = "rolling"
    optimize_metric: ResearchOptimizeMetric = "sharpe"
    grid: list[ResearchGridDimensionIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_step(self):
        if self.step is None:
            self.step = self.test_len
        if self.step != self.test_len:
            raise ValueError(
                "walk-forward step must equal test_len so OOS segments do not overlap or gap"
            )
        return self


class ResearchJobCreate(BaseModel):
    type: Literal["SWEEP", "IS_OOS", "WALK_FORWARD"]
    base_run_id: UUID
    spec: ResearchSweepSpecIn | ResearchIsOosSpecIn | ResearchWalkForwardSpecIn

    @model_validator(mode="after")
    def validate_spec_for_type(self):
        expected = {
            "SWEEP": ResearchSweepSpecIn,
            "IS_OOS": ResearchIsOosSpecIn,
            "WALK_FORWARD": ResearchWalkForwardSpecIn,
        }[self.type]
        if not isinstance(self.spec, expected):
            raise ValueError(f"{self.type} requires a matching research spec")
        return self


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
    role: str = "SWEEP"
    segment_index: int | None = None
    is_selected: bool = False
    start_date: date | None = None
    evaluation_start_date: date | None = None
    end_date: date | None = None
    metrics: ResearchResultMetricOut | None = None
    degradation: dict[str, float | None] | None = None


class ResearchEquityPointOut(BaseModel):
    date: date
    equity_base: float
    return_: float = Field(alias="return")


class ResearchWalkForwardEquityOut(BaseModel):
    job_id: UUID
    stitching_method: Literal["segment_return_rebase"]
    points: list[ResearchEquityPointOut]
    metrics: ResearchResultMetricOut | None = None
    is_return: float | None = None
    oos_return: float | None = None
    walk_forward_efficiency: float | None = None


class ResearchRobustnessOut(BaseModel):
    job_id: UUID
    summary_version: int
    optimize_metric: str
    sensitivity: dict[str, Any] | None = None
    is_oos_degradation: dict[str, Any] | None = None
    walk_forward_efficiency: float | None = None
    monte_carlo_tail: dict[str, Any] | None = None
    deflated_sharpe: dict[str, Any]
    computed_at: datetime
