"""
投影写入器 — pipeline 各阶段完成后自动写入记忆。

三类投影：
1. summary_projection  — 章节生成后写入 working layer（近章摘要）
2. state_projection    — 角色状态快照写入 episodic layer
3. memory_projection   — extraction/伏笔事件写入 semantic layer
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_item import MemoryItem
from app.services.memory_store import MemoryStore


class ProjectionWriter:
    """pipeline 投影写入。"""

    def __init__(self, db: AsyncSession, project_id: str):
        self.db = db
        self.project_id = project_id
        self.store = MemoryStore(db, project_id)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    async def write_summary(self, chapter: int, title: str, summary: str) -> bool:
        """章节生成后写入 working memory 摘要。"""
        await self.store.upsert(MemoryItem(
            layer="working",
            category="summary",
            subject=f"ch{chapter}",
            field="title_summary",
            value=f"{title}: {summary}" if summary else title,
            source_chapter=chapter,
            evidence=[f"projection:summary:ch{chapter}"],
        ))
        return True

    async def write_state_snapshot(
        self,
        chapter: int,
        character: str,
        field: str,
        value: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """角色状态变化快照写入 episodic memory。"""
        await self.store.upsert(MemoryItem(
            layer="episodic",
            category="character_state",
            subject=character,
            field=field,
            value=value,
            payload=payload or {},
            source_chapter=chapter,
            evidence=[f"projection:state:ch{chapter}"],
        ))
        return True

    async def write_memory_event(
        self,
        chapter: int,
        category: str,
        subject: str,
        field: str,
        value: str,
        status: str = "active",
    ) -> bool:
        """extraction/伏笔/关系事件写入 semantic memory。"""
        await self.store.upsert(MemoryItem(
            layer="semantic",
            category=category,
            subject=subject,
            field=field,
            value=value,
            status=status,
            source_chapter=chapter,
            evidence=[f"projection:memory:ch{chapter}"],
        ))
        return True

    async def write_open_loop(self, chapter: int, name: str, description: str) -> bool:
        """新伏笔写入 open_loop。"""
        await self.store.upsert(MemoryItem(
            layer="semantic",
            category="open_loop",
            subject=name,
            field="description",
            value=description,
            payload={"status": "active"},
            status="active",
            source_chapter=chapter,
            evidence=[f"projection:open_loop:ch{chapter}"],
        ))
        return True

    async def resolve_open_loop(self, name: str, chapter: int) -> bool:
        """伏笔回收。"""
        await self.store.upsert(MemoryItem(
            layer="semantic",
            category="open_loop",
            subject=name,
            field="status",
            value="resolved",
            payload={"status": "resolved", "resolved_at_chapter": chapter},
            status="resolved",
            source_chapter=chapter,
            evidence=[f"projection:resolve:ch{chapter}"],
        ))
        return True