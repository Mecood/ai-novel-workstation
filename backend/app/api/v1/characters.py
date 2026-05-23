from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.character import Character
from app.schemas.character import CharacterCreate, CharacterResponse

router = APIRouter(prefix="/projects/{project_id}/characters", tags=["characters"])


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