from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StrategyParamTypeOut(BaseModel):
    type: Literal["integer", "number", "string", "object"]
    description: str | None = None
    min: float | None = None
    max: float | None = None
    exclusive_min: float | None = None
    enum: list[str] | None = None
    value_type: Literal["number"] | None = None
    value_min: float | None = None
    value_max: float | None = None
    value_exclusive_min: float | None = None


class StrategySchemaOut(BaseModel):
    required_params: list[str] = Field(default_factory=list)
    optional_params: list[str] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)
    param_types: dict[str, StrategyParamTypeOut] = Field(default_factory=dict)
    description: str
    supported_allocation_modes: list[str] = Field(default_factory=list)
    supported_asset_classes: list[str] = Field(default_factory=list)
    supports_shorting: bool
    supports_margin: bool
    supports_mixed_currency: bool
