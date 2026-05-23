from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.worldview import Worldview
from app.schemas.worldview import WorldviewCreate, WorldviewResponse

router = APIRouter(prefix="/projects/{project_id}/worldviews", tags=["worldviews"])


@router.post("", response_model=WorldviewResponse, status_code=201)
async def create_worldview(
    project_id: UUID,
    data: WorldviewCreate,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    worldview = Worldview(
        project_id=project_id,
        name=data.name,
        description=data.description,
        rules=data.rules,
        timeline=data.timeline,
    )
    db.add(worldview)
    await db.commit()
    await db.refresh(worldview)
    return WorldviewResponse.model_validate(worldview)


@router.get("", response_model=list[WorldviewResponse])
async def list_worldviews(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id).order_by(Worldview.created_at.desc())
    )
    worldviews = result.scalars().all()
    return [WorldviewResponse.model_validate(w) for w in worldviews]