"""Add run query performance indexes

Revision ID: 0007_run_query_perf_idx
Revises: 0006_actor_scoped_idemp
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_run_query_perf_idx"
down_revision = "0006_actor_scoped_idemp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "backtest_runs_actor_created_idx",
        "backtest_runs",
        ["actor_key", "created_at"],
    )
    op.create_index(
        "backtest_runs_status_created_idx",
        "backtest_runs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("backtest_runs_status_created_idx", table_name="backtest_runs")
    op.drop_index("backtest_runs_actor_created_idx", table_name="backtest_runs")
