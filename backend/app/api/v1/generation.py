"""AI generation API routes with SSE streaming."""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.models.project import Project
from app.services.ai_service import AIService

router = APIRouter(prefix="/projects/{project_id}")
ai_service = AIService()


@router.post("/story-core/generate")
async def generate_story_core(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate story core for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    
    content = await ai_service.generate_story_core(project)
    
    # Update project with story core
    try:
        project.story_core = json.loads(content)
    except json.JSONDecodeError:
        project.story_core = {"raw": content}
    await db.commit()
    
    return {"content": content}


@router.post("/worldview/generate")
async def generate_worldview(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate worldview for a project."""
    project = await db.get(Project, project_id)
    if not project or not project.story_core:
        raise HTTPException(404, "Project or story core not found")
    
    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    content = await ai_service.generate_worldview(project, story_core_text)
    
    return {"content": content}


@router.post("/characters/generate")
async def generate_characters(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate characters for a project."""
    project = await db.get(Project, project_id)
    if not project or not project.story_core:
        raise HTTPException(404, "Project or story core not found")
    
    # Get or generate worldview
    from sqlalchemy import select
    from app.models.worldview import Worldview
    
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()
    
    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    worldview_text = worldview.description if worldview else "暂无世界观设定"
    
    content = await ai_service.generate_characters(project, story_core_text, worldview_text)
    
    return {"content": content}


@router.post("/chapters/generate")
async def generate_chapter(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream generate a new chapter."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    
    # Gather context
    from sqlalchemy import select
    from app.models.worldview import Worldview
    from app.models.character import Character
    from app.models.chapter import Chapter
    
    # Get worldview
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()
    
    # Get characters
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = list(result.scalars().all())
    
    # Get existing chapters
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.desc())
    )
    chapters = list(result.scalars().all())
    next_number = (chapters[0].chapter_number + 1) if chapters else 1
    
    story_core_text = json.dumps(project.story_core, ensure_ascii=False) if project.story_core else ""
    worldview_text = worldview.description if worldview else ""
    
    async def event_generator():
        full_content = ""
        async for chunk in ai_service.generate_chapter_stream(
            project, next_number, story_core_text,
            worldview_text, characters, chapters,
        ):
            full_content += chunk
            yield {"event": "chunk", "data": chunk}
        
        # Save chapter to database
        from app.models.chapter import Chapter as ChapterModel
        chapter = ChapterModel(
            project_id=project_id,
            chapter_number=next_number,
            title=f"第{next_number}章",
            content={"text": full_content},
            summary="",
            word_count=len(full_content),
            status="generated",
        )
        db.add(chapter)
        await db.commit()
        
        yield {"event": "done", "data": json.dumps({
            "chapter_number": next_number,
            "word_count": len(full_content),
        })}
    
    return EventSourceResponse(event_generator())


@router.post("/consistency/check")
async def check_consistency(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Check consistency of the latest chapter against existing content."""
    from sqlalchemy import select
    from app.models.chapter import Chapter
    from app.models.worldview import Worldview
    from app.models.character import Character
    
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    
    # Get latest chapter
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.desc())
        .limit(1)
    )
    latest_chapter = result.scalar_one_or_none()
    if not latest_chapter:
        raise HTTPException(400, "No chapters to check")
    
    # Get all chapters
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.asc())
    )
    all_chapters = list(result.scalars().all())
    
    # Get worldview and characters for context
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()
    
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = list(result.scalars().all())
    
    # Build existing content summary
    existing_content = []
    if project.story_core:
        existing_content.append({"type": "story_core", "data": project.story_core})
    if worldview:
        existing_content.append({"type": "worldview", "data": worldview.description})
    for c in characters:
        existing_content.append({"type": "character", "data": c.name, "details": c.background})
    for ch in all_chapters[:-1]:  # Exclude the latest
        existing_content.append({"type": "chapter", "number": ch.chapter_number, "summary": ch.summary})
    
    chapter_text = latest_chapter.content.get("text", "") if isinstance(latest_chapter.content, dict) else str(latest_chapter.content)
    
    result = await ai_service.check_consistency(chapter_text, existing_content)
    return {"content": result}