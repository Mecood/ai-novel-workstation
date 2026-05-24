"""Vector search API routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.models.project import Project
from app.models.chapter import Chapter
from app.services.vector_search import VectorSearchService
from app.services.ai_service import AIService

router = APIRouter(prefix="/projects/{project_id}/search", tags=["search"])

ai_service = AIService()
vector_service = VectorSearchService(
    persist_dir=settings.storage_path,
    siliconflow_api_key=settings.SILICONFLOW_API_KEY or "",
)


class SearchQuery(BaseModel):
    query: str
    top_k: int = 5
    use_rerank: bool = True


class SearchResponse(BaseModel):
    results: list[dict]
    total: int


@router.post("", response_model=SearchResponse)
async def search_content(
    project_id: str,
    data: SearchQuery,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Semantic search across story content with optional reranking."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Build AI client
    client = await ai_service._build_client(db)
    try:
        if data.use_rerank and settings.SILICONFLOW_API_KEY:
            results = await vector_service.search_with_rerank(
                project_id, data.query, top_k=data.top_k, ai_client=client
            )
        else:
            results = await vector_service.search(
                project_id, data.query, top_k=data.top_k, ai_client=client
            )
    finally:
        await client.close()

    return SearchResponse(results=results, total=len(results))


@router.get("/context")
async def get_context(
    project_id: str,
    topic: str = Query(..., description="Chapter topic for context retrieval"),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Get semantic context for chapter generation."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    client = await ai_service._build_client(db)
    try:
        context = await vector_service.get_context_for_chapter(
            project_id, topic, max_chunks=5,
            use_rerank=bool(settings.SILICONFLOW_API_KEY),
            ai_client=client,
        )
    finally:
        await client.close()

    return {"context": context}


@router.post("/index/{content_type}", status_code=201)
async def index_content(
    project_id: str,
    content_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Index story content into vector store."""
    valid_types = {"chapters", "worldview", "characters"}
    if content_type not in valid_types:
        raise HTTPException(400, f"Invalid content type, must be one of: {valid_types}")

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    client = await ai_service._build_client(db)
    try:
        indexed = 0

        if content_type == "chapters":
            result = await db.execute(
                select(Chapter).where(Chapter.project_id == project_id)
            )
            chapters = list(result.scalars().all())
            for ch in chapters:
                text = ch.content.get("text", "") if isinstance(ch.content, dict) else str(ch.content)
                if text:
                    await vector_service.add_content(
                        project_id, text,
                        {"chapter": ch.chapter_number, "title": ch.title, "type": "chapter"},
                        ai_client=client,
                    )
                    indexed += 1

        elif content_type == "worldview":
            from app.models.worldview import Worldview
            result = await db.execute(
                select(Worldview).where(Worldview.project_id == project_id)
            )
            worldview = result.scalar_one_or_none()
            if worldview and worldview.description:
                await vector_service.add_content(
                    project_id, worldview.description,
                    {"chapter": 0, "title": "世界观设定", "type": "worldview"},
                    ai_client=client,
                )
                indexed = 1

        elif content_type == "characters":
            from app.models.character import Character
            result = await db.execute(
                select(Character).where(Character.project_id == project_id)
            )
            characters = list(result.scalars().all())
            for c in characters:
                text = f"角色名：{c.name}\n角色类型：{c.role_type}\n背景设定：{c.background}\n性格特点：{c.personality}"
                if c.arc:
                    text += f"\n成长弧：{c.arc}"
                await vector_service.add_content(
                    project_id, text,
                    {"chapter": 0, "title": c.name, "type": "character", "role_type": c.role_type},
                    ai_client=client,
                )
                indexed += 1

        return {"indexed": indexed, "content_type": content_type}

    finally:
        await client.close()