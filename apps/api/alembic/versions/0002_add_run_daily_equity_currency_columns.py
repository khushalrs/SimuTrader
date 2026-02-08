"""Add currency buckets to run_daily_equity

Revision ID: 0002_rde_currency_cols
Revises: 0001_init_schema
Create Date: 2026-02-08 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_rde_currency_cols"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_daily_equity",
        sa.Column(
            "equity_by_currency",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "run_daily_equity",
        sa.Column(
            "cash_by_currency",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "run_daily_equity",
        sa.Column(
            "fees_cum_by_currency",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("run_daily_equity", "fees_cum_by_currency")
    op.drop_column("run_daily_equity", "cash_by_currency")
    op.drop_column("run_daily_equity", "equity_by_currency")
