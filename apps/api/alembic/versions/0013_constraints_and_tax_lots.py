"""Add linked constraint events and FIFO tax-lot consumptions.

Revision ID: 0013_constraints_and_tax_lots
Revises: 0012_explainability_records
Create Date: 2026-07-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0013_constraints_and_tax_lots"
down_revision = "0012_explainability_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_order_decisions",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "run_order_decisions_order_id_fkey",
        "run_order_decisions",
        "run_orders",
        ["order_id"],
        ["order_id"],
    )
    op.create_index(
        "run_order_decisions_order_id_idx",
        "run_order_decisions",
        ["order_id"],
    )

    op.create_table(
        "run_constraint_events",
        sa.Column("constraint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("constraint_name", sa.String(), nullable=False),
        sa.Column("bound_value", sa.Float(), nullable=True),
        sa.Column("pre_clamp_value", sa.Float(), nullable=False),
        sa.Column("applied_value", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["run_order_decisions.decision_id"],
        ),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_runs.run_id"]),
        sa.PrimaryKeyConstraint("constraint_id"),
    )
    op.create_index(
        "run_constraint_events_run_date_idx",
        "run_constraint_events",
        ["run_id", "date"],
    )
    op.create_index(
        "run_constraint_events_decision_idx",
        "run_constraint_events",
        ["decision_id"],
    )

    op.create_table(
        "run_tax_lot_consumptions",
        sa.Column("consumption_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tax_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("lot_opened_on", sa.Date(), nullable=False),
        sa.Column("lot_unit_cost_native", sa.Float(), nullable=False),
        sa.Column("qty_consumed", sa.Float(), nullable=False),
        sa.Column("holding_days", sa.Integer(), nullable=False),
        sa.Column("bucket", sa.String(), nullable=False),
        sa.Column("realized_pnl_base", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tax_event_id"],
            ["run_tax_events.tax_event_id"],
        ),
        sa.ForeignKeyConstraint(["run_id"], ["backtest_runs.run_id"]),
        sa.PrimaryKeyConstraint("consumption_id"),
    )
    op.create_index(
        "run_tax_lot_consumptions_run_date_idx",
        "run_tax_lot_consumptions",
        ["run_id", "date"],
    )
    op.create_index(
        "run_tax_lot_consumptions_event_idx",
        "run_tax_lot_consumptions",
        ["tax_event_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "run_tax_lot_consumptions_event_idx",
        table_name="run_tax_lot_consumptions",
    )
    op.drop_index(
        "run_tax_lot_consumptions_run_date_idx",
        table_name="run_tax_lot_consumptions",
    )
    op.drop_table("run_tax_lot_consumptions")
    op.drop_index(
        "run_constraint_events_decision_idx",
        table_name="run_constraint_events",
    )
    op.drop_index(
        "run_constraint_events_run_date_idx",
        table_name="run_constraint_events",
    )
    op.drop_table("run_constraint_events")
    op.drop_index(
        "run_order_decisions_order_id_idx",
        table_name="run_order_decisions",
    )
    op.drop_constraint(
        "run_order_decisions_order_id_fkey",
        "run_order_decisions",
        type_="foreignkey",
    )
    op.drop_column("run_order_decisions", "order_id")
