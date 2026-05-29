import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class Worldview(Base):
    __tablename__ = "worldviews"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    rules = Column(JSON, nullable=True)
    timeline = Column(JSON, nullable=True)
    _version = Column(Integer, default=0)
    _based_on = Column(JSON, nullable=True, default=dict)
    _history = Column(JSON, nullable=True, default=list)
    _stale = Column(String(10), nullable=False, default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())