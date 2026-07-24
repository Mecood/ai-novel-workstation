"""参考书拆解（Deconstruction Agent）历史记录模型。

与 DeconstructionHistory 表映射：记录一次参考书拆解分析的结果，
供项目复用、对比、回溯拆解思路。
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base, GUID


class DeconstructionHistory(Base):
    """参考书拆解历史记录。"""
    __tablename__ = "deconstruction_history"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    reference_title = Column(String(500), nullable=False, default="")
    analysis_mode = Column(String(20), nullable=False, default="quick")  # quick / deep
    target_genre = Column(String(100), nullable=False, default="")
    raw_result = Column(JSON, nullable=True)
    canon_contamination_warnings = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Optional back-reference to Project (not imported eagerly to avoid circular deps)
