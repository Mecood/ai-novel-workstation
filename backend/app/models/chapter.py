import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(JSON, nullable=True)
    summary = Column(String(1000), nullable=True)
    outline_detail = Column(JSON, nullable=True)
    word_count = Column(Integer, default=0)
    status = Column(String(50), nullable=False, default="draft")
    _version = Column(Integer, default=0)
    _based_on = Column(JSON, nullable=True, default=dict)
    _history = Column(JSON, nullable=True, default=list)
    _stale = Column(String(10), nullable=False, default="false")

    # ── Phase 7a：CBN/CPNs/CEN 骨架 JSON ─────────────────────────
    _skeleton = Column(JSON, nullable=True, default=dict)

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

    @property
    def skeleton(self) -> dict:
        """返回骨架数据，兼容旧行：NULL 或 None → 空 dict。"""
        return self._skeleton or {}

    @skeleton.setter
    def skeleton(self, value: dict | None) -> None:
        self._skeleton = value