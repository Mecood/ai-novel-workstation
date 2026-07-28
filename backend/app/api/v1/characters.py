from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db, AsyncSession
from app.models.project import Project
from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterResponse, CharacterUpdate

router = APIRouter(prefix="/projects/{project_id}/characters", tags=["characters"])

@router.get("/arc")
async def character_arc(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """返回项目所有角色的弧线数据。"""
    try:
        from app.services.character_arc_service import get_character_arc
        data = await get_character_arc(db, str(project_id))
    except Exception as e:
        raise HTTPException(500, str(e))
    return data



@router.post("", response_model=CharacterResponse, status_code=201)
async def create_character(
    project_id: UUID,
    data: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    character = Character(
        project_id=project_id,
        name=data.name,
        role_type=data.role_type,
        personality=data.personality,
        background=data.background,
        appearance=data.appearance,
        relationships=data.relationships,
        arc=data.arc,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    try:
        from app.services.pipeline_advancer import PipelineAdvancer
        advancer = PipelineAdvancer(db)
        await advancer.check_and_advance(str(project_id), trigger="character_created")
    except Exception:
        pass
    return CharacterResponse.model_validate(character)


@router.get("", response_model=list[CharacterResponse])
async def list_characters(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Character).where(Character.project_id == project_id).order_by(Character.created_at.desc())
    )
    characters = result.scalars().all()
    return [CharacterResponse.model_validate(c) for c in characters]


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    project_id: UUID,
    character_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.project_id == project_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return CharacterResponse.model_validate(character)


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    project_id: UUID,
    character_id: UUID,
    data: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Character).where(Character.id == character_id, Character.project_id == project_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)

    await db.commit()
    await db.refresh(character)

    # 联动过期检测
    try:
        from app.services.stale_detection_service import check_and_mark_stale
        await check_and_mark_stale(
            db, str(project_id),
            changed_entity="character",
            changed_name=character.name,
        )
    except Exception:
        pass