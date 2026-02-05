from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class Strategy(Base):
    __tablename__ = "strategies"

    strategy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    config = Column(JSONB, nullable=False)

    __table_args__ = (
        Index("strategies_created_idx", "created_at"),
    )
