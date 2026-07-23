"""
L0-L3 渐进式上下文压缩服务。

为 AI 章节生成提供分级上下文，在预算内最大化有用信息。
压缩规则：
  L0: 近 5 章全文保留
  L1: 6-10 章前 → 300 字摘要 + 新实体
  L2: 11-20 章前 → 100 字摘要 + 角色状态变化
  L3: 20 章以上 → 关键事实列表（境界/伏笔/能力）
"""
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.story_event import StoryEvent
from app.models.character import Character
from app.models.foreshadowing import Foreshadowing
from app.models.review_report import ReviewReport
from app.models.chapter_commit import ChapterCommit


class ContextLevel(str, Enum):
    L0 = "l0"  # 全文（最近 5 章）
    L1 = "l1"  # 300 字摘要 + 新实体（6-10 章）
    L2 = "l2"  # 100 字摘要 + 角色状态（11-20 章）
    L3 = "l3"  # 关键事实列表（20 章以上）


# 每层预算
LEVEL_BUDGETS: dict[ContextLevel, int] = {
    ContextLevel.L0: 2000,   # 每章全文 ≈ 2000 token
    ContextLevel.L1: 400,    # 300 字摘要 + 实体 ≈ 400 token
    ContextLevel.L2: 200,    # 100 字摘要 + 状态 ≈ 200 token
    ContextLevel.L3: 100,    # 关键事实 ≈ 100 token
}

# 章节范围定义
L0_SPAN = 5    # 最近 5 章全文
L1_SPAN = 5    # 再往前 5 章摘要
L2_SPAN = 10   # 再往前 10 章极简摘要
# L3: 剩下的所有章节


async def build_compressed_context(
    db: AsyncSession,
    project_id: str,
    target_chapter: int,
    max_tokens: int = 4000,
) -> str:
    """
    按 L0→L1→L2→L3 顺序构建上下文，预算不超过 max_tokens。

    返回格式化的上下文文本，直接注入到 AI prompt 中。
    """
    # 获取所有已完成的章节（按编号降序）
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id, Chapter.status == "generated")
        .order_by(Chapter.chapter_number.desc())
    )
    chapters = result.scalars().all()

    if not chapters:
        return ""

    # 按距离目标章节的远近分组
    l0_chapters = []  # 最近 5 章
    l1_chapters = []  # 6-10 章前
    l2_chapters = []  # 11-20 章前
    l3_chapters = []  # 21+ 章前

    for ch in chapters:
        distance = target_chapter - ch.chapter_number
        if distance <= 0:
            continue  # 跳过目标章节及以后的章节
        if distance <= L0_SPAN:
            l0_chapters.append(ch)
        elif distance <= L0_SPAN + L1_SPAN:
            l1_chapters.append(ch)
        elif distance <= L0_SPAN + L1_SPAN + L2_SPAN:
            l2_chapters.append(ch)
        else:
            l3_chapters.append(ch)

    # 按编号升序排列（让上下文按时间顺序排列）
    l0_chapters.sort(key=lambda c: c.chapter_number)
    l1_chapters.sort(key=lambda c: c.chapter_number)
    l2_chapters.sort(key=lambda c: c.chapter_number)
    l3_chapters.sort(key=lambda c: c.chapter_number)

    parts = []
    budget_used = 0

    # L0：全文
    if l0_chapters and budget_used < max_tokens:
        l0_text = await _build_l0(db, l0_chapters)
        l0_tokens = _estimate_tokens(l0_text)
        if budget_used + l0_tokens <= max_tokens:
            parts.append(l0_text)
            budget_used += l0_tokens
        else:
            # 预算不够，截断
            allowed = max_tokens - budget_used
            if allowed > 200:
                l0_text = _truncate_text(l0_text, allowed)
                parts.append(l0_text)
                budget_used += allowed

    # L1：摘要 + 该章引入的新实体
    if l1_chapters and budget_used < max_tokens:
        l1_text = await _build_l1(db, l1_chapters, project_id)
        l1_tokens = _estimate_tokens(l1_text)
        if budget_used + l1_tokens <= max_tokens:
            parts.append(l1_text)
            budget_used += l1_tokens
        else:
            allowed = max_tokens - budget_used
            if allowed > 100:
                parts.append(_truncate_text(l1_text, allowed))
                budget_used += allowed

    # L2：极简摘要 + 角色状态变化
    if l2_chapters and budget_used < max_tokens:
        l2_text = await _build_l2(db, l2_chapters, project_id)
        l2_tokens = _estimate_tokens(l2_text)
        if budget_used + l2_tokens <= max_tokens:
            parts.append(l2_text)
            budget_used += l2_tokens
        else:
            allowed = max_tokens - budget_used
            if allowed > 50:
                parts.append(_truncate_text(l2_text, allowed))
                budget_used += allowed

    # L3：关键事实
    if l3_chapters and budget_used < max_tokens:
        l3_text = await _build_l3(db, project_id)
        l3_tokens = _estimate_tokens(l3_text)
        if budget_used + l3_tokens <= max_tokens:
            parts.append(l3_text)
            budget_used += l3_tokens
        else:
            allowed = max_tokens - budget_used
            if allowed > 30:
                parts.append(_truncate_text(l3_text, allowed))
                budget_used += allowed

    return "\n\n".join(parts)


