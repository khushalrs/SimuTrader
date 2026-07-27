from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BacktestCreate(BaseModel):
    name: Optional[str] = None
    strategy_id: Optional[UUID] = None
    config_snapshot: Dict[str, Any]
    data_snapshot_id: str
    seed: int = Field(default=42, ge=0)


class RunCloneRequest(BaseModel):
    name: Optional[str] = None


class RunScenarioRequest(BaseModel):
    name: Optional[str] = None
    patch: Dict[str, Any]


class PlaygroundPresetOut(BaseModel):
    id: str
    name: str
    description: str
    strategy_type: str
    base_currency: str
    symbols: list[str] = Field(default_factory=list)
    asset_classes: list[str] = Field(default_factory=list)
    data_snapshot_id: str
    config_snapshot: Dict[str, Any]


class BacktestPreflightRequest(BaseModel):
    config_snapshot: Dict[str, Any]


class BacktestPreflightCoverageOut(BaseModel):
    symbol: str
    currency: Optional[str] = None
    asset_class: Optional[str] = None
    exchange: Optional[str] = None
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    rows: int


class BacktestPreflightRiskFlagOut(BaseModel):
    code: str
    severity: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class BacktestPreflightOut(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data_coverage: list[BacktestPreflightCoverageOut] = Field(default_factory=list)
    required_fx_pairs: list[str] = Field(default_factory=list)
    effective_start_date: Optional[date] = None
    effective_end_date: Optional[date] = None
    strategy_capability: Dict[str, Any] = Field(default_factory=dict)
    estimated_trading_days: Optional[int] = None
    estimated_symbols: int = 0
    estimated_rebalance_count: Optional[int] = None
    risk_flags: list[BacktestPreflightRiskFlagOut] = Field(default_factory=list)


class BacktestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    strategy_id: Optional[UUID] = None
    name: Optional[str] = None
    status: str
    error_code: Optional[str] = None
    error_message_public: Optional[str] = None
    error_retryable: Optional[bool] = None
    error_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    config_snapshot: Dict[str, Any]
    data_snapshot_id: str
    seed: int


class BacktestStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message_public: Optional[str] = None


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
    benchmark_equity_base: Optional[float] = None
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
    beta: Optional[float] = None
    alpha: Optional[float] = None
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    explanation: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class RunPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    symbol: str
    qty: float
    avg_cost_native: float
    market_value_base: float
    unrealized_pnl_base: float
    weight: Optional[float] = None


class RunExposureBreakdownOut(BaseModel):
    long_base: float
    short_base: float
    gross_base: float
    net_base: float


class RunExposurePointOut(RunExposureBreakdownOut):
    date: date
    leverage: Optional[float] = None
    equity_native_by_currency: Dict[str, float] = Field(default_factory=dict)
    exposure_base_by_currency: Dict[str, RunExposureBreakdownOut] = Field(
        default_factory=dict
    )
    by_asset_class: Dict[str, RunExposureBreakdownOut] = Field(default_factory=dict)
    by_country: Dict[str, RunExposureBreakdownOut] = Field(default_factory=dict)


class RunFillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    symbol: str
    side: Optional[str] = None
    qty: float
    price: float
    notional: float
    commission: float
    slippage: float


class RunCostsSummaryOut(BaseModel):
    commissions_native: Dict[str, float] = Field(default_factory=dict)
    slippage_native: Dict[str, float] = Field(default_factory=dict)
    fees_total_base: float
    taxes_total_base: float
    borrow_fees_base: float
    margin_interest_base: float


class RunExplainPeriodOut(BaseModel):
    start_date: date
    end_date: date
    return_value: float


class RunExplainPositionOut(BaseModel):
    date: date
    symbol: str
    qty: float
    market_value_base: float


class RunExplainTradeOut(BaseModel):
    date: date
    symbol: str
    side: Optional[str] = None
    qty: float
    notional_native: float
    currency: Optional[str] = None
    notional_base: Optional[float] = None


class RunExplainTaxEventOut(BaseModel):
    date: date
    symbol: str
    realized_pnl_base: float
    tax_due_base: float
    bucket: str


class RunExplainOut(BaseModel):
    gross_return: Optional[float] = None
    net_return: Optional[float] = None
    total_drag: Optional[float] = None
    drag_breakdown: Dict[str, float] = Field(default_factory=dict)
    dominant_drag: Optional[str] = None
    trade_count: int
    turnover: Optional[float] = None
    tax_regime: str
    headline: str
    summary: str
    best_period: Optional[RunExplainPeriodOut] = None
    worst_period: Optional[RunExplainPeriodOut] = None
    largest_position: Optional[RunExplainPositionOut] = None
    largest_trade: Optional[RunExplainTradeOut] = None
    largest_tax_event: Optional[RunExplainTaxEventOut] = None


class RunTaxEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    symbol: str
    quantity: float
    realized_pnl_base: float
    holding_period_days: int
    bucket: str
    tax_rate: float
    tax_due_base: float
    meta: Dict[str, Any] = Field(default_factory=dict)


class RunTaxesOut(BaseModel):
    run_id: UUID
    event_count: int
    total_realized_pnl_base: float
    total_tax_due_base: float
    by_bucket_tax_due_base: Dict[str, float] = Field(default_factory=dict)
    events: list[RunTaxEventOut] = Field(default_factory=list)


class RunCompareMetricRowOut(BaseModel):
    run_id: UUID
    name: Optional[str] = None
    strategy_type: Optional[str] = None
    tax_regime: Optional[str] = None
    base_currency: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    cagr: Optional[float] = None
    volatility: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    gross_return: Optional[float] = None
    net_return: Optional[float] = None
    fee_drag: Optional[float] = None
    tax_drag: Optional[float] = None
    borrow_drag: Optional[float] = None
    margin_interest_drag: Optional[float] = None
    delta_vs_base: Dict[str, Optional[float]] = Field(default_factory=dict)


class RunNormalizedEquityPointOut(BaseModel):
    date: date
    value: float


class RunCompareSeriesOut(BaseModel):
    run_id: UUID
    points: list[RunNormalizedEquityPointOut] = Field(default_factory=list)


class RunCompareOut(BaseModel):
    base_run_id: UUID
    run_ids: list[UUID]
    metric_rows: list[RunCompareMetricRowOut] = Field(default_factory=list)
    equity_series: list[RunCompareSeriesOut] = Field(default_factory=list)


class RunBenchmarkPointOut(BaseModel):
    date: date
    benchmark_equity_base: float
    benchmark_return: float


class RunMonthlyReturnOut(BaseModel):
    year: int
    month: int
    return_value: float = Field(serialization_alias="return")
    benchmark_return: Optional[float] = None


class RunAnnualReturnOut(BaseModel):
    year: int
    return_value: float = Field(serialization_alias="return")
    benchmark_return: Optional[float] = None


class RunPeriodReturnSummaryOut(BaseModel):
    return_value: Optional[float] = Field(default=None, serialization_alias="return")
    benchmark_return: Optional[float] = None


class RunPeriodicReturnsOut(BaseModel):
    monthly: list[RunMonthlyReturnOut] = Field(default_factory=list)
    annual: list[RunAnnualReturnOut] = Field(default_factory=list)
    ytd: RunPeriodReturnSummaryOut
    full_period: RunPeriodReturnSummaryOut


class RunRollingPointOut(BaseModel):
    date: date
    sharpe: Optional[float] = None
    volatility: Optional[float] = None
    beta: Optional[float] = None


class RunRollingMetaOut(BaseModel):
    window: int
    metrics: list[str]
    reason: Optional[str] = None
    required_observations: int
    available_observations: int


class RunRollingOut(BaseModel):
    data: list[RunRollingPointOut] = Field(default_factory=list)
    meta: RunRollingMetaOut


class RunMonteCarloRequest(BaseModel):
    method: Literal["bootstrap", "block_bootstrap", "trade_shuffle"] = "bootstrap"
    n: int = Field(default=5000, ge=100, le=50_000)
    block_len: int = Field(default=5, ge=2, le=252)


class RunMonteCarloDistributionOut(BaseModel):
    p05: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p95: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    ci95: list[float] = Field(default_factory=list)


class RunMonteCarloPathOut(BaseModel):
    path_id: int
    values: list[float]


class RunMonteCarloOut(BaseModel):
    run_id: UUID
    method: str
    source: str
    frequency: str
    n: int
    horizon: int
    block_len: Optional[int] = None
    seed: int
    terminal_return: RunMonteCarloDistributionOut
    max_drawdown: RunMonteCarloDistributionOut
    sharpe: RunMonteCarloDistributionOut
    probability_positive: float
    drawdown_at_risk_95: Optional[float] = None
    paths: list[RunMonteCarloPathOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RunReturnAttributionRowOut(BaseModel):
    symbol: str
    contribution: float
    avg_weight: float
    total_return: Optional[float] = None


class RunCostWaterfallItemOut(BaseModel):
    key: str
    amount_base: float
    return_drag_bps: float


class RunCostAttributionOut(BaseModel):
    base_currency: str
    initial_capital_base: float
    items: list[RunCostWaterfallItemOut] = Field(default_factory=list)
