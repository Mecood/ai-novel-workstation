import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class Knowledge(Base):
    __tablename__ = "knowledges"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="general")
    tags = Column(JSON, nullable=True, default=list)
    source = Column(String(20), nullable=False, default="manual")  # manual / auto
    source_type = Column(String(50), nullable=True)  # worldview / character / chapter / story_core
    source_id = Column(GUID, nullable=True)  # 关联的实体ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())