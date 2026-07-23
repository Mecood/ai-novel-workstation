"""
自动事实提取服务 — 从章节正文中提取结构化事件。
流程：LLM 调用 → 10 类事件提取 → 实体消歧 → 写入数据库 → 闭合伏笔 → 更新角色 → 写入知识库
"""
import json
import re
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import AIService
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.foreshadowing import Foreshadowing
from app.models.knowledge import Knowledge
from app.models.story_event import StoryEvent
from app.core.config import settings

EVENT_TYPES = [
    "character_state_changed", "relationship_changed", "world_rule_revealed",
    "power_breakthrough", "artifact_obtained", "promise_created",
    "promise_paid_off", "open_loop_created", "open_loop_closed", "location_changed",
]

EVENT_TYPE_LABELS = {
    "character_state_changed": "角色状态",
    "relationship_changed": "关系变化",
    "world_rule_revealed": "世界观揭示",
    "power_breakthrough": "实力突破",
    "artifact_obtained": "获得道具",
    "promise_created": "埋下伏笔",
    "promise_paid_off": "伏笔回收",
    "open_loop_created": "新悬念",
    "open_loop_closed": "解开悬念",
    "location_changed": "场景转移",
}


class ExtractionService:
    def __init__(self, ai_service: AIService):
        self._ai_service = ai_service

    # ── Public API ──────────────────────────────────────────────────────

    async def extract_events(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        content: str | None = None,
    ) -> dict:
        """对单章正文进行事件提取，写数据库。"""
        # 1) 取正文
        text = content or self._extract_chapter_text(chapter)
        if not text or len(text.strip()) < 50:
            return {"event_count": 0, "character_updates": 0,
                    "foreshadowing_closures": 0, "knowledge_items": 0, "events": [],
                    "message": "章节内容过短，跳过提取"}

        # 2) 调 LLM 提取 10 类事件
        raw_events = await self._call_llm_extract(db, project, chapter.chapter_number, text)

        # 3) 实体消歧：将 events[i].entities 里的角色名映射到 Character.id
        char_map = await self._build_char_name_to_id(db, project.id)
        for ev in raw_events:
            ev["character_ids"] = [
                char_map[n] for n in ev.get("entities", []) if n in char_map
            ]

        # 4) 写入 story_events
        # 4) 写入 story_events
        try:
            saved = await self._save_events(db, project.id, chapter, raw_events)
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
            raise
        # 5) 更新 character 出场记录
        char_updates = await self._update_character_appearances(db, project.id,
                                                                chapter.chapter_number, raw_events)

        # 6) 闭合匹配的伏笔
        closures = await self._auto_close_foreshadowings(db, project.id, chapter.chapter_number,
                                                         raw_events, saved)

        # 7) 写知识库
        kn_items = await self._extract_and_save_knowledge(db, project.id, chapter, text)

        return {
            "event_count": len(saved),
            "character_updates": char_updates,
            "foreshadowing_closures": closures,
            "knowledge_items": kn_items,
            "events": saved,
        }

    async def get_events(
        self, db: AsyncSession, project_id, *,
        chapter_number: int | None = None,
        event_types: list[str] | None = None,
        character_ids: list[str] | None = None,
        offset: int = 0, limit: int = 50,
    ) -> dict:
        """查询已提取事件（不触发 LLM）。"""
        q = select(StoryEvent).where(StoryEvent.project_id == project_id)
        if chapter_number is not None:
            q = q.where(StoryEvent.chapter_number == chapter_number)
        if event_types:
            q = q.where(StoryEvent.event_type.in_(event_types))

        # 总数
        total_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(total_q)).scalar() or 0

        items_q = q.order_by(StoryEvent.chapter_number, StoryEvent.order,
                             StoryEvent.created_at).offset(offset).limit(limit)
        items = (await db.execute(items_q)).scalars().all()

        # SQLite 不原生支持 JSONB overlap，Python 端过滤
        if character_ids:
            filtered = []
            for e in items:
                if any(c in (e.character_ids or []) for c in character_ids):
                    filtered.append(e)
            items = filtered

        return {
            "items": [self._event_to_dict(e) for e in items],
            "total": int(total),
        }

    async def get_timeline(self, db: AsyncSession, project_id,
                           event_types: list[str] | None = None) -> dict:
        """事件时间线数据。"""
        q = select(StoryEvent).where(StoryEvent.project_id == project_id)
        if event_types:
            q = q.where(StoryEvent.event_type.in_(event_types))
        items_q = q.order_by(StoryEvent.chapter_number, StoryEvent.order)
        items = (await db.execute(items_q)).scalars().all()

        chapters = sorted(set(e.chapter_number for e in items))
        counts = [sum(1 for e in items if e.chapter_number == ch) for ch in chapters]
        return {
            "chapters": chapters,
            "events_per_chapter": counts,
            "events": [self._event_to_dict(e) for e in items],
        }

    # ── LLM 调用 ────────────────────────────────────────────────────────

    async def _call_llm_extract(self, db: AsyncSession, project: Project,
                                chapter_number: int, text: str) -> list[dict]:
        system_prompt = (
            "你是一位小说情节结构分析师。请从章节正文中识别并提取情节事件，"
            "用严格的 JSON 数组格式输出。\n\n"
            f"事件类型（10种，严格用以下枚举值）：{EVENT_TYPES}\n\n"
            "每个事件对象必须包含：\n"
            "- event_type: 类型枚举\n"
            "- title: 一句话标题（≤30字）\n"
            "- description: 详细描述（≤150字）\n"
            "- entities: 该事件涉及的角色名/物品名列表\n"
            "- confidence: 0~1 置信度\n"
            "- evidence: 原文证据片段（直接引用）\n"
            "- order: 在章内出现顺序（从1开始）\n\n"
            "仅输出 JSON 数组，不要 markdown 包裹，不要多余文字。"
        )
        user_prompt = (
            f"### 小说名称：{project.name}\n"
            f"### 第 {chapter_number} 章正文（截断到 3000 字）：\n\n"
            f"{text[:3000]}\n\n"
            "请提取事件（如无事件请返回空数组 []）："
        )

        client = await self._ai_service._build_client(db)
        try:
            result = str(await client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=4000,
            ))
            return self._parse_llm_events(result)
        finally:
            await client.close()

    def _parse_llm_events(self, text: str) -> list[dict]:
        text = re.sub(r"```(?:json)?\s*", "", text)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group())
            if not isinstance(data, list):
                return []
            out = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                et = item.get("event_type")
                if et not in EVENT_TYPES:
                    continue
                out.append({
                    "event_type": et,
                    "title": str(item.get("title", ""))[:255],
                    "description": str(item.get("description", ""))[:1000],
                    "entities": item.get("entities") or [],
                    "character_ids": [],
                    "confidence": min(1.0, max(0.0, float(item.get("confidence", 1.0)))),
                    "evidence": str(item.get("evidence", ""))[:1000],
                    "order": int(item.get("order", 0)),
                })
            return out
        except Exception:
            return []

    # ── 实体消歧 ────────────────────────────────────────────────────────

    async def _build_char_name_to_id(self, db: AsyncSession, project_id) -> dict[str, str]:
        """消歧策略：精确匹配 Character.name 或 aliases 内的别名。"""
        result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        chars = result.scalars().all()

        name_to_id: dict[str, str] = {}
        for c in chars:
            if c.name:
                name_to_id[c.name] = str(c.id)
            for alias in (c.aliases or []):
                if alias and alias not in name_to_id:
                    name_to_id[alias] = str(c.id)

        return name_to_id

    # ── 写事件 ──────────────────────────────────────────────────────────

    async def _save_events(self, db: AsyncSession, project_id: str,
                           chapter: Chapter, events: list[dict]) -> list[dict]:
        saved = []
        for ev in events:
            se = StoryEvent(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                chapter_id=chapter.id,
                event_type=ev["event_type"],
                title=ev["title"],
                description=ev["description"],
                entities=ev["entities"],
                character_ids=ev["character_ids"],
                confidence=ev["confidence"],
                evidence=ev["evidence"],
                order=ev["order"],
            )
            db.add(se)
            saved.append(self._event_to_dict(se))
        await db.flush()
        return saved

    def _event_to_dict(self, se: StoryEvent) -> dict:
        return {
            "id": str(se.id),
            "project_id": str(se.project_id),
            "chapter_number": se.chapter_number,
            "event_type": se.event_type,
            "event_type_label": EVENT_TYPE_LABELS.get(se.event_type, se.event_type),
            "title": se.title,
            "description": se.description,
            "entities": se.entities or [],
            "character_ids": se.character_ids or [],
            "confidence": float(se.confidence) if se.confidence is not None else 1.0,
            "evidence": se.evidence,
            "order": se.order,
            "created_at": se.created_at.isoformat() if se.created_at else None,
        }

    # ── 更新角色出场 ────────────────────────────────────────────────────

    async def _update_character_appearances(self, db: AsyncSession, project_id: str,
                                            chapter_number: int, events: list[dict]) -> int:
        char_id_set = set()
        for ev in events:
            char_id_set.update(ev.get("character_ids", []))
        if not char_id_set:
            return 0

        result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.id.in_(list(char_id_set)),
            )
        )
        chars = result.scalars().all()
        updated = 0
        for c in chars:
            fa = c.first_appearance_chapter
            if fa is None or chapter_number < fa:
                c.first_appearance_chapter = chapter_number
            c.last_appearance_chapter = chapter_number
            chaps = c.appearance_chapters or []
            if chapter_number not in chaps:
                chaps.append(chapter_number)
                c.appearance_chapters = chaps
            updated += 1
        return updated

    # ── 自动闭合伏笔 ────────────────────────────────────────────────────

    async def _auto_close_foreshadowings(
        self, db: AsyncSession, project_id: str,
        chapter_number: int, events: list[dict], saved_events: list[dict],
    ) -> int:
        """
        规则：
        - events 中 event_type == 'promise_paid_off' 的事件，
          与 status == 'planted' 的伏笔做子串匹配。
        - 置信度 >= 0.7 才自动闭合。
        """
        paid_off_events = [ev for ev in events if ev["event_type"] == "promise_paid_off"]
        if not paid_off_events:
            return 0

        # 收集已保存事件的 id，按 title+chapter 索引
        saved_index = {}
        for se in saved_events:
            key = (se["title"], se["chapter_number"])
            saved_index[key] = se["id"]

        result = await db.execute(
            select(Foreshadowing).where(
                Foreshadowing.project_id == project_id,
                Foreshadowing.status == "planted",
            )
        )
        foreshadowings = result.scalars().all()

        closed = 0
        for f in foreshadowings:
            f_text = (f.title + " " + (f.description or "")).lower()
            for ev in paid_off_events:
                ev_text = (ev["title"] + " " + (ev["description"] or "")).lower()
                if (f.title and f.title.lower() in ev_text) or (f_text in ev_text and len(f_text) > 4):
                    if float(ev["confidence"]) >= 0.7:
                        f.status = "paid_off"
                        # 尝试关联 event_id
                        key = (ev["title"], chapter_number)
                        if key in saved_index:
                            f.event_id = saved_index[key]
                        f.payoff_chapter = chapter_number
                        f.auto_match_confidence = ev["confidence"]
                        closed += 1
                        break
        return closed

    # ── 写知识库 ────────────────────────────────────────────────────────

    async def _extract_and_save_knowledge(self, db: AsyncSession, project_id: str,
                                          chapter: Chapter, text: str) -> int:
        try:
            items = await self._ai_service.extract_knowledge(db, text, "章节内容")
            count = 0
            for item in items:
                if not item.get("title") or not item.get("content"):
                    continue
                db.add(Knowledge(
                    project_id=project_id,
                    title=item["title"],
                    content=item["content"],
                    category=item.get("category", "event"),
                    tags=item.get("tags", []),
                    source="auto",
                    source_type="chapter",
                    source_id=str(chapter.id),
                ))
                count += 1
            await db.flush()
            return count
        except Exception:
            return 0

    # ── 辅助方法 ────────────────────────────────────────────────────────

    def _extract_chapter_text(self, chapter: Chapter) -> str:
        if isinstance(chapter.content, dict):
            return chapter.content.get("text", json.dumps(chapter.content, ensure_ascii=False))
        if isinstance(chapter.content, str):
            return chapter.content
        return str(chapter.content or "")