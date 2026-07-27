"""Add signal snapshots and order-decision records.

Revision ID: 0012_explainability_records
Revises: 0011_research_robustness
Create Date: 2026-07-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_explainability_records"
down_revision = "0011_research_robustness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_signal_snapshots",
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("signal_name", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column(
            "selected",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_runs.run_id"]),
        sa.PrimaryKeyConstraint("signal_id"),
    )
    op.create_index(
        "run_signal_snapshots_run_date_idx",
        "run_signal_snapshots",
        ["run_id", "date"],
    )
    op.create_index(
        "run_signal_snapshots_run_date_symbol_idx",
        "run_signal_snapshots",
        ["run_id", "date", "symbol"],
    )

    op.create_table(
        "run_order_decisions",
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("requested_target_weight", sa.Float(), nullable=True),
        sa.Column("target_weight", sa.Float(), nullable=True),
        sa.Column("target_qty", sa.Float(), nullable=True),
        sa.Column("current_qty", sa.Float(), nullable=False),
        sa.Column("delta_qty", sa.Float(), nullable=True),
        sa.Column("intended_side", sa.String(), nullable=True),
        sa.Column("intended_qty", sa.Float(), nullable=True),
        sa.Column("executable_qty", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_runs.run_id"]),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index(
        "run_order_decisions_run_date_idx",
        "run_order_decisions",
        ["run_id", "date"],
    )
    op.create_index(
        "run_order_decisions_run_date_symbol_idx",
        "run_order_decisions",
        ["run_id", "date", "symbol"],
    )


def downgrade() -> None:
    op.drop_index(
        "run_order_decisions_run_date_symbol_idx",
        table_name="run_order_decisions",
    )
    op.drop_index(
        "run_order_decisions_run_date_idx",
        table_name="run_order_decisions",
    )
    op.drop_table("run_order_decisions")
    op.drop_index(
        "run_signal_snapshots_run_date_symbol_idx",
        table_name="run_signal_snapshots",
    )
    op.drop_index(
        "run_signal_snapshots_run_date_idx",
        table_name="run_signal_snapshots",
    )
    op.drop_table("run_signal_snapshots")
