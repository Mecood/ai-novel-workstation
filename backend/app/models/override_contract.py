import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from app.core.database import Base, GUID
import enum


class ConstraintType(str, enum.Enum):
    SOFT_HOOK_STRENGTH = "soft_hook_strength"        # 软建议：钩子强度
    SOFT_MICROPAYOFF = "soft_micropayoff"            # 软建议：微兑现密度
    SOFT_COOLPOINT = "soft_coolpoint"                # 软建议：爽点密度
    SOFT_READING_DESIRE = "soft_reading_desire"       # 软建议：阅读欲望


class RationaleType(str, enum.Enum):
    TRANSITIONAL_SETUP = "transitional_setup"          # 过渡章，需要铺垫
    LOGIC_INTEGRITY = "logic_integrity"                # 逻辑完整性优先
    PACING_BALANCE = "pacing_balance"                  # 节奏平衡
    CHARACTER_ARC = "character_arc"                    # 角色弧光需求
    WORLD_BUILDING = "world_building"                  # 世界观铺设
    PLOT_COMPLEXITY = "plot_complexity"                # 情节复杂度
    EMOTIONAL_RESONANCE = "emotional_resonance"        # 情感共鸣优先
    USER_OVERRIDE = "user_override"                    # 用户主动选择


class ContractStatus(str, enum.Enum):
    PENDING = "pending"          # 已签署，等待执行
    FULFILLED = "fulfilled"      # 已履行
    OVERDUE = "overdue"          # 逾期未履行
    CANCELLED = "cancelled"      # 取消


class OverrideContract(Base):
    __tablename__ = "override_contracts"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # 产生合同的章节号
    chapter_number = Column(Integer, nullable=False)

    # 违背的约束类型
    constraint_type = Column(String(30), nullable=False, default=ConstraintType.SOFT_HOOK_STRENGTH.value)
    # 理由类型
    rationale_type = Column(String(30), nullable=False, default=RationaleType.TRANSITIONAL_SETUP.value)
    # 具体理由说明（自由文本，由 LLM 或用户填写）
    rationale_text = Column(Text, nullable=False)

    # 偿还计划描述
    payback_plan = Column(Text, nullable=True)
    # 偿还截止章节号
    due_chapter = Column(Integer, nullable=False)
    # 实际履行章节号
    fulfilled_chapter = Column(Integer, nullable=True)

    # 状态
    status = Column(String(20), nullable=False, default=ContractStatus.PENDING.value, index=True)

    # 是否自动延期（当 due_chapter 到达但未履行时，是否自动延期 5 章）
    auto_extend = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        {"extend_existing": True},
    )