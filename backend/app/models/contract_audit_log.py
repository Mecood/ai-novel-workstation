"""
Contract audit log model — append-only 合同审计日志。

与 ChapterContract 的关系：
  - ChapterContract：当前契约快照（可更新，反映当前状态）
  - ContractAuditLog：所有变更的不可篡改日志（只增不改，append-only）

每次 ChapterContract 被 create/update/status 变更时，
ContractService 都会追加一条审计记录。状态损坏时可通过日志重建。
"""
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class ContractAuditLog(Base):
    """
    合同审计日志（append-only）。

    所有操作类型（action）：
      CREATE     — 契约创建
      UPDATE     — 契约内容更新（重新签署）
      STATUS_CHANGE — 状态流转（DRAFT→SIGNED→FULFILLED/REJECTED）
      FULFILLMENT_CHECK — 履行检查结果
      COMMIT     — 章节提交（最终判定）

    设计原则：
      - 只增不改：insert 一次后不再修改（由业务层保证）
      - 每条记录包含变更前后快照，支持从日志重建历史状态
      - required_nodes/forbidden_zones 等核心字段记录完整快照
    """
    __tablename__ = "contract_audit_logs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)
    contract_id = Column(GUID, ForeignKey("chapter_contracts.id", ondelete="SET NULL"), nullable=True)

    # ── 操作类型 ─────────────────────────────────────────────────
    action = Column(String(30), nullable=False, index=True)
    # CREATE / UPDATE / STATUS_CHANGE / FULFILLMENT_CHECK / COMMIT

    # ── 操作上下文 ────────────────────────────────────────────────
    actor = Column(String(50), nullable=False, default="auto_pipeline")
    # 触发来源：auto_pipeline / user / api / init_service

    # ── 变更快照 ──────────────────────────────────────────────────
    # 操作前状态（nullable，首次 CREATE 为 null）
    old_status = Column(String(20), nullable=True)
    old_required_nodes = Column(JSON, nullable=True)
    old_forbidden_zones = Column(JSON, nullable=True)
    old_constraints = Column(JSON, nullable=True)

    # 变更后状态（CREATE / UPDATE 时有值）
    new_status = Column(String(20), nullable=True)
    new_required_nodes = Column(JSON, nullable=True)
    new_forbidden_zones = Column(JSON, nullable=True)
    new_constraints = Column(JSON, nullable=True)

    # ── 附加信息 ──────────────────────────────────────────────────
    # 操作详情（如履行检查结果、提交判定结果、状态变更原因）
    detail = Column(JSON, nullable=True)

    # 备注
    note = Column(Text, nullable=True)

    # ── 时间 ──────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # 唯一约束：同一 (project_id, chapter_number, action, created_at) 不应重复
    # 索引：(project_id, chapter_number, created_at)
    __table_args__ = (
        {"extend_existing": True},
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "chapter_number": self.chapter_number,
            "contract_id": str(self.contract_id) if self.contract_id else None,
            "action": self.action,
            "actor": self.actor,
            "old_status": self.old_status,
            "old_required_nodes": self.old_required_nodes or [],
            "old_forbidden_zones": self.old_forbidden_zones or [],
            "old_constraints": self.old_constraints or [],
            "new_status": self.new_status,
            "new_required_nodes": self.new_required_nodes or [],
            "new_forbidden_zones": self.new_forbidden_zones or [],
            "new_constraints": self.new_constraints or [],
            "detail": self.detail or {},
            "note": self.note or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
