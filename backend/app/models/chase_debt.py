import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Numeric, Text
from sqlalchemy.sql import func
from app.core.database import Base, GUID
import enum


class DebtType(str, enum.Enum):
    HOOK_STRENGTH = "hook_strength"        # 章末钩子强度不足
    MICROPAYOFF = "micropayoff"            # 缺乏微兑现（爽点密度不足）
    COOLPOINT = "coolpoint"                # 缺乏爽点/高潮
    READING_DESIRE = "reading_desire"       # 整体阅读欲望不足


class DebtStatus(str, enum.Enum):
    ACTIVE = "active"          # 活跃中，持续计息
    PARTIAL = "partial"        # 已部分偿还
    PAID = "paid"              # 已全额偿还
    OVERDUE = "overdue"        # 逾期
    CANCELLED = "cancelled"    # 取消（如合同覆盖后手动取消）


class ChaseDebt(Base):
    __tablename__ = "chase_debts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # 债务类型
    debt_type = Column(String(30), nullable=False, default=DebtType.HOOK_STRENGTH.value)
    # 债务描述（如"第3章钩子强度不足：章末无悬念留白"）
    description = Column(Text, nullable=True)

    # 初始债务量（0~10 的评分差，如 10-4.5=5.5）
    original_amount = Column(Numeric(5, 2), nullable=False, default=0.0)
    # 当前债务量（含利息，初始=original_amount）
    current_amount = Column(Numeric(5, 2), nullable=False, default=0.0)
    # 利息率（每章，默认 0.1 = 10%）
    interest_rate = Column(Numeric(3, 2), nullable=False, default=Decimal("0.10"))

    # 产生债务的章节号
    source_chapter = Column(Integer, nullable=False)
    # 截止章节号（预期还清章节，可选）
    due_chapter = Column(Integer, nullable=True)
    # 实际还清章节号
    paid_chapter = Column(Integer, nullable=True)

    # 状态
    status = Column(String(20), nullable=False, default=DebtStatus.ACTIVE.value, index=True)

    # 关联的 Override Contract ID（可选，当债务由合同覆盖时）
    contract_id = Column(GUID, ForeignKey("override_contracts.id", ondelete="SET NULL"), nullable=True)

    # 元数据（扩展字段，如 LLM 评估原文）
    extra_meta = Column("extra_meta", JSON, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {"extend_existing": True},
    )