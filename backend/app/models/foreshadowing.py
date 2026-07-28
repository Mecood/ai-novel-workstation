import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, JSON, Numeric, Text
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class Foreshadowing(Base):
    __tablename__ = "foreshadowings"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False)
    target_chapter = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="planted")
    event_id = Column(GUID, ForeignKey("story_events.id", ondelete="SET NULL"), nullable=True)
    payoff_chapter = Column(Integer, nullable=True)
    auto_match_confidence = Column(Numeric(3, 2), nullable=True)

    # ── Phase 14.4: 伏笔 DAG 支持 ─────────────────────────────────────
    depends_on = Column(JSON, nullable=True, default=list)
    dependency_type = Column(String(32), nullable=True, default="prerequisite")
    expected_redemption_chapter = Column(Integer, nullable=True)
    auto_check_enabled = Column(Boolean, nullable=False, default=True)

    # ── 伏笔管理重构：证据链 + 三步回收流程 ───────────────────────────
    evidence_line = Column(String(255), nullable=True)
    evidence_chapter = Column(Integer, nullable=True)
    evidence_text = Column(Text, nullable=True)
    reminder_level = Column(String(20), nullable=False, default="low")
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())