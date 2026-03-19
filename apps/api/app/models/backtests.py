from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.strategy_id"))
    name = Column(String)
    status = Column(String, nullable=False)
    error = Column(Text)
    error_code = Column(String)
    error_message_public = Column(Text)
    error_retryable = Column(Boolean)
    error_id = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    config_snapshot = Column(JSONB, nullable=False)
    data_snapshot_id = Column(String, nullable=False)
    seed = Column(Integer, nullable=False, server_default=text("42"))

    __table_args__ = (
        Index("backtest_runs_status_idx", "status"),
        Index("backtest_runs_created_idx", "created_at"),
    )


class BacktestRequestIdempotency(Base):
    __tablename__ = "backtest_request_idempotency"

    idempotency_key = Column(String, primary_key=True, nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("backtest_request_idempotency_expires_idx", "expires_at"),
    )


class RunMetric(Base):
    __tablename__ = "run_metrics"

    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), primary_key=True)
    cagr = Column(Float)
    volatility = Column(Float)
    sharpe = Column(Float)
    sortino = Column(Float)
    max_drawdown = Column(Float)
    turnover = Column(Float)
    gross_return = Column(Float)
    net_return = Column(Float)
    fee_drag = Column(Float)
    tax_drag = Column(Float)
    borrow_drag = Column(Float)
    margin_interest_drag = Column(Float)
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class RunDailyEquity(Base):
    __tablename__ = "run_daily_equity"

    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), primary_key=True)
    date = Column(Date, primary_key=True)
    equity_base = Column(Float, nullable=False)
    cash_base = Column(Float, nullable=False)
    gross_exposure_base = Column(Float, nullable=False)
    net_exposure_base = Column(Float, nullable=False)
    drawdown = Column(Float, nullable=False)
    fees_cum_base = Column(Float, nullable=False)
    taxes_cum_base = Column(Float, nullable=False)
    borrow_fees_cum_base = Column(Float, nullable=False)
    margin_interest_cum_base = Column(Float, nullable=False)
    equity_by_currency = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    cash_by_currency = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    fees_cum_by_currency = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("run_daily_equity_date_idx", "date"),
    )


class RunPosition(Base):
    __tablename__ = "run_positions"

    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), primary_key=True)
    date = Column(Date, primary_key=True)
    symbol = Column(String, primary_key=True)
    qty = Column(Float, nullable=False)
    avg_cost_native = Column(Float, nullable=False)
    market_value_base = Column(Float, nullable=False)
    unrealized_pnl_base = Column(Float, nullable=False)


class RunOrder(Base):
    __tablename__ = "run_orders"

    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), nullable=False)
    date = Column(Date, nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    qty = Column(Float, nullable=False)
    order_type = Column(String, nullable=False)
    limit_price = Column(Float)
    status = Column(String, nullable=False)
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("run_orders_run_date_idx", "run_id", "date"),
    )


class RunFill(Base):
    __tablename__ = "run_fills"

    fill_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("run_orders.order_id"))
    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), nullable=False)
    date = Column(Date, nullable=False)
    symbol = Column(String, nullable=False)
    qty = Column(Float, nullable=False)
    price_native = Column(Float, nullable=False)
    commission_native = Column(Float, nullable=False)
    slippage_native = Column(Float, nullable=False)
    notional_native = Column(Float, nullable=False)
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("run_fills_run_date_idx", "run_id", "date"),
    )


class RunTaxEvent(Base):
    __tablename__ = "run_tax_events"

    tax_event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), nullable=False)
    date = Column(Date, nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    realized_pnl_base = Column(Float, nullable=False)
    holding_period_days = Column(Integer, nullable=False)
    bucket = Column(String, nullable=False)
    tax_rate = Column(Float, nullable=False)
    tax_due_base = Column(Float, nullable=False)
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("run_tax_events_run_date_idx", "run_id", "date"),
    )


class RunFinancing(Base):
    __tablename__ = "run_financing"

    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"), primary_key=True)
    date = Column(Date, primary_key=True)
    margin_borrowed_base = Column(Float, nullable=False)
    margin_interest_base = Column(Float, nullable=False)
    short_notional_base = Column(Float, nullable=False)
    borrow_fee_base = Column(Float, nullable=False)
