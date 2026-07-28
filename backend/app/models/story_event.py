import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey, Numeric
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class StoryEvent(Base):
    __tablename__ = "story_events"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)
    chapter_id = Column(GUID, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True, index=True)

    event_type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    entities = Column(JSON, default=list)
    character_ids = Column(JSON, default=list)

    confidence = Column(Numeric(3, 2), default=1.0)
    evidence = Column(Text, nullable=True)

    order = Column(Integer, default=0)
    # ── timeline_track 待下次 DB migration ──
    # timeline_track = Column(Text, default="main")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        {"extend_existing": True},
    )