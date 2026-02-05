from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, Column, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"

    asset_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol = Column(String, unique=True, nullable=False)
    name = Column(Text)
    asset_class = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    exchange = Column(String)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    data_source = Column(String, nullable=False)
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        Index("assets_class_idx", "asset_class"),
    )
