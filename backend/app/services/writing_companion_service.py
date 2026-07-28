"""
P5A: AI 写作伴侣 — Writing Companion Service

三种能力：
1. 续写建议（continue_suggest）— 根据当前文本 + 上下文，推荐 2-3 个走向
2. 灵感推荐（inspiration）— 基于场景，推荐角色互动/反转/冲突点子
3. 角色状态提示（char_reminders）— 提醒哪些角色久未出场、情绪/状态变化
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
from app.models.chapter import Chapter
from app.models.story_event import StoryEvent

# ── 输出类型 ─────────────────────────────────────────

@dataclass
class ContinueSuggestion:
    direction: str           # "继续当前情节" / "转折" / "切换视角"
    text: str                # AI 续写建议文本
    reasoning: str           # 为什么推荐这个方向

@dataclass
class InspirationIdea:
    category: str            # "角色互动" / "反转" / "冲突" / "悬念"
    concept: str             # 核心点子
    scene_suggestion: str    # 建议如何融入当前场景

@dataclass
class CharacterReminder:
    character_name: str
    last_seen_chapter: int
    status_note: str         # "3章未出场，张力在累积" / "情绪方向不一致" 等
    severity: str            # "info" / "warn" / "urgent"

@dataclass
class WritingCompanionResult:
    continues: list[ContinueSuggestion] = field(default_factory=list)
    inspirations: list[InspirationIdea] = field(default_factory=list)
    char_reminders: list[CharacterReminder] = field(default_factory=list)


class WritingCompanionService:
    """AI 写作伴侣"""

    def __init__(self, ai_service=None):
        self.ai = ai_service

    # ── 纯逻辑（不需要 AI）───────────────────────────────────

    async def get_char_reminders(
        self, db: AsyncSession, project_id: str, current_chapter: int,
    ) -> list[CharacterReminder]:
        """检查角色状态，返回提醒"""
        characters = [
                            c for c in 
                            ((await db.execute(
                                select(Character).where(Character.project_id == project_id)
                            )).scalars().all())
                        ]

        reminders: list[CharacterReminder] = []
        for c in characters:
            # 查找该角色最后一次出现的事件
            events = (
                (await db.execute(
                    select(StoryEvent).where(
                        StoryEvent.project_id == project_id,
                        StoryEvent.character_ids.like(f'%"{c.id}"%'),
                    ).order_by(StoryEvent.created_at.desc()).limit(1)
                ))
                .scalars().all()
            )

            if not events:
                reminders.append(CharacterReminder(
                    character_name=str(c.name),
                    last_seen_chapter=0,
                    status_note=f"{c.name} 尚未在任何事件中出现",
                    severity="warn",
                ))
                continue

            last_ch = events[0].chapter_id
            # 取 chapter_number
            last_ch_row = (
                (await db.execute(
                    select(Chapter.chapter_number).where(Chapter.id == last_ch)
                ))
                .scalars().first()
            )

            gap = current_chapter - (last_ch_row or 0)
            if gap >= 3:
                reminders.append(CharacterReminder(
                    character_name=str(c.name),
                    last_seen_chapter=last_ch_row or 0,
                    status_note=f"已 {gap} 章未出场，上次在第{last_ch_row}章",
                    severity="urgent" if gap >= 5 else "warn",
                ))
            elif gap == 2:
                reminders.append(CharacterReminder(
                    character_name=str(c.name),
                    last_seen_chapter=last_ch_row or 0,
                    status_note=f"上一章未出场，读者可能想念{c.name}",
                    severity="info",
                ))

        return reminders

    # ── AI 驱动的能力 ────────────────────────────────────

    async def get_continue_suggestions(
        self, project_name: str, chapter_number: int,
        recent_text: str, previous_context: str,
        worldview: str = "", character_list: str = "",
    ) -> list[ContinueSuggestion]:
        """生成续写方向建议"""
        if not self.ai:
            return []

        prompt = f"""你是小说创作顾问。根据以下信息，为当前章节推荐 2-3 个继续写作的方向。

作品：{project_name}
当前正在写第{chapter_number}章
已有剧情概要：
{previous_context[:800]}

当前角色：
{character_list[:500]}

最近写的内容（当前的最后部分）：
{recent_text[-1500:]}

请据此推荐 2-3 个合理的继续发展方向。严格按照以下 JSON 格式输出：
```json
[
  {{"direction": "简述方向", "text": "具体建议内容（几句话）", "reasoning": "推荐理由"}}
]
```

只输出纯 JSON，不要包含任何解释、标题或注释。"""

        try:
            result = await self.ai.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
            )
            data = self._parse_json(result)
            return [
                ContinueSuggestion(**item) for item in data
                if all(k in item for k in ("direction", "text", "reasoning"))
            ]
        except Exception:
            return []

    async def get_inspirations(
        self, project_name: str, chapter_number: int,
        current_scene: str, worldview: str,
    ) -> list[InspirationIdea]:
        """灵感推荐：基于场景点子"""
        if not self.ai:
            return []

        prompt = f"""你是小说创意顾问。用户正在创作《{project_name}》第{chapter_number}章。

当前场景描述：
{current_scene}

世界观背景：
{worldview[:1000]}

请推荐 2-3 个激发灵感的点子，帮助推动当前场景或制造意外的情节发展。
点子的类型可选：角色互动、反转、冲突、悬念。

严格按照以下 JSON 格式输出：
```json
[
  {{"genre_id": "角色互动", "concept": "一句话点子", "context_suggestion": "具体怎么写"}}
]
```
```"""

        try:
            result = await self.ai.chat(
                system="只输出纯 JSON，不要任何解释。每个点子控制在 100 字以内。",
                messages=[{"role":"user","content":prompt}],
                temperature=0.95,
            )
            data = self._parse_json(result)
            return [
                InspirationIdea(**item) for item in data
                if all(k in item for k in ("genre_id", "concept", "context_suggestion"))
            ]
        except Exception:
            return []

    def _parse_json(self, text: str):
        """安全解析 JSON"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text)