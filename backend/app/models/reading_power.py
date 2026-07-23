import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Numeric, Boolean, Text
from sqlalchemy.sql import func
from app.core.database import Base, GUID
import enum


class HookType(str, enum.Enum):
    CLIFFHANGER = "cliffhanger"          # 悬念断章（"他推开门，看到了……"）
    QUESTION = "question"                # 疑问断章（"那个人到底是谁？"）
    REVELATION = "revelation"            # 反转/揭示（"原来真相是……"）
    CRISIS = "crisis"                    # 危机降临（"一把剑已经刺到眼前"）
    EMOTIONAL = "emotional"              # 情感冲击（"她转身离去，再也没有回头"）
    ACTION = "action"                    # 战斗高潮
    PROMISE = "promise"                  # 预告（"三天后，决战之巅"）
    NONE = "none"                        # 无钩子


class HookStrength(str, enum.Enum):
    STRONG = "strong"      # 强烈的阅读欲望（8-10分）
    MEDIUM = "medium"      # 中等（5-7分）
    WEAK = "weak"          # 较弱（0-4分）


class ChapterReadingPower(Base):
    __tablename__ = "chapter_reading_power"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)

    # 追读力综合评分（0-10，由 LLM 评估得出）
    reading_power_score = Column(Numeric(4, 2), nullable=False, default=5.0)

    # 章末钩子类型
    hook_type = Column(String(30), nullable=True, default=HookType.NONE.value)
    # 钩子强度
    hook_strength = Column(String(10), nullable=True, default=HookStrength.WEAK.value)
    # 钩子描述（LLM 给出的一句话描述）
    hook_description = Column(Text, nullable=True)

    # 爽点模式列表（如 ["战斗突破", "仇人吃瘪", "获得宝物"]）
    coolpoint_patterns = Column(JSON, default=list)
    # 微兑现列表（如 ["小伏笔回收", "对话透露信息"]）
    micropayoffs = Column(JSON, default=list)

    # 是否为过渡章
    is_transition = Column(Boolean, default=False)
    # 过渡章说明（为什么需要过渡）
    transition_note = Column(Text, nullable=True)

    # 当前债务余额（该章产生债务 + 历史债务在该章的快照）
    debt_balance = Column(Numeric(5, 2), default=0.0)

    # LLM 评估原文（原始 JSON 响应）
    evaluation_raw = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        {"extend_existing": True},
    )