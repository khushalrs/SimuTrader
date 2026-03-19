"""Add structured failure fields to backtest_runs

Revision ID: 0003_backtest_run_failure_fields
Revises: 0002_rde_currency_cols
Create Date: 2026-03-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_backtest_run_failure_fields"
down_revision = "0002_rde_currency_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backtest_runs", sa.Column("error_code", sa.String(), nullable=True))
    op.add_column(
        "backtest_runs", sa.Column("error_message_public", sa.Text(), nullable=True)
    )
    op.add_column(
        "backtest_runs", sa.Column("error_retryable", sa.Boolean(), nullable=True)
    )
    op.add_column("backtest_runs", sa.Column("error_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("backtest_runs", "error_id")
    op.drop_column("backtest_runs", "error_retryable")
    op.drop_column("backtest_runs", "error_message_public")
    op.drop_column("backtest_runs", "error_code")
