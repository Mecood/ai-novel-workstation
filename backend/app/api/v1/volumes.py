from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.volume import Volume
from app.schemas.volume import VolumeCreate, VolumeUpdate, VolumeResponse

router = APIRouter(prefix="/projects/{project_id}/volumes", tags=["volumes"])


async def _ensure_project(db: AsyncSession, project_id: UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[VolumeResponse])
async def list_volumes(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await _ensure_project(db, project_id)
    result = await db.execute(
        select(Volume)
        .where(Volume.project_id == project_id)
        .order_by(Volume.volume_number.asc())
    )
    volumes = result.scalars().all()
    return [VolumeResponse.model_validate(v) for v in volumes]


@router.post("", response_model=VolumeResponse, status_code=201)
async def create_volume(
    project_id: UUID,
    data: VolumeCreate,
    db: AsyncSession = Depends(get_db),
):
    await _ensure_project(db, project_id)

    volume_number = data.volume_number
    if volume_number is None:
        max_result = await db.execute(
            select(func.max(Volume.volume_number)).where(Volume.project_id == project_id)
        )
        current_max = max_result.scalar() or 0
        volume_number = current_max + 1

    volume = Volume(
        project_id=project_id,
        volume_number=volume_number,
        title=data.title,
        description=data.description,
        chapter_start=data.chapter_start,
        chapter_end=data.chapter_end,
        highlight_rhythm=data.highlight_rhythm,
        emotion_arc=data.emotion_arc,
        foreshadowing_notes=data.foreshadowing_notes,
        twists=data.twists,
    )
    db.add(volume)
    await db.commit()
    await db.refresh(volume)
    return VolumeResponse.model_validate(volume)


@router.put("/{volume_id}", response_model=VolumeResponse)
async def update_volume(
    project_id: UUID,
    volume_id: UUID,
    data: VolumeUpdate,
    db: AsyncSession = Depends(get_db),
):
    await _ensure_project(db, project_id)

    result = await db.execute(
        select(Volume).where(Volume.id == volume_id, Volume.project_id == project_id)
    )
    volume = result.scalar_one_or_none()
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(volume, field, value)

    await db.commit()
    await db.refresh(volume)
    return VolumeResponse.model_validate(volume)


@router.delete("/{volume_id}", status_code=204)
async def delete_volume(
    project_id: UUID,
    volume_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await _ensure_project(db, project_id)

    result = await db.execute(
        select(Volume).where(Volume.id == volume_id, Volume.project_id == project_id)
    )
    volume = result.scalar_one_or_none()
    if not volume:
        raise HTTPException(status_code=404, detail="Volume not found")

    await db.delete(volume)
    await db.commit()
