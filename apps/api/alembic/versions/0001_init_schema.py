"""Initial schema

Revision ID: 0001_init_schema
Revises: 
Create Date: 2026-01-28 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.Text()),
        sa.Column("asset_class", sa.String(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("exchange", sa.String()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("data_source", sa.String(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("assets_class_idx", "assets", ["asset_class"])

    op.create_table(
        "trading_calendars",
        sa.Column("calendar_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_table(
        "calendar_days",
        sa.Column(
            "calendar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trading_calendars.calendar_id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("is_trading_day", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("calendar_id", "date"),
    )

    op.create_table(
        "strategies",
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("strategies_created_idx", "strategies", ["created_at"])

    op.create_table(
        "backtest_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategies.strategy_id"),
        ),
        sa.Column("name", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("config_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_snapshot_id", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False, server_default=sa.text("42")),
    )
    op.create_index("backtest_runs_status_idx", "backtest_runs", ["status"])
    op.create_index("backtest_runs_created_idx", "backtest_runs", ["created_at"])

    op.create_table(
        "run_metrics",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("cagr", sa.Float()),
        sa.Column("volatility", sa.Float()),
        sa.Column("sharpe", sa.Float()),
        sa.Column("sortino", sa.Float()),
        sa.Column("max_drawdown", sa.Float()),
        sa.Column("turnover", sa.Float()),
        sa.Column("gross_return", sa.Float()),
        sa.Column("net_return", sa.Float()),
        sa.Column("fee_drag", sa.Float()),
        sa.Column("tax_drag", sa.Float()),
        sa.Column("borrow_drag", sa.Float()),
        sa.Column("margin_interest_drag", sa.Float()),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_table(
        "run_daily_equity",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("equity_base", sa.Float(), nullable=False),
        sa.Column("cash_base", sa.Float(), nullable=False),
        sa.Column("gross_exposure_base", sa.Float(), nullable=False),
        sa.Column("net_exposure_base", sa.Float(), nullable=False),
        sa.Column("drawdown", sa.Float(), nullable=False),
        sa.Column("fees_cum_base", sa.Float(), nullable=False),
        sa.Column("taxes_cum_base", sa.Float(), nullable=False),
        sa.Column("borrow_fees_cum_base", sa.Float(), nullable=False),
        sa.Column("margin_interest_cum_base", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "date"),
    )
    op.create_index("run_daily_equity_date_idx", "run_daily_equity", ["date"])

    op.create_table(
        "run_positions",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("avg_cost_native", sa.Float(), nullable=False),
        sa.Column("market_value_base", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl_base", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "date", "symbol"),
    )

    op.create_table(
        "run_orders",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("order_type", sa.String(), nullable=False),
        sa.Column("limit_price", sa.Float()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("run_orders_run_date_idx", "run_orders", ["run_id", "date"])

    op.create_table(
        "run_fills",
        sa.Column("fill_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("run_orders.order_id"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("price_native", sa.Float(), nullable=False),
        sa.Column("commission_native", sa.Float(), nullable=False),
        sa.Column("slippage_native", sa.Float(), nullable=False),
        sa.Column("notional_native", sa.Float(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("run_fills_run_date_idx", "run_fills", ["run_id", "date"])

    op.create_table(
        "run_tax_events",
        sa.Column("tax_event_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("realized_pnl_base", sa.Float(), nullable=False),
        sa.Column("holding_period_days", sa.Integer(), nullable=False),
        sa.Column("bucket", sa.String(), nullable=False),
        sa.Column("tax_rate", sa.Float(), nullable=False),
        sa.Column("tax_due_base", sa.Float(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("run_tax_events_run_date_idx", "run_tax_events", ["run_id", "date"])

    op.create_table(
        "run_financing",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("margin_borrowed_base", sa.Float(), nullable=False),
        sa.Column("margin_interest_base", sa.Float(), nullable=False),
        sa.Column("short_notional_base", sa.Float(), nullable=False),
        sa.Column("borrow_fee_base", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "date"),
    )


def downgrade() -> None:
    op.drop_table("run_financing")
    op.drop_index("run_tax_events_run_date_idx", table_name="run_tax_events")
    op.drop_table("run_tax_events")
    op.drop_index("run_fills_run_date_idx", table_name="run_fills")
    op.drop_table("run_fills")
    op.drop_index("run_orders_run_date_idx", table_name="run_orders")
    op.drop_table("run_orders")
    op.drop_table("run_positions")
    op.drop_index("run_daily_equity_date_idx", table_name="run_daily_equity")
    op.drop_table("run_daily_equity")
    op.drop_table("run_metrics")
    op.drop_index("backtest_runs_created_idx", table_name="backtest_runs")
    op.drop_index("backtest_runs_status_idx", table_name="backtest_runs")
    op.drop_table("backtest_runs")
    op.drop_index("strategies_created_idx", table_name="strategies")
    op.drop_table("strategies")
    op.drop_table("calendar_days")
    op.drop_table("trading_calendars")
    op.drop_index("assets_class_idx", table_name="assets")
    op.drop_table("assets")
