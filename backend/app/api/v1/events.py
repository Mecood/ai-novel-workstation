"""Story event extraction API routes."""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.story_event import StoryEvent
from app.services.ai_service import AIService
from app.services.extraction_service import ExtractionService

router = APIRouter(prefix="/projects/{project_id}/events", tags=["events"])
ai_service = AIService()
extraction_service = ExtractionService(ai_service)

from pydantic import BaseModel


class EventUpdate(BaseModel):
    order: int | None = None
    timeline_track: str | None = None


# ── 1) 触发提取（SSE 流） ───────────────────────────────────────────────
@router.post("/{chapter_number}/extract")
async def trigger_extract(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """对第 {chapter_number} 章触发事件提取，返回 SSE 流。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    chapter = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id,
                              Chapter.chapter_number == chapter_number)
    ).scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    async def event_stream():
        try:
            yield {"data": json.dumps({"type": "progress",
                                       "message": f"开始分析第 {chapter_number} 章..."})}
            result = await extraction_service.extract_events(db, project, chapter)
            await db.commit()
            yield {"data": json.dumps({"type": "complete", "data": result})}
        except Exception as e:
            yield {"data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


# ── 2) 事件列表（分页 + 筛选） ──────────────────────────────────────────
@router.get("")
async def list_events(
    project_id: UUID,
    chapter: int | None = Query(None, description="按章节号筛选"),
    event_type: str | None = Query(None, description="按事件类型筛选"),
    character_id: str | None = Query(None, description="按角色 ID 筛选"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return await extraction_service.get_events(
        db, project_id,
        chapter_number=chapter,
        event_types=[event_type] if event_type else None,
        character_ids=[character_id] if character_id else None,
        offset=offset,
        limit=limit,
    )


# ── 3) 事件时间线 ───────────────────────────────────────────────────────
@router.get("/timeline")
async def get_timeline(
    project_id: UUID,
    event_type: str | None = Query(None, description="按类型筛选"),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return await extraction_service.get_timeline(
        db, project_id,
        event_types=[event_type] if event_type else None,
    )


# ── 4) 角色相关事件 ─────────────────────────────────────────────────────
@router.get("/characters/{character_id}/events")
async def get_character_events(
    project_id: UUID,
    character_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return await extraction_service.get_events(
        db, project_id,
        character_ids=[character_id],
        offset=offset,
        limit=limit,
    )


# ── 5) 关系图谱数据（P2） ─────────────────────────────────────────────
@router.get("/relationships")
async def get_relationships(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    关系图谱数据：从 relationship_changed 事件构建角色关系时间线。

    返回结构：
    {
        "nodes": [{"id": "uuid", "name": "林渊", "role_type": "主角"}],
        "edges": [
            {
                "source_id": "uuid_a", "target_id": "uuid_b",
                "source_name": "林渊", "target_name": "苏瑶",
                "relationship": "师徒",
                "chapter": 5,
                "description": "苏瑶收林渊为徒",
                "created_at": "..."
            }
        ],
        "timeline": [
            {"chapter": 3, "event": "林渊与苏瑶相遇", "description": "..."}
        ]
    }
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    project_id_str = str(project_id)

    # 1) 取所有角色 → 节点列表
    chars = (await db.execute(
        select(Character).where(Character.project_id == project_id)
    )).scalars().all()
    nodes = [
        {"id": str(c.id), "name": c.name, "role_type": c.role_type}
        for c in chars
    ]

    # 2) 取所有 relationship_changed 事件
    rel_events = (await db.execute(
        select(StoryEvent)
        .where(
            StoryEvent.project_id == project_id,
            StoryEvent.event_type == "relationship_changed",
        )
        .order_by(StoryEvent.chapter_number, StoryEvent.order)
    )).scalars().all()

    # 3) 构建 edges：每个事件的 entities 两两配对
    char_id_set = {str(c.id) for c in chars}
    edges = []
    timeline = []
    for ev in rel_events:
        entities = ev.entities or []
        char_ids = ev.character_ids or []
        # 优先用 character_ids；退回到 entities
        involved_ids = [c for c in char_ids if c in char_id_set] or \
                       [str(c.id) for c in chars if c.name in entities]
        if len(involved_ids) >= 2:
            for i, src in enumerate(involved_ids[:2]):
                tgt = involved_ids[i + 1]
                if src == tgt:
                    continue
                edges.append({
                    "source_id": src,
                    "target_id": tgt,
                    "source_name": next((n["name"] for n in nodes if n["id"] == src), src),
                    "target_name": next((n["name"] for n in nodes if n["id"] == tgt), tgt),
                    "relationship": ev.title or "关系变化",
                    "chapter": ev.chapter_number,
                    "description": ev.description or "",
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                })
        timeline.append({
            "chapter": ev.chapter_number,
            "event": ev.title or "",
            "description": ev.description or "",
            "entities": entities,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "timeline": timeline,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


# ── 6) 更新事件（order / timeline_track） ──────────────────────────────
@router.patch("/{event_id}")
async def update_event(
    project_id: UUID,
    event_id: UUID,
    body: EventUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    event = await db.get(StoryEvent, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.project_id != project_id:
        raise HTTPException(403, "Event does not belong to this project")
    if body.order is not None:
        event.order = body.order
    if body.timeline_track is not None:
        event.timeline_track = body.timeline_track
    await db.commit()
    await db.refresh(event)
    return extraction_service._event_to_dict(event)