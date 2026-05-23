import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, default="chapter")  # chapter/character/worldview/outline
    system_prompt = Column(Text, nullable=True)
    user_prompt_template = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)
    is_default = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