async def _build_l0(db: AsyncSession, chapters: list[Chapter]) -> str:
    """L0：近 5 章全文。"""
    lines = []
    for ch in chapters:
        content = _extract_text(ch)
        summary = ch.summary or ""
        lines.append(
            f"### 第{ch.chapter_number}章 {ch.title}\n"
            f"摘要：{summary}\n"
            f"正文：\n{content[:2000]}"
        )
    return "【最近章节全文】\n" + "\n\n".join(lines)


async def _build_l1(db: AsyncSession, chapters: list[Chapter], project_id: str) -> str:
    """L1：300 字摘要 + 该章引入的新实体。"""
    lines = []
    for ch in chapters:
        summary = (ch.summary or "")[:300]
        # 该章引入的 StoryEvent 中的新实体
        events_result = await db.execute(
            select(StoryEvent)
            .where(
                StoryEvent.project_id == project_id,
                StoryEvent.chapter_number == ch.chapter_number,
            )
            .order_by(StoryEvent.order)
        )
        events = events_result.scalars().all()
        entities = []
        for ev in events:
            for e in (ev.entities or []):
                if e not in entities:
                    entities.append(e)

        line = f"第{ch.chapter_number}章 {ch.title}：{summary}"
        if entities:
            line += f"\n  新出现/重要实体：{', '.join(entities[:10])}"
        lines.append(line)
    return "【早期章节摘要】\n" + "\n".join(lines)


async def _build_l2(db: AsyncSession, chapters: list[Chapter], project_id: str) -> str:
    """L2：100 字摘要 + 角色状态变化。"""
    # 获取所有角色名
    char_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    chars = char_result.scalars().all()
    char_map = {str(c.id): c.name for c in chars}

    lines = []
    for ch in chapters:
        summary = (ch.summary or "")[:100]

        # 该章角色状态变化事件
        events_result = await db.execute(
            select(StoryEvent)
            .where(
                StoryEvent.project_id == project_id,
                StoryEvent.chapter_number == ch.chapter_number,
                StoryEvent.event_type.in_([
                    "character_state_changed", "power_breakthrough",
                    "relationship_changed",
                ])
            )
        )
        events = events_result.scalars().all()
        state_changes = []
        for ev in events:
            names = [char_map.get(cid, cid) for cid in (ev.character_ids or [])]
            if names:
                state_changes.append(f"{'、'.join(names)}: {ev.title}")

        line = f"第{ch.chapter_number}章 {ch.title}：{summary}"
        if state_changes:
            line += "\n  " + "\n  ".join(state_changes[:5])
        lines.append(line)
    return "【较早章节概览】\n" + "\n".join(lines)


async def _build_l3(db: AsyncSession, project_id: str) -> str:
    """L3：关键事实列表（角色境界/已回收伏笔/已升级能力）。"""
    facts = []

    # 角色当前状态
    char_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    for c in char_result.scalars().all():
        if c.name:
            if c.last_appearance_chapter:
                facts.append(f"角色「{c.name}」最后出场于第{c.last_appearance_chapter}章")
            if c.arc:
                facts.append(f"「{c.name}」角色弧线：{c.arc[:100]}")

    # 已回收的伏笔
    fs_result = await db.execute(
        select(Foreshadowing)
        .where(
            Foreshadowing.project_id == project_id,
            Foreshadowing.status == "paid_off",
        )
        .order_by(Foreshadowing.payoff_chapter.desc())
        .limit(20)
    )
    for f in fs_result.scalars().all():
        facts.append(
            f"伏笔回收：{f.title}（第{f.payoff_chapter}章）"
        )

    # 最近的 ReviewReport 给出的关键 blocking 问题
    rr_result = await db.execute(
        select(ReviewReport)
        .where(ReviewReport.project_id == project_id)
        .order_by(ReviewReport.created_at.desc())
        .limit(1)
    )
    rr = rr_result.scalar_one_or_none()
    if rr and rr.blocking_count > 0:
        facts.append(
            f"最近审查发现 {rr.blocking_count} 个 blocking 问题，"
            f"综合评分 {rr.overall_score}"
        )

    if not facts:
        return ""

    return "【全局关键事实】\n" + "\n".join(facts)


def _extract_text(chapter: Chapter) -> str:
    """从章节中提取纯文本。"""
    if isinstance(chapter.content, dict):
        return chapter.content.get("text", "")
    return str(chapter.content or "")


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文字符 ≈ 1.5 token，英文 ≈ 1 token）。"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 0.4)


def _truncate_text(text: str, max_tokens: int) -> str:
    """按 token 预算截断文本。"""
    if _estimate_tokens(text) <= max_tokens:
        return text
    # 按字符数粗略截断
    ratio = max_tokens / max(_estimate_tokens(text), 1)
    cut = int(len(text) * ratio)
    return text[:cut] + "\n\n[后续内容已截断]"