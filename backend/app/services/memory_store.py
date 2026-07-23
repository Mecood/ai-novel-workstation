"""
记忆存储服务 — MemoryItem 的 CRUD + 查询 + 冲突检测。

对应裂变创作的 ScratchpadManager + store.py。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.memory_item import MemoryItem


class MemoryStore:
    """记忆条目存储管理器。"""

    def __init__(self, db: AsyncSession, project_id: str):
        self.db = db
        self.project_id = project_id

    # ── 写入 ────────────────────────────────────────────

    async def upsert(self, item: MemoryItem) -> MemoryItem:
        """插入或更新记忆条目。按 (project_id, subject, field, category) 去重。"""
        item.project_id = self.project_id
        now = datetime.now(timezone.utc)
        item.updated_at = now
        if not item.created_at:
            item.created_at = now

        stmt = sqlite_insert(MemoryItem).values(
            id=item.id,
            project_id=item.project_id,
            layer=item.layer,
            category=item.category,
            subject=item.subject,
            field=item.field,
            value=item.value,
            payload=item.payload,
            status=item.status,
            source_chapter=item.source_chapter,
            evidence=item.evidence,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id", "subject", "field", "category"],
            set_={
                "value": item.value,
                "payload": item.payload,
                "status": item.status,
                "source_chapter": item.source_chapter,
                "evidence": item.evidence,
                "updated_at": item.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return item

    async def upsert_many(self, items: list[MemoryItem]) -> int:
        """批量插入/更新。返回写入数量。"""
        count = 0
        for item in items:
            await self.upsert(item)
            count += 1
        return count

    async def mark_outdated(self, subject: str, field: str, category: str) -> int:
        """将指定 key 的旧版本标记为 outdated。返回受影响行数。"""
        result = await self.db.execute(
            select(MemoryItem).where(
                and_(
                    MemoryItem.project_id == self.project_id,
                    MemoryItem.subject == subject,
                    MemoryItem.field == field,
                    MemoryItem.category == category,
                    MemoryItem.status == "active",
                )
            )
        )
        items = result.scalars().all()
        now = datetime.now(timezone.utc)
        for item in items:
            item.status = "outdated"
            item.updated_at = now
        await self.db.commit()
        return len(items)

    # ── 查询 ────────────────────────────────────────────

    async def query(
        self,
        status: str = "active",
        category: Optional[str] = None,
        layer: Optional[str] = None,
        limit: int = 500,
    ) -> list[MemoryItem]:
        """查询记忆条目。"""
        conditions = [MemoryItem.project_id == self.project_id]
        if status:
            conditions.append(MemoryItem.status == status)
        if category:
            conditions.append(MemoryItem.category == category)
        if layer:
            conditions.append(MemoryItem.layer == layer)

        stmt = (
            select(MemoryItem)
            .where(and_(*conditions))
            .order_by(MemoryItem.source_chapter.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def query_active(self, limit: int = 500) -> list[MemoryItem]:
        """查询所有 active 条目。"""
        return await self.query(status="active", limit=limit)

    async def count_by_category(self) -> dict[str, int]:
        """按分类统计条目数。"""
        items = await self.query_active()
        counts: dict[str, int] = {}
        for item in items:
            counts[item.category] = counts.get(item.category, 0) + 1
        return counts

    # ── 冲突检测 ────────────────────────────────────────

    async def conflicts(self) -> list[dict]:
        """检测同一 key 下有多个 active 条目的冲突。"""
        items = await self.query_active()
        by_key: dict[tuple, list[MemoryItem]] = {}
        for item in items:
            key = item.memory_key()
            by_key.setdefault(key, []).append(item)

        conflicts = []
        for key, group in by_key.items():
            if len(group) > 1:
                conflicts.append({
                    "key": list(key),
                    "count": len(group),
                    "items": [i.to_dict() for i in group],
                })
        return conflicts

    # ── 清理 ────────────────────────────────────────────

    async def delete_outdated(self) -> int:
        """删除所有 outdated 条目。返回删除数。"""
        result = await self.db.execute(
            delete(MemoryItem).where(
                and_(
                    MemoryItem.project_id == self.project_id,
                    MemoryItem.status == "outdated",
                )
            )
        )
        await self.db.commit()
        return result.rowcount or 0

    async def delete_by_category(self, category: str) -> int:
        """删除指定分类的全部条目。"""
        result = await self.db.execute(
            delete(MemoryItem).where(
                and_(
                    MemoryItem.project_id == self.project_id,
                    MemoryItem.category == category,
                )
            )
        )
        await self.db.commit()
        return result.rowcount or 0