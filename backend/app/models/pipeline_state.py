"""Pipeline state persistence model."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text

from app.core.database import Base, GUID


class PipelineState(Base):
    __tablename__ = "pipeline_state"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, nullable=False, index=True)
    current_stage = Column(String(32), default="init", nullable=False)
    last_advanced_at = Column(DateTime, nullable=True)
    total_chapters = Column(Integer, default=0)
    reviewed_chapters = Column(Integer, default=0)
    committed_chapters = Column(Integer, default=0)
    pipeline_runs = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))