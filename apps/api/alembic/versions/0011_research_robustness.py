"""Store research robustness summaries.

Revision ID: 0011_research_robustness
Revises: 0010_research_jobs
Create Date: 2026-07-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_research_robustness"
down_revision = "0010_research_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_jobs",
        sa.Column(
            "robustness_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "research_jobs",
        sa.Column(
            "robustness_computed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("research_jobs", "robustness_computed_at")
    op.drop_column("research_jobs", "robustness_summary")
