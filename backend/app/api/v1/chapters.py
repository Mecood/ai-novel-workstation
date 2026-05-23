from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.schemas.chapter import ChapterCreate, ChapterUpdate, ChapterResponse

router = APIRouter(prefix="/projects/{project_id}/chapters", tags=["chapters"])


@router.post("", response_model=ChapterResponse, status_code=201)
async def create_chapter(
    project_id: UUID,
    data: ChapterCreate,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapter = Chapter(
        project_id=project_id,
        chapter_number=data.chapter_number,
        title=data.title,
        content=data.content,
        summary=data.summary,
        outline_detail=data.outline_detail,
        word_count=data.word_count,
        status=data.status,
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)


@router.get("", response_model=list[ChapterResponse])
async def list_chapters(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.asc())
    )
    chapters = result.scalars().all()
    return [ChapterResponse.model_validate(c) for c in chapters]


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    project_id: UUID,
    chapter_id: UUID,
    data: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chapter, field, value)

    await db.commit()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)


@router.delete("/{chapter_id}", status_code=204)
async def delete_chapter(
    project_id: UUID,
    chapter_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    await db.delete(chapter)
    await db.commit()


@router.get("/previous-summary")
async def get_previous_summary(
    project_id: UUID,
    current_chapter: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(Chapter).where(Chapter.project_id == project_id)
    if current_chapter is not None:
        query = query.where(Chapter.chapter_number < current_chapter)
    query = query.order_by(Chapter.chapter_number.asc())

    result = await db.execute(query)
    chapters = result.scalars().all()

    completed = [
        ch for ch in chapters
        if ch.summary and ch.summary.strip()
    ]

    if not completed:
        return {"summary": None, "chapter_count": 0}

    parts = [
        f"### 第{ch.chapter_number}章 {ch.title}\n\n{ch.summary.strip()}"
        for ch in completed
    ]
    summary_text = "\n\n".join(parts)

    return {"summary": summary_text, "chapter_count": len(completed)}