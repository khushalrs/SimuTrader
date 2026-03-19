"""Add run execution metadata and actor tier fields

Revision ID: 0005_run_exec_actor_meta
Revises: 0004_req_idempotency
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_run_exec_actor_meta"
down_revision = "0004_req_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "backtest_runs",
        sa.Column("actor_tier", sa.String(), nullable=False, server_default=sa.text("'guest'")),
    )
    op.add_column("backtest_runs", sa.Column("actor_key", sa.String(), nullable=True))
    op.add_column("backtest_runs", sa.Column("execution_task_id", sa.String(), nullable=True))
    op.create_index(
        "backtest_runs_actor_status_idx",
        "backtest_runs",
        ["actor_key", "status"],
    )
    op.create_index(
        "backtest_runs_execution_task_id_idx",
        "backtest_runs",
        ["execution_task_id"],
    )


def downgrade() -> None:
    op.drop_index("backtest_runs_execution_task_id_idx", table_name="backtest_runs")
    op.drop_index("backtest_runs_actor_status_idx", table_name="backtest_runs")
    op.drop_column("backtest_runs", "execution_task_id")
    op.drop_column("backtest_runs", "actor_key")
    op.drop_column("backtest_runs", "actor_tier")
