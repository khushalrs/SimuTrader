"""Add research jobs and child-run planning.

Revision ID: 0010_research_jobs
Revises: 0009_benchmark_metrics
Create Date: 2026-07-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0010_research_jobs"
down_revision = "0009_benchmark_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_jobs",
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "base_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column(
            "base_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "spec",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("planned_child_count", sa.Integer(), nullable=False),
        sa.Column("actor_tier", sa.String(), nullable=False),
        sa.Column("actor_key", sa.String(), nullable=False),
        sa.Column("data_snapshot_id", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column(
            "strategy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("strategies.strategy_id"),
        ),
        sa.Column("error_code", sa.String()),
        sa.Column("error_message_public", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "type IN ('SWEEP', 'IS_OOS', 'WALK_FORWARD')",
            name="research_jobs_type_check",
        ),
        sa.CheckConstraint(
            "planned_child_count > 0",
            name="research_jobs_planned_child_count_check",
        ),
    )
    op.create_index(
        "research_jobs_actor_created_idx",
        "research_jobs",
        ["actor_key", "created_at"],
    )
    op.create_index(
        "research_jobs_actor_status_idx",
        "research_jobs",
        ["actor_key", "status"],
    )

    op.create_table(
        "research_job_runs",
        sa.Column(
            "job_run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_jobs.job_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.run_id"),
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column(
            "params_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column(
            "dispatch_status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'PLANNED'"),
        ),
        sa.Column(
            "is_selected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("segment_index", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "job_id",
            "role",
            "ordinal",
            name="research_job_runs_job_role_ordinal_key",
        ),
        sa.UniqueConstraint(
            "job_id",
            "role",
            "config_hash",
            name="research_job_runs_job_role_hash_key",
        ),
    )
    op.create_index(
        "research_job_runs_job_idx",
        "research_job_runs",
        ["job_id"],
    )
    op.create_index(
        "research_job_runs_run_idx",
        "research_job_runs",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index("research_job_runs_run_idx", table_name="research_job_runs")
    op.drop_index("research_job_runs_job_idx", table_name="research_job_runs")
    op.drop_table("research_job_runs")
    op.drop_index("research_jobs_actor_status_idx", table_name="research_jobs")
    op.drop_index("research_jobs_actor_created_idx", table_name="research_jobs")
    op.drop_table("research_jobs")
