"""
记忆条目模型 — 裂变创作 MemoryItem 的 SQLAlchemy 适配。

三层记忆架构：
- working:  大纲+近章摘要+角色状态 — 直接注入 prompt
- episodic: 状态变化+关系变化+出场记录 — 近期情节上下文
- semantic: 长期事实（世界观/角色/伏笔/知识）— 按优先级预算筛选
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class _JsonColumn:
    """自定义 JSON 列 — 在 SQLite 中以 TEXT 存储，Python dict/list 透明序列化。"""

    def __init__(self):
        self.column = Column(Text, nullable=False, default="{}")

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        raw = obj.__dict__.get(self.column.name, "{}")
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return {}

    def __set__(self, obj, value):
        if value is None:
            obj.__dict__[self.column.name] = "{}"
        elif isinstance(value, str):
            obj.__dict__[self.column.name] = value
        else:
            obj.__dict__[self.column.name] = json.dumps(value, ensure_ascii=False)


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), nullable=False)
    layer = Column(String(16), nullable=False, server_default="semantic")
    category = Column(String(32), nullable=False, server_default="story_fact")
    subject = Column(String(128), nullable=False, server_default="")
    field = Column(String(128), nullable=False, server_default="")
    value = Column(Text, nullable=False, server_default="")

    payload = Column(Text, nullable=False, server_default="{}")
    evidence = Column(Text, nullable=False, server_default="[]")

    status = Column(String(16), nullable=False, server_default="active")
    source_chapter = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # 优先级映射
    CATEGORY_PRIORITY = {
        "world_rule": 0,
        "character_state": 1,
        "relationship": 2,
        "story_fact": 3,
        "open_loop": 4,
        "reader_promise": 5,
        "timeline": 6,
        "summary": 7,
        "state_snapshot": 7,
    }

    def __init__(self, **kwargs):
        # 显式设置默认值
        kwargs.setdefault("id", str(uuid.uuid4()))
        kwargs.setdefault("layer", "semantic")
        kwargs.setdefault("category", "story_fact")
        kwargs.setdefault("subject", "")
        kwargs.setdefault("field", "")
        kwargs.setdefault("value", "")
        kwargs.setdefault("status", "active")
        kwargs.setdefault("source_chapter", 0)
        # 序列化为 TEXT
        if isinstance(kwargs.get("payload"), (dict, list)):
            kwargs["payload"] = json.dumps(kwargs["payload"], ensure_ascii=False)
        if isinstance(kwargs.get("evidence"), (dict, list)):
            kwargs["evidence"] = json.dumps(kwargs["evidence"], ensure_ascii=False)
        for key, val in kwargs.items():
            setattr(self, key, val)

    @property
    def priority(self) -> int:
        return self.CATEGORY_PRIORITY.get(self.category, 99)

    def get_payload(self):
        """安全读取 payload（反序列化）。"""
        raw = getattr(self, "payload", "{}")
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_evidence(self):
        """安全读取 evidence（反序列化）。"""
        raw = getattr(self, "evidence", "[]")
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "layer": self.layer,
            "category": self.category,
            "subject": self.subject,
            "field": self.field,
            "value": self.value,
            "payload": self.get_payload(),
            "status": self.status,
            "source_chapter": self.source_chapter,
            "evidence": self.get_evidence(),
        }

    def memory_key(self) -> tuple:
        """去重键：同 subject+field+category 视为同一记忆条目"""
        return (self.subject, self.field, self.category)