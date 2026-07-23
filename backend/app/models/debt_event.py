import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Numeric, Text
from sqlalchemy.sql import func
from app.core.database import Base, GUID
import enum


class DebtEventType(str, enum.Enum):
    CREATED = "created"                  # 债务创建
    INTEREST_ACCRUED = "interest_accrued"  # 利息累积
    PARTIAL_PAYMENT = "partial_payment"    # 部分偿还
    FULL_PAYMENT = "full_payment"          # 全额偿还
    OVERDUE = "overdue"                    # 逾期
    CANCELLED = "cancelled"                # 取消
    ADJUSTED = "adjusted"                  # 调整（手动修改）


class DebtEvent(Base):
    __tablename__ = "debt_events"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    debt_id = Column(GUID, ForeignKey("chase_debts.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # 事件类型
    event_type = Column(String(30), nullable=False, index=True)
    # 触发章节号（产生此事件的章节）
    chapter_number = Column(Integer, nullable=False)

    # 事件发生时的金额快照（便于追溯）
    amount_before = Column(Numeric(5, 2), nullable=True)
    amount_after = Column(Numeric(5, 2), nullable=True)
    amount_change = Column(Numeric(5, 2), nullable=True)  # 变化量（正=增加，负=减少）

    # 详细描述
    description = Column(Text, nullable=True)

    # 关联的章节追读力 ID（可选）
    reading_power_id = Column(GUID, ForeignKey("chapter_reading_power.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        {"extend_existing": True},
    )