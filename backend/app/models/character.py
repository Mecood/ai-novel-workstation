import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, ForeignKey
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
    first_appearance_chapter = Column(Integer, nullable=True)
    last_appearance_chapter = Column(Integer, nullable=True)
    aliases = Column(JSON, nullable=True, default=list)
    appearance_chapters = Column(JSON, nullable=True, default=list)
    _version = Column(Integer, default=0)
    _based_on = Column(JSON, nullable=True, default=dict)
    _history = Column(JSON, nullable=True, default=list)
    _stale = Column(String(10), nullable=False, default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def version(self):
        return self._version

    @property
    def stale(self):
        return self._stale

    @property
    def based_on(self):
        return self._based_on

    @property
    def history(self):
        return self._history