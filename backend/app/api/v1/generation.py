"""AI generation API routes with SSE streaming."""
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.core.config import settings
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.character import Character
from app.models.chapter import Chapter
from app.services.ai_service import AIService
from app.services.vector_search import VectorSearchService

router = APIRouter(prefix="/projects/{project_id}")
ai_service = AIService()
vector_service = VectorSearchService(
    persist_dir=settings.storage_path,
    siliconflow_api_key=settings.SILICONFLOW_API_KEY or "",
)


def _extract_json(text: str):
    """Extract JSON from AI response, stripping markdown code fences if present."""
    # Strip ```json ... ``` or ``` ... ```
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', text.strip())
    cleaned = re.sub(r'\n?```\s*$', '', cleaned.strip())
    return json.loads(cleaned)


@router.post("/story-core/generate")
async def generate_story_core(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate story core for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    content = await ai_service.generate_story_core(db, project)

    # Update project with story core
    try:
        project.story_core = _extract_json(content)
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
    content = await ai_service.generate_worldview(db, project, story_core_text)

    try:
        parsed = _extract_json(content)
    except (json.JSONDecodeError, ValueError):
        parsed = {"description": content}

    name = parsed.get("name") or f"{project.name or '项目'}的世界观"
    description = (
        parsed.get("description")
        or parsed.get("overview")
        or "暂无描述"
    )
    rules = parsed.get("rules") or []
    timeline = parsed.get("timeline") or []

    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()
    if worldview:
        worldview.name = name
        worldview.description = description
        worldview.rules = rules
        worldview.timeline = timeline
    else:
        worldview = Worldview(
            project_id=project_id,
            name=name,
            description=description,
            rules=rules,
            timeline=timeline,
        )
        db.add(worldview)
    await db.commit()

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
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()

    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    worldview_text = worldview.description if worldview else "暂无世界观设定"

    content = await ai_service.generate_characters(db, project, story_core_text, worldview_text)

    try:
        parsed = _extract_json(content)
    except (json.JSONDecodeError, ValueError):
        parsed = []

    if not isinstance(parsed, list):
        parsed = []

    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    for old in result.scalars().all():
        await db.delete(old)

    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "未命名角色"
        role_type = item.get("role_type") or "supporting"
        personality = item.get("personality")
        background = item.get("background")
        appearance = item.get("appearance")
        relationships = item.get("relationships")
        arc = item.get("arc")
        db.add(Character(
            project_id=project_id,
            name=name,
            role_type=role_type,
            personality=personality,
            background=background,
            appearance=appearance,
            relationships=relationships,
            arc=arc,
        ))
    await db.commit()

    return {"content": content}


@router.post("/chapters/generate")
async def generate_chapter(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream generate a new chapter with semantic context retrieval."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

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

    # Build AI client for vector search
    client = await ai_service._build_client(db)

    # 向量检索：获取与当前章节相关的历史内容（语义搜索）
    vector_context = ""
    try:
        vector_context = await vector_service.get_context_for_chapter(
            project_id, f"第{next_number}章", max_chunks=5,
            use_rerank=bool(settings.SILICONFLOW_API_KEY),
            ai_client=client,
        )
    except Exception:
        vector_context = ""  # Fallback: 向量检索失败不影响章节生成

    await client.close()

    async def event_generator():
        full_content = ""
        async for chunk in ai_service.generate_chapter_stream(
            db, project, next_number, story_core_text,
            worldview_text, characters, chapters, vector_context,
        ):
            full_content += chunk
            yield {"event": "chunk", "data": chunk}

        # Save chapter to database
        chapter = Chapter(
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

    result = await ai_service.check_consistency(db, chapter_text, existing_content)
    return {"content": result}


@router.post("/chapters/{chapter_id}/regenerate")
async def regenerate_chapter(
    project_id: str,
    chapter_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream regenerate an existing chapter in place, replacing its content."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Load target chapter
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

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

    # Get other chapters (exclude the one being regenerated)
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id, Chapter.id != chapter_id)
        .order_by(Chapter.chapter_number.desc())
    )
    other_chapters = list(result.scalars().all())

    story_core_text = json.dumps(project.story_core, ensure_ascii=False) if project.story_core else ""
    worldview_text = worldview.description if worldview else ""
    target_number = chapter.chapter_number

    async def event_generator():
        full_content = ""
        async for chunk in ai_service.generate_chapter_stream(
            db, project, target_number, story_core_text,
            worldview_text, characters, other_chapters,
        ):
            full_content += chunk
            yield {"event": "chunk", "data": chunk}

        # Update chapter content in place
        chapter.content = {"text": full_content}
        chapter.word_count = len(full_content)
        await db.commit()

        yield {"event": "done", "data": json.dumps({
            "chapter_id": str(chapter_id),
            "chapter_number": target_number,
            "word_count": len(full_content),
        })}

    return EventSourceResponse(event_generator())