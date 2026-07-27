"""Persist benchmark equity and promote relative performance metrics.

Revision ID: 0009_benchmark_metrics
Revises: 0008_strategy_actor_scope
Create Date: 2026-07-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_benchmark_metrics"
down_revision = "0008_strategy_actor_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_daily_equity",
        sa.Column("benchmark_equity_base", sa.Float(), nullable=True),
    )
    for column_name in (
        "beta",
        "alpha",
        "tracking_error",
        "information_ratio",
    ):
        op.add_column(
            "run_metrics",
            sa.Column(column_name, sa.Float(), nullable=True),
        )

    # Preserve already-computed values for existing runs where possible.
    op.execute(
        """
        UPDATE run_metrics
        SET
            beta = CASE
                WHEN jsonb_typeof(meta->'beta') = 'number'
                THEN (meta->>'beta')::double precision
            END,
            alpha = CASE
                WHEN jsonb_typeof(meta->'alpha') = 'number'
                THEN (meta->>'alpha')::double precision
            END,
            information_ratio = CASE
                WHEN jsonb_typeof(meta->'information_ratio') = 'number'
                THEN (meta->>'information_ratio')::double precision
            END
        """
    )


def downgrade() -> None:
    for column_name in (
        "information_ratio",
        "tracking_error",
        "alpha",
        "beta",
    ):
        op.drop_column("run_metrics", column_name)
    op.drop_column("run_daily_equity", "benchmark_equity_base")
