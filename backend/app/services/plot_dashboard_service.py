"""
Plot Dashboard Service — 剧情复盘看板数据聚合。

从 StoryEvent + Foreshadowing 提取：
- protagonist_goal_journey: 主角目标演变序列
- subplot_health: 副线进展评分
- key_events: 关键事件里程碑
"""
from __future__ import annotations
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.story_event import StoryEvent
from app.models.foreshadowing import Foreshadowing


EVENT_TYPES_MILESTONE = {
    "open_loop_created", "promise_paid_off", "character_entered",
    "character_left", "revelation", "conflict_escalated",
}


async def get_plot_dashboard(
    db: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    """返回剧情复盘看板数据结构。"""
    # 获取所有事件
    ev_result = await db.execute(
        select(StoryEvent)
        .where(StoryEvent.project_id == project_id)
        .order_by(StoryEvent.chapter_number.asc(), StoryEvent.order.asc())
    )
    events = list(ev_result.scalars())

    # 获取所有伏笔
    fs_result = await db.execute(
        select(Foreshadowing)
        .where(Foreshadowing.project_id == project_id)
    )
    foreshadowings = list(fs_result.scalars())

    max_chapter = max((e.chapter_number for e in events), default=1)

    # ── 关键事件里程碑 ──
    key_events: list[dict[str, Any]] = []
    for ev in events:
        if ev.event_type in EVENT_TYPES_MILESTONE:
            key_events.append({
                "chapter": ev.chapter_number,
                "event": ev.title or "",
                "event_type": ev.event_type,
                "type_label": ev.event_type,
            })

    # ── 主角目标演变 ──
    # 用 open_loop_created 类事件作为目标节点
    goal_events = [e for e in events if e.event_type == "open_loop_created"]
    goal_journey = []
    for ev in goal_events[:8]:  # 限制到前 8 个
        goal_journey.append({
            "chapter": ev.chapter_number,
            "goal": ev.title or "",
            "goal_type": ("original" if goal_events
                         and ev.chapter_number == min(ge.chapter_number for ge in goal_events)
                         else "current"),
        })
    if goal_journey and goal_journey[-1]["goal_type"] == "original":
        goal_journey[-1]["goal_type"] = "current"

    # ── 副线健康度 ──
    # 从伏笔的状态分组，按 chapter 推断活跃度
    subplot_health: list[dict[str, Any]] = []
    fs_by_type: dict[str, list[Foreshadowing]] = {}
    for fs in foreshadowings:
        key = fs.status or "unknown"
        fs_by_type.setdefault(key, []).append(fs)

    for status, items in fs_by_type.items():
        if not items:
            continue
        last_chapter = max(
            (f.payoff_chapter or f.target_chapter or f.evidence_chapter or 0)
            for f in items
        )
        # 评分：距离最新章节越近越健康
        score = max(1, 10 - (max_chapter - last_chapter))
        status_label = {
            "planted": "active",
            "paid_off": "resolved",
            "abandoned": "abandoned",
            "overdue": "overdue",
        }.get(status, status)
        subplot_health.append({
            "name": f"伏笔组 ({status})",
            "last_chapter": last_chapter,
            "score": min(10, max(1, score)),
            "status": status_label,
        })

    # 如果没伏笔数据，从事件类型推断主副线
    if not subplot_health:
        event_types_count: dict[str, int] = {}
        for ev in events:
            et = ev.event_type or "other"
            event_types_count[et] = event_types_count.get(et, 0) + 1
        for et, cnt in sorted(event_types_count.items(), key=lambda x: -x[1])[:5]:
            subplot_health.append({
                "name": f"事件类型: {et}",
                "last_chapter": max(
                    (e.chapter_number for e in events if e.event_type == et),
                    default=0,
                ),
                "score": min(10, cnt),
                "status": "active" if et in EVENT_TYPES_MILESTONE else "background",
            })

    return {
        "project_id": project_id,
        "total_chapters": max_chapter,
        "total_events": len(events),
        "protagonist_goal_journey": goal_journey,
        "subplot_health": subplot_health,
        "key_events": key_events,
    }
