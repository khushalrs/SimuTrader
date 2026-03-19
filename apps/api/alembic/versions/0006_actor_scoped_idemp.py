"""Scope idempotency records by actor key

Revision ID: 0006_actor_scoped_idemp
Revises: 0005_run_exec_actor_meta
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_actor_scoped_idemp"
down_revision = "0005_run_exec_actor_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "backtest_request_idempotency",
        sa.Column("actor_key", sa.String(), nullable=True),
    )
    op.execute(
        "UPDATE backtest_request_idempotency "
        "SET actor_key = 'legacy:unknown' "
        "WHERE actor_key IS NULL"
    )
    op.drop_constraint(
        "backtest_request_idempotency_pkey",
        "backtest_request_idempotency",
        type_="primary",
    )
    op.alter_column("backtest_request_idempotency", "actor_key", nullable=False)
    op.create_primary_key(
        "backtest_request_idempotency_pkey",
        "backtest_request_idempotency",
        ["actor_key", "idempotency_key"],
    )
    op.create_index(
        "backtest_request_idempotency_actor_expires_idx",
        "backtest_request_idempotency",
        ["actor_key", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "backtest_request_idempotency_actor_expires_idx",
        table_name="backtest_request_idempotency",
    )
    op.drop_constraint(
        "backtest_request_idempotency_pkey",
        "backtest_request_idempotency",
        type_="primary",
    )
    op.create_primary_key(
        "backtest_request_idempotency_pkey",
        "backtest_request_idempotency",
        ["idempotency_key"],
    )
    op.drop_column("backtest_request_idempotency", "actor_key")
