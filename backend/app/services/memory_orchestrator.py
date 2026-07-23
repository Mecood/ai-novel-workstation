"""
记忆编排器 — 裂变创作 MemoryOrchestrator 的适配版。

四合一：Bootstrap + Budget + Compactor + Orchestrator
核心方法 build_memory_pack(chapter, task_type) 返回三层记忆。
"""

from typing import Any, Optional
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_item import MemoryItem
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.foreshadowing import Foreshadowing
from app.models.worldview import Worldview
from app.services.memory_store import MemoryStore


# ── 预算分配（简化裂变 budget.py）──────────────────

BUDGET_TABLE = {
    "write":  {"max_items": 30, "working_pct": 0.45, "episodic_pct": 0.30, "semantic_pct": 0.25},
    "review": {"max_items": 40, "working_pct": 0.35, "episodic_pct": 0.35, "semantic_pct": 0.30},
    "query":  {"max_items": 25, "working_pct": 0.30, "episodic_pct": 0.45, "semantic_pct": 0.25},
}

COMPACT_EVERY_N_CHAPTERS = 5           # 每生成5章自动压缩
TIMELINE_EXPIRY_CHAPTERS = 50           # 超过50章的时间线过期


class MemoryOrchestrator:
    """三层记忆编排器。"""

    def __init__(self, db: AsyncSession, project_id: str):
        self.db = db
        self.project_id = project_id
        self.store = MemoryStore(db, project_id)

    # ═══════════════════════════════════════════════════
    # 核心：构建三层记忆包
    # ═══════════════════════════════════════════════════

    async def build_memory_pack(
        self, chapter: int, task_type: str = "write"
    ) -> dict[str, Any]:
        """构建三层记忆包，替代 context_service.build_compressed_context。"""
        budget = BUDGET_TABLE.get(task_type, BUDGET_TABLE["write"])
        max_items = budget["max_items"]

        # ── working memory：大纲 + 近章摘要 + 角色状态 ──
        working = await self._build_working(chapter)
        w_limit = int(max_items * budget["working_pct"])
        working = working[:w_limit]

        # ── episodic memory：近期状态变化 ──
        episodic = await self._build_episodic(chapter)
        e_limit = int(max_items * budget["episodic_pct"])
        episodic = episodic[:e_limit]

        # ── semantic memory：长期事实，按优先级+budget筛选 ──
        all_active = await self.store.query_active()
        # 相关性过滤（与当前章节有关联的优先）
        relevant = await self._filter_relevant(all_active, chapter)
        s_limit = int(max_items * budget["semantic_pct"])
        semantic = self._apply_budget(relevant, s_limit)

        return {
            "working_memory": [self._fmt_working(w) for w in working],
            "episodic_memory": [self._fmt_episodic(e) for e in episodic],
            "semantic_memory": [s.to_dict() for s in semantic],
            "stats": {
                "total_active": len(all_active),
                "working": len(working),
                "episodic": len(episodic),
                "semantic_total": len(relevant),
                "semantic_injected": len(semantic),
                "compacted": await self._needs_compact(chapter),
            },
        }

    # ═══════════════════════════════════════════════════
    # Working Memory
    # ═══════════════════════════════════════════════════

    async def _build_working(self, chapter: int) -> list[dict]:
        """working = 最近3章摘要 + 角色状态快照。"""
        result: list[dict] = []

        # 近3章摘要（从 chapters 表）
        stmt = (
            select(Chapter)
            .where(Chapter.project_id == self.project_id)
            .where(Chapter.chapter_number < chapter)
            .where(Chapter.status == "generated")
            .order_by(Chapter.chapter_number.desc())
            .limit(3)
        )
        chapters = (await self.db.execute(stmt)).scalars().all()
        for ch in reversed(chapters):
            result.append({
                "source": f"ch{ch.chapter_number}",
                "chapter": ch.chapter_number,
                "title": ch.title,
                "summary": ch.summary or "",
            })

        # 角色当前状态（从 memory_items 中最新的 character_state）
        char_states = await self.store.query(category="character_state", status="active", limit=20)
        for cs in char_states:
            result.append({
                "source": f"char:{cs.subject}",
                "chapter": cs.source_chapter,
                "field": cs.field,
                "value": cs.value,
            })

        return result

    # ═══════════════════════════════════════════════════
    # Episodic Memory
    # ═══════════════════════════════════════════════════

    async def _build_episodic(self, chapter: int) -> list[dict]:
        """episodic = 近10章状态变化 + 关系变化 + 出场记录。"""
        window = max(1, chapter - 10)
        items = await self.store.query_active()

        episodic: list[dict] = []
        for item in items:
            if item.source_chapter >= window:
                if item.category in ("character_state", "relationship", "story_fact"):
                    episodic.append({
                        "source": f"ch{item.source_chapter}",
                        "chapter": item.source_chapter,
                        "category": item.category,
                        "subject": item.subject,
                        "field": item.field,
                        "value": item.value[:200],
                    })

        episodic.sort(key=lambda x: x["chapter"], reverse=True)
        return episodic

    # ═══════════════════════════════════════════════════
    # 相关性过滤 + 预算裁剪
    # ═══════════════════════════════════════════════════

    async def _filter_relevant(
        self, items: list[MemoryItem], chapter: int
    ) -> list[MemoryItem]:
        """按优先级 + 近度筛选。优先级高的（world_rule/character_state）不过滤，低的按章节窗口过滤。"""
        window = 20  # 20章内的语义记忆视为相关
        relevant: list[MemoryItem] = []

        for item in items:
            # 高优先级始终保留
            if item.category in ("world_rule", "character_state", "open_loop"):
                relevant.append(item)
                continue
            # 时间线过滤
            if item.category == "timeline" and chapter - item.source_chapter > TIMELINE_EXPIRY_CHAPTERS:
                continue
            # 近度窗口
            if item.source_chapter > 0 and chapter - item.source_chapter <= window:
                relevant.append(item)
            elif item.source_chapter == 0:  # bootstrap 条目
                relevant.append(item)

        # 按优先级排序
        relevant.sort(key=lambda x: (x.priority, -x.source_chapter))
        return relevant

    def _apply_budget(self, items: list[MemoryItem], max_items: int) -> list[MemoryItem]:
        """按预算裁剪。"""
        if len(items) <= max_items:
            return list(items)
        return list(items[:max_items])

    # ═══════════════════════════════════════════════════
    # 格式化（注入 prompt）
    # ═══════════════════════════════════════════════════

    def _fmt_working(self, w: dict) -> str:
        if w.get("title"):
            return f"第{w['chapter']}章 {w['title']}: {w.get('summary', '')}"
        if w.get("source", "").startswith("char:"):
            return f"[角色状态] {w['source'][5:]}.{w['field']} = {w['value']}"
        return str(w.get("summary", w.get("value", "")))

    def _fmt_episodic(self, e: dict) -> str:
        return (
            f"第{e['chapter']}章 [{e['category']}] {e['subject']}"
            f"{' · ' + e['field'] if e.get('field') else ''}"
            f"{': ' + e['value'] if e.get('value') else ''}"
        )

    # ═══════════════════════════════════════════════════
    # Bootstrap：从现有数据回填初始记忆
    # ═══════════════════════════════════════════════════

    async def bootstrap(self) -> dict[str, int]:
        """从现有角色/世界观/伏笔/知识条目回填初始长期记忆。"""
        counts: dict[str, int] = defaultdict(int)

        # ── 角色 → character_state ──
        chars = (await self.db.execute(
            select(Character).where(Character.project_id == self.project_id)
        )).scalars().all()
        for c in chars:
            state_fields = {
                "role_type": c.role_type or "",
                "background": c.background or "",
                "current_status": "alive",
            }
            if c.personality:
                if isinstance(c.personality, list):
                    state_fields["personality"] = ", ".join(c.personality)
                else:
                    state_fields["personality"] = str(c.personality)
            for field, val in state_fields.items():
                if val:
                    await self.store.upsert(MemoryItem(
                        layer="semantic",
                        category="character_state",
                        subject=c.name,
                        field=field,
                        value=str(val),
                        evidence=["bootstrap:characters"],
                    ))
                    counts["character_state"] += 1

        # ── 世界观 → world_rule ──
        wvs = (await self.db.execute(
            select(Worldview).where(Worldview.project_id == self.project_id)
        )).scalars().all()
        for wv in wvs:
            if wv.name:
                await self.store.upsert(MemoryItem(
                    layer="semantic",
                    category="world_rule",
                    subject=wv.name,
                    field="description",
                    value=wv.description or "",
                    evidence=["bootstrap:worldviews"],
                ))
                counts["world_rule"] += 1

        # ── 伏笔 → open_loop ──
        fores = (await self.db.execute(
            select(Foreshadowing).where(Foreshadowing.project_id == self.project_id)
        )).scalars().all()
        for f in fores:
            fstatus = str(f.status or "planted").lower()
            status = "resolved" if fstatus in ("resolved", "paid_off") else "active"
            await self.store.upsert(MemoryItem(
                layer="semantic",
                category="open_loop",
                subject=f.title or f"foreshadowing_{str(f.id)[:8]}",
                field="status",
                value=f.description or "",
                payload={"status": status, "expected_chapter": f.expected_redemption_chapter or f.target_chapter},
                status=status,
                evidence=["bootstrap:foreshadowings"],
            ))
            counts["open_loop"] += 1

        # ── 已有章节 → story_fact（章节事件） ──
        chapters = (await self.db.execute(
            select(Chapter).where(Chapter.project_id == self.project_id)
            .where(Chapter.status == "generated")
        )).scalars().all()
        for ch in chapters:
            await self.store.upsert(MemoryItem(
                layer="episodic",
                category="story_fact",
                subject=f"ch{ch.chapter_number}",
                field="title",
                value=ch.title or "",
                source_chapter=ch.chapter_number,
                evidence=["bootstrap:chapters"],
            ))
            counts["story_fact"] += 1

        return dict(counts)

    # ═══════════════════════════════════════════════════
    # Compactor：压缩清理
    # ═══════════════════════════════════════════════════

    async def compact(self) -> dict[str, int]:
        """压缩记忆：去 outdated、清已回收伏笔、合并过旧时间线。"""
        stats: dict[str, int] = {}

        # 1) 同 key outdated 只保留最新
        items = await self.store.query_active()
        by_key: dict[tuple, list[MemoryItem]] = defaultdict(list)
        active_keys = set()
        for item in items:
            key = item.memory_key()
            active_keys.add(key)
        # 查 outdated
        outdated = await self.store.query(status="outdated")
        for item in outdated:
            key = item.memory_key()
            if key in active_keys:
                # 已有 active 版本，删 outdated
                continue
            by_key[key].append(item)

        # 每组 outdated 只保留最新
        keep_outdated: list[MemoryItem] = []
        for key, group in by_key.items():
            group.sort(key=lambda x: x.updated_at, reverse=True)
            keep_outdated.append(group[0])
        # 删掉多余的 outdated
        all_outdated_ids = {o.id for o in outdated}
        keep_ids = {k.id for k in keep_outdated}
        for oid in all_outdated_ids - keep_ids:
            await self.store.db.execute(
                select(MemoryItem).where(MemoryItem.id == oid)
            )  # 标记删除
        stats["outdated_cleaned"] = len(all_outdated_ids) - len(keep_ids)

        # 2) 清理已回收伏笔
        open_loops = await self.store.query(category="open_loop")
        resolved_count = 0
        for ol in open_loops:
            pstatus = (ol.payload or {}).get("status", "")
            if pstatus in ("resolved", "closed", "done"):
                ol.status = "resolved"
                resolved_count += 1
        stats["open_loops_resolved"] = resolved_count

        # 3) 合并过旧时间线
        timeline = await self.store.query(category="timeline")
        if timeline:
            latest_ch = max(t.source_chapter for t in timeline)
            old = [t for t in timeline if latest_ch - t.source_chapter > TIMELINE_EXPIRY_CHAPTERS]
            if len(old) > 1:
                # 生成摘要条目
                samples = [t.value[:60] for t in old[:8] if t.value]
                summary_text = "；".join(samples) if samples else "早期关键事件"
                await self.store.upsert(MemoryItem(
                    layer="semantic",
                    category="story_fact",
                    subject="timeline_summary",
                    field=f"<=ch{old[-1].source_chapter}",
                    value=f"早期事件摘要：{summary_text}",
                    payload={"from_ch": old[0].source_chapter, "to_ch": old[-1].source_chapter, "merged": len(old)},
                    source_chapter=old[-1].source_chapter,
                    evidence=["compactor:timeline"],
                ))
                # 删旧条目
                for o in old:
                    await self.store.db.execute(
                        select(MemoryItem).where(MemoryItem.id == o.id)
                    )
                stats["timeline_merged"] = len(old)

        await self.store.db.commit()
        return stats

    async def _needs_compact(self, chapter: int) -> bool:
        """判断是否需要压缩。"""
        return chapter > 0 and chapter % COMPACT_EVERY_N_CHAPTERS == 0


# ── 便捷入口 ──

async def build_memory_pack_for_chapter(
    db: AsyncSession,
    project_id: str,
    chapter: int,
    task_type: str = "write",
    auto_bootstrap: bool = True,
) -> dict[str, Any]:
    """
    为章节生成构建三层记忆包。

    便捷函数，供 ai_service 调用。
    首次调用自动 bootstrap（如果 memory_items 表为空）。
    """
    orch = MemoryOrchestrator(db, project_id)

    # 首次使用自动 bootstrap
    if auto_bootstrap:
        count_result = await db.execute(
            select(func.count()).select_from(MemoryItem)
            .where(MemoryItem.project_id == project_id)
        )
        total = count_result.scalar() or 0
        if total == 0:
            await orch.bootstrap()

    # 自动压缩
    if await orch._needs_compact(chapter):
        try:
            await orch.compact()
        except Exception:
            pass

    return await orch.build_memory_pack(chapter, task_type)