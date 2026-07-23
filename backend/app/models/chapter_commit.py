import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey, Numeric
from sqlalchemy.sql import func
from app.core.database import Base, GUID
import enum


class CommitStatus(str, enum.Enum):
    ACCEPTED = "accepted"       # 提交通过
    REJECTED = "rejected"       # 提交被拒绝


class ChapterCommit(Base):
    """
    写后提交记录 — 汇总审查结果 + 履行结果 + 提取结果，判定是否通过。
    每次提交生成一条新记录，支持多次提交（同一章可修改后重提交）。
    """
    __tablename__ = "chapter_commits"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)
    chapter_id = Column(GUID, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    contract_id = Column(GUID, ForeignKey("chapter_contracts.id", ondelete="SET NULL"), nullable=True)

    # 提交状态
    status = Column(String(20), nullable=False, default=CommitStatus.REJECTED.value, index=True)

    # 提交版本号（同一章从 1 开始递增）
    commit_version = Column(Integer, nullable=False, default=1)

    # ── 履行结果 ────────────────────────────────────────────────────────
    # ContractService.check_fulfillment() 的输出
    fulfillment_result = Column(JSON, nullable=True, default=dict)
    # 格式：
    # {
    #   "planned_nodes": ["node_001", "node_002", ...],       # 契约中所有 required_nodes 的 id 列表
    #   "covered_nodes": ["node_001", ...],                    # 正文中覆盖到的节点 id
    #   "missed_nodes": ["node_002", ...],                     # 未覆盖的 required_nodes id
    #   "extra_nodes": ["node_005", ...],                      # 正文中出现了但契约未要求的节点 id
    #   "forbidden_violations": ["zone_001", ...],             # 触犯的禁区 id
    #   "summary": "覆盖了 3/4 个核心节点，漏掉了角色情感弧线"  # 文字总结
    # }

    # ── 审查结果（来自 review_reports） ────────────────────────────────
    review_result = Column(JSON, nullable=True, default=dict)
    # 格式：
    # {
    #   "report_id": "uuid",
    #   "overall_score": 7.5,
    #   "blocking_count": 0,
    #   "blocking_issues": ["问题描述"],
    #   "dimension_scores": { "structure": 8.0, "logic": 7.0, ... }
    # }

    # ── 提取结果（来自 story_events） ──────────────────────────────────
    extraction_result = Column(JSON, nullable=True, default=dict)
    # 格式：
    # {
    #   "event_count": 5,
    #   "event_types": ["character_state_changed", "power_breakthrough"],
    #   "events_extracted": true
    # }

    # ── 投影状态（Phase 5 预留） ────────────────────────────────────────
    projection_status = Column(String(20), nullable=True, default=None)
    # 预留：后续版本用，如 "pending", "projected", "skipped"

    # ── 判定详情 ────────────────────────────────────────────────────────
    rejection_reasons = Column(JSON, nullable=True, default=list)
    # 判定被拒绝的原因列表，如：
    # ["blocking_issue: 情节逻辑矛盾", "missed_node: 林动突破地阶"]

    # ── 时间戳 ──────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        {"extend_existing": True},
    )