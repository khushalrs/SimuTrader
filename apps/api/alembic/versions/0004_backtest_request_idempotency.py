"""Add request idempotency table for backtests

Revision ID: 0004_req_idempotency
Revises: 0003_backtest_run_failure_fields
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0004_req_idempotency"
down_revision = "0003_backtest_run_failure_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_request_idempotency",
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("idempotency_key"),
    )
    op.create_index(
        "backtest_request_idempotency_expires_idx",
        "backtest_request_idempotency",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "backtest_request_idempotency_expires_idx",
        table_name="backtest_request_idempotency",
    )
    op.drop_table("backtest_request_idempotency")
