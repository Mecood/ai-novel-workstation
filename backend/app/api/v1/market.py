"""
P5D/P5E: Reader Feedback + Deconstruction API
"""
from typing import Annotated
from fastapi import APIRouter, Depends, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.chapter import Chapter
from app.services.market_service import ReaderFeedbackService, DeconstructionService
from app.services.ai_service import AIService

router = APIRouter(prefix="/market", tags=["market"])


@router.post("/reader-feedback/{chapter_id}")
async def reader_feedback(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
):
    """读者模拟——4种读者对本章的反馈"""
    ch = (
        (await db.execute(select(Chapter).where(Chapter.id == chapter_id)))
        .scalars().first()
    )
    if not ch:
        return {"comments": []}

    svc = ReaderFeedbackService(ai_service=AIService())
    comments = await svc.feedback(
        project_name="",
        chapter_number=int(ch.chapter_number),
        chapter_text=str(ch.content) if ch.content is not None else "",
    )
    return {"comments": comments}


@router.post("/deconstruct-text")
async def deconstruct_text(
    novel_text: Annotated[str, Body()],
    novel_title: Annotated[str, Body()] = "目标作品",
):
    """竞品拆解——分析一篇小说的结构"""
    svc = DeconstructionService(ai_service=AIService())
    result = await svc.deconstruct(novel_text, novel_title)
    return result