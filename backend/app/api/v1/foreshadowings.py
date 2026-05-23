from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.foreshadowing import Foreshadowing
from app.models.chapter import Chapter
from app.schemas.foreshadowing import ForeshadowingCreate, ForeshadowingUpdate, ForeshadowingResponse

router = APIRouter(prefix="/projects/{project_id}/foreshadowings", tags=["foreshadowings"])


@router.post("", response_model=ForeshadowingResponse, status_code=201)
async def create_foreshadowing(
    project_id: UUID,
    data: ForeshadowingCreate,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    foreshadowing = Foreshadowing(
        project_id=project_id,
        title=data.title,
        description=data.description,
        target_chapter=data.target_chapter,
        status=data.status,
    )
    db.add(foreshadowing)
    await db.commit()
    await db.refresh(foreshadowing)
    return ForeshadowingResponse.model_validate(foreshadowing)


@router.get("", response_model=list[ForeshadowingResponse])
async def list_foreshadowings(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Foreshadowing)
        .where(Foreshadowing.project_id == project_id)
        .order_by(Foreshadowing.created_at.desc())
    )
    foreshadowings = result.scalars().all()
    return [ForeshadowingResponse.model_validate(f) for f in foreshadowings]


@router.put("/{foreshadowing_id}", response_model=ForeshadowingResponse)
async def update_foreshadowing(
    project_id: UUID,
    foreshadowing_id: UUID,
    data: ForeshadowingUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Foreshadowing).where(
            Foreshadowing.id == foreshadowing_id,
            Foreshadowing.project_id == project_id,
        )
    )
    foreshadowing = result.scalar_one_or_none()
    if not foreshadowing:
        raise HTTPException(status_code=404, detail="Foreshadowing not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(foreshadowing, field, value)

    await db.commit()
    await db.refresh(foreshadowing)
    return ForeshadowingResponse.model_validate(foreshadowing)


@router.get("/unresolved")
async def list_unresolved_foreshadowings(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    max_chapter_result = await db.execute(
        select(func.max(Chapter.chapter_number)).where(Chapter.project_id == project_id)
    )
    max_chapter = max_chapter_result.scalar() or 0

    result = await db.execute(
        select(Foreshadowing)
        .where(
            Foreshadowing.project_id == project_id,
            Foreshadowing.status.in_(["planted", "active"]),
        )
        .order_by(Foreshadowing.target_chapter.asc().nulls_last())
    )
    foreshadowings = result.scalars().all()

    items = []
    overdue_count = 0
    for f in foreshadowings:
        is_overdue = (
            f.target_chapter is not None
            and max_chapter > 0
            and f.target_chapter <= max_chapter
        )
        if is_overdue:
            overdue_count += 1
        items.append({
            "id": str(f.id),
            "title": f.title,
            "description": f.description,
            "target_chapter": f.target_chapter,
            "status": f.status,
            "is_overdue": is_overdue,
        })

    return {
        "count": len(items),
        "overdue": overdue_count,
        "items": items,
    }