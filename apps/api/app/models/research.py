from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    base_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("backtest_runs.run_id"),
        nullable=False,
    )
    type = Column(String, nullable=False)
    base_config = Column(JSONB, nullable=False)
    spec = Column(JSONB, nullable=False)
    status = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    planned_child_count = Column(Integer, nullable=False)
    actor_tier = Column(String, nullable=False)
    actor_key = Column(String, nullable=False)
    data_snapshot_id = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.strategy_id"))
    error_code = Column(String)
    error_message_public = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    started_at = Column(DateTime(timezone=True))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
    finished_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "type IN ('SWEEP', 'IS_OOS', 'WALK_FORWARD')",
            name="research_jobs_type_check",
        ),
        CheckConstraint(
            "planned_child_count > 0",
            name="research_jobs_planned_child_count_check",
        ),
        Index("research_jobs_actor_created_idx", "actor_key", "created_at"),
        Index("research_jobs_actor_status_idx", "actor_key", "status"),
    )


class ResearchJobRun(Base):
    __tablename__ = "research_job_runs"

    job_run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id = Column(UUID(as_uuid=True), ForeignKey("backtest_runs.run_id"))
    ordinal = Column(Integer, nullable=False)
    role = Column(String, nullable=False)
    params_json = Column(JSONB, nullable=False)
    config_json = Column(JSONB, nullable=False)
    config_hash = Column(String, nullable=False)
    dispatch_status = Column(
        String,
        nullable=False,
        server_default=text("'PLANNED'"),
    )
    is_selected = Column(Boolean, nullable=False, server_default=text("false"))
    segment_index = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "role",
            "ordinal",
            name="research_job_runs_job_role_ordinal_key",
        ),
        UniqueConstraint(
            "job_id",
            "role",
            "config_hash",
            name="research_job_runs_job_role_hash_key",
        ),
        Index("research_job_runs_job_idx", "job_id"),
        Index("research_job_runs_run_idx", "run_id"),
    )
