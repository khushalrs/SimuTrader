from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, Column, Date, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class TradingCalendar(Base):
    __tablename__ = "trading_calendars"

    calendar_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, unique=True, nullable=False)
    timezone = Column(String, nullable=False)
    meta = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class CalendarDay(Base):
    __tablename__ = "calendar_days"

    calendar_id = Column(UUID(as_uuid=True), ForeignKey("trading_calendars.calendar_id"), primary_key=True)
    date = Column(Date, primary_key=True)
    is_trading_day = Column(Boolean, nullable=False)
