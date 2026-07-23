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
from app.services.ai_service import AIService
from app.services.extraction_service import ExtractionService

router = APIRouter(prefix="/projects/{project_id}/events", tags=["events"])
ai_service = AIService()
extraction_service = ExtractionService(ai_service)


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