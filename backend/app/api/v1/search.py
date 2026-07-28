"""Simple text search API routes — pure SQLite LIKE matching, no AI/embeddings."""

import pathlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.services.simple_search import SimpleSearchService

router = APIRouter(prefix="/projects/{project_id}/search", tags=["search"])

# ── Resolve the same SQLite file path used by the async engine ──────────────
_backend_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent
_db_path = str(_backend_dir / "novel_workstation.db")
simple_search = SimpleSearchService(db_path=_db_path)


class SearchQuery(BaseModel):
    query: str
    top_k: int = 5


class SearchResponse(BaseModel):
    results: list[dict]
    total: int


@router.post("", response_model=SearchResponse)
async def search_content(
    project_id: str,
    data: SearchQuery,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Full-text search across chapters, characters, worldview, and knowledge."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    results = simple_search.search(project_id, data.query, top_k=data.top_k)
    return SearchResponse(results=results, total=len(results))


@router.get("/context")
async def get_context(
    project_id: str,
    topic: str = Query(..., description="Chapter topic for context retrieval"),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Get keyword-match context for chapter generation."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    context = simple_search.get_context_for_chapter(
        project_id, topic, max_chunks=5
    )
    return {"context": context}


@router.post("/index/{content_type}", status_code=201)
async def index_content(
    project_id: str,
    content_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Index story content into search store. With simple search this is a
    no-op stub — content is searched directly from the database tables. We
    return the article count for compatibility with the frontend."""
    valid_types = {"chapters", "worldview", "characters", "knowledge"}
    if content_type not in valid_types:
        raise HTTPException(400, f"Invalid content type, must be one of: {valid_types}")

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    from sqlalchemy import select

    indexed = 0
    if content_type == "chapters":
        from app.models.chapter import Chapter
        result = await db.execute(
            select(Chapter).where(Chapter.project_id == project_id)
        )
        indexed = len(result.scalars().all())
    elif content_type == "characters":
        from app.models.character import Character
        result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        indexed = len(result.scalars().all())
    elif content_type == "worldviews":
        from app.models.worldview import Worldview
        result = await db.execute(
            select(Worldview).where(Worldview.project_id == project_id)
        )
        indexed = len(result.scalars().all())
    elif content_type == "knowledges":
        from app.models.knowledge import Knowledge
        result = await db.execute(
            select(Knowledge).where(Knowledge.project_id == project_id)
        )
        indexed = len(result.scalars().all())

    return {"indexed": indexed, "content_type": content_type}