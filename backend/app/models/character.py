import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class Character(Base):
    __tablename__ = "characters"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    role_type = Column(String(50), nullable=False)
    personality = Column(JSON, nullable=True)
    background = Column(Text, nullable=True)
    appearance = Column(Text, nullable=True)
    relationships = Column(JSON, nullable=True)
    arc = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())