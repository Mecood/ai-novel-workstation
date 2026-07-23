import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class Project(Base):
    __tablename__ = "projects"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    genre = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="draft")
    story_core = Column(JSON, nullable=True)
    context = Column(JSON, nullable=True)  # Phase 14.3: 风格指导等额外上下文
    template_id = Column(GUID, ForeignKey("genre_templates.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    pipeline_stage = Column(String(20), nullable=True, default="init")  # init/plan/write/review/commit/completed
    auto_advance_enabled = Column(Boolean, nullable=False, default=True)  # Phase 9：自动推进开关
