"""Actor-scope strategies with ownership columns and index

Revision ID: 0008_strategy_actor_scope
Revises: 0007_run_query_perf_idx
Create Date: 2026-04-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_strategy_actor_scope"
down_revision = "0007_run_query_perf_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("actor_tier", sa.String(), nullable=False, server_default=sa.text("'guest'")),
    )
    op.add_column("strategies", sa.Column("actor_key", sa.String(), nullable=True))
    op.execute(
        "UPDATE strategies SET actor_key = 'legacy:strategy' WHERE actor_key IS NULL"
    )
    op.alter_column("strategies", "actor_key", nullable=False)
    op.create_index(
        "strategies_actor_created_idx",
        "strategies",
        ["actor_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("strategies_actor_created_idx", table_name="strategies")
    op.drop_column("strategies", "actor_key")
    op.drop_column("strategies", "actor_tier")

