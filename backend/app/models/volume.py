import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class Volume(Base):
    __tablename__ = "volumes"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    volume_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    chapter_start = Column(Integer, nullable=False, default=1)
    chapter_end = Column(Integer, nullable=True)
    highlight_rhythm = Column(JSON, nullable=True)
    emotion_arc = Column(JSON, nullable=True)
    foreshadowing_notes = Column(JSON, nullable=True)
    twists = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
