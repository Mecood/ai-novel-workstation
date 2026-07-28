"""
P5A: Writing Companion API
"""
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.writing_companion_service import WritingCompanionService, CharacterReminder, ContinueSuggestion, InspirationIdea
from app.services.ai_service import AIService

router = APIRouter(prefix="/companion", tags=["writing-companion"])


@router.get("/char-reminders/{project_id}")
async def char_reminders(
    project_id: str,
    current_chapter: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    """角色出场提醒"""
    svc = WritingCompanionService()
    reminders = await svc.get_char_reminders(db, project_id, current_chapter)
    return {"reminders": [r.__dict__ for r in reminders]}


@router.post("/continue-suggestions")
async def continue_suggestions(
    project_name: Annotated[str, Body()],
    chapter_number: Annotated[int, Body()],
    recent_text: Annotated[str, Body()],
    previous_context: Annotated[str, Body()] = "",
    worldview: Annotated[str, Body()] = "",
    character_list: Annotated[str, Body()] = "",
):
    """续写方向建议"""
    svc = WritingCompanionService(ai_service=AIService())
    suggestions = await svc.get_continue_suggestions(
        project_name=project_name,
        chapter_number=chapter_number,
        recent_text=recent_text,
        previous_context=previous_context,
        worldview=worldview,
        character_list=character_list,
    )
    return {"suggestions": [s.__dict__ for s in suggestions]}


@router.post("/inspirations")
async def inspirations(
    project_name: Annotated[str, Body()],
    chapter_number: Annotated[int, Body()],
    current_scene: Annotated[str, Body()],
    worldview: Annotated[str, Body()] = "",
):
    """灵感推荐"""
    svc = WritingCompanionService(ai_service=AIService())
    ideas = await svc.get_inspirations(
        project_name=project_name,
        chapter_number=chapter_number,
        current_scene=current_scene,
        worldview=worldview,
    )
    return {"ideas": [i.__dict__ for i in ideas]}