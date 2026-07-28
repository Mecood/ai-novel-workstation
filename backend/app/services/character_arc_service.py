"""
Character Arc Service — 从 StoryEvent 提取角色弧线数据。

遍历所有章节的事件，按角色聚合出 appearance/power/emotion/relationship 序列。
纯数据库查询，不调用外部 AI。
"""
from __future__ import annotations
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
from app.models.story_event import StoryEvent


EMOTION_KEYWORDS_POS = {"revelation", "joy", "love", "victory", "triumph"}
EMOTION_KEYWORDS_NEG = {"grief", "fear", "betrayal", "loss", "death", "betrayal"}
POWER_KEYWORDS = {"power_gained", "upgrade", "training", "awaken"}
REL_KEYWORDS = {"relationship", "bond", "conflict", "ally"}


def _compute_emotion(events: list[dict]) -> int:
    """简单情绪值：正关键词 +1 每个，负关键词 -1 每个，夹在 1-10。"""
    score = 5
    for e in events:
        tt = str(e.get("event_type", "")).lower()
        title = str(e.get("title", "")).lower()
        combined = tt + " " + title
        for kw in EMOTION_KEYWORDS_POS:
            if kw in combined: score += 1
        for kw in EMOTION_KEYWORDS_NEG:
            if kw in combined: score -= 1
    return max(1, min(10, score))


def _compute_power(events: list[dict]) -> int:
    """能力值：1-10，每有关键词增长 1。"""
    score = 3
    for e in events:
        tt = str(e.get("event_type", "")).lower()
        for kw in POWER_KEYWORDS:
            if kw in tt: score += 1
            break
    return max(1, min(10, score))


def _compute_relationship_density(events: list[dict]) -> int:
    """关系密度：涉及其他角色数。"""
    connected = set()
    for e in events:
        char_ids = e.get("character_ids", []) or []
        connected.update(str(x) for x in char_ids)
    return max(1, len(connected))


async def get_character_arc(
    db: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    """返回项目所有角色的弧线数据。"""
    char_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters: list[Character] = list(char_result.scalars())

    if not characters:
        return {"characters": []}

    char_ids = [str(c.id) for c in characters]

    event_result = await db.execute(
        select(StoryEvent)
        .where(StoryEvent.project_id == project_id)
        .order_by(StoryEvent.chapter_number.asc(), StoryEvent.order.asc())
    )
    events = list(event_result.scalars())

    character_arc_list: list[dict[str, Any]] = []

    for char in characters:
        char_id = str(char.id)
        # 找该角色相关的事件
        char_events = []
        for ev in events:
            cid_set = set(str(x) for x in (ev.character_ids or []))
            if char_id in cid_set:
                char_events.append({
                    "chapter": ev.chapter_number,
                    "event_type": ev.event_type,
                    "title": ev.title,
                    "character_ids": ev.character_ids or [],
                })

        # fallback：如果任何事件都没有匹配到角色，把所有章节的事件均匀分配
        if not char_events and events:
            total_chars = len(characters)
            for ev in events:
                if ev.chapter_number % total_chars == characters.index(char):
                    char_events.append({
                        "chapter": ev.chapter_number,
                        "event_type": ev.event_type,
                        "title": ev.title,
                        "character_ids": ev.character_ids or [],
                    })

        # 按章节排序
        chapters_seen = sorted(set(e["chapter"] for e in char_events))

        arc = []
        for ch_num in chapters_seen:
            ch_events = [e for e in char_events if e["chapter"] == ch_num]
            arc.append({
                "chapter": ch_num,
                "appearance": 1,
                "emotion": _compute_emotion(ch_events),
                "power": _compute_power(ch_events),
                "relationships": _compute_relationship_density(ch_events),
            })

        issues: list[dict] = []
        # 检查：连续章节数 > 2 无变化
        if len(arc) >= 3:
            last_chapter = arc[-1]["chapter"]
            max_chapter_all = max(e.chapter_number for e in events) if events else last_chapter
            gap = max_chapter_all - last_chapter
            if gap >= 3:
                issues.append({
                    "type": "abandoned",
                    "msg": f"已 {gap} 章未出现，考虑交代去向",
                    "chapter": last_chapter,
                })

        character_arc_list.append({
            "id": char_id,
            "name": char.name or "",
            "role_type": char.role_type or "",
            "arc": arc,
            "issues": issues,
        })

    return {"characters": character_arc_list}
