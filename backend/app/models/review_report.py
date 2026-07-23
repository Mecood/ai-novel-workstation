import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(GUID, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True)
    chapter_number = Column(Integer, nullable=False)
    overall_score = Column(Numeric(5, 2), default=0.0)
    dimension_scores = Column(JSON, default=dict)
    severity_counts = Column(JSON, default=dict)
    issues = Column(JSON, default=list)
    blocking_count = Column(Integer, default=0)
    summary = Column(Text, nullable=True)
    report_file = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ── Phase 7b：三层评审结果 ─────────────────────────────────────────
    tiered_results = Column(JSON, nullable=True, default=dict)
    # 格式: {"l1": {...}, "l2": {...}, "l3": {...}}

    # ── Phase 15.2：用户裁决 ──────────────────────────────────────────
    user_decision = Column(String(32), nullable=True)
    user_note = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "chapter_number", name="uq_review_project_chapter"),
    )