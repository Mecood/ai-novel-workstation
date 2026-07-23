import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.sql import func
from app.core.database import Base, GUID
import enum


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"              # 未签署（契约生成后但未确认）
    SIGNED = "signed"            # 已签署（写前状态）
    FULFILLED = "fulfilled"      # 已履行（写后判定通过）
    REJECTED = "rejected"        # 已拒绝（写后判定未通过）


class ChapterContract(Base):
    """
    写前契约 — 记录一章承诺完成什么、不能碰什么。
    每章最多一条有效契约（通过 project_id + chapter_number 唯一约束保证）。
    """
    __tablename__ = "chapter_contracts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)
    chapter_id = Column(GUID, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)

    # 契约状态
    status = Column(String(20), nullable=False, default=ContractStatus.DRAFT.value, index=True)

    # ── 契约内容（LLM 生成） ─────────────────────────────────────────────

    # 必须覆盖的叙事节点列表
    # 每个节点格式：{ "id": "node_001", "title": "林动突破地阶", "description": "林动在古墓中突破至地阶修为", "character": "林动" }
    required_nodes = Column(JSON, default=list)

    # 可选覆盖的节点列表
    optional_nodes = Column(JSON, default=list)

    # 写作约束列表
    # 每个约束格式：{ "key": "word_count", "label": "字数控制", "value": "2000-3000字" }
    constraints = Column(JSON, default=list)

    # 禁区列表（不能碰的内容）
    # 每个禁区格式：{ "id": "zone_001", "description": "不能提前揭露幕后黑手修罗殿主", "reason": "伏笔设置在第20章回收" }
    forbidden_zones = Column(JSON, default=list)

    # 生成契约时的上下文摘要（用于调试和审计）
    context_summary = Column(Text, nullable=True)

    # ── 时间戳 ──────────────────────────────────────────────────────────
    signed_at = Column(DateTime(timezone=True), nullable=True)     # 签署时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # 每章最多一条有效契约
        {"extend_existing": True},
    )