from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.knowledge import Knowledge
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse

router = APIRouter(prefix="/projects/{project_id}/knowledges", tags=["knowledges"])


@router.post("", response_model=KnowledgeResponse, status_code=201)
async def create_knowledge(
    project_id: UUID,
    data: KnowledgeCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    note = Knowledge(
        project_id=project_id,
        title=data.title,
        content=data.content,
        category=data.category,
        tags=data.tags or [],
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return KnowledgeResponse.model_validate(note)


@router.get("", response_model=list[KnowledgeResponse])
async def list_knowledges(
    project_id: UUID,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(Knowledge).where(Knowledge.project_id == project_id)
    if category:
        query = query.where(Knowledge.category == category)
    query = query.order_by(Knowledge.updated_at.desc())

    result = await db.execute(query)
    notes = result.scalars().all()
    return [KnowledgeResponse.model_validate(n) for n in notes]


@router.get("/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge(
    project_id: UUID,
    knowledge_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Knowledge).where(Knowledge.id == knowledge_id, Knowledge.project_id == project_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return KnowledgeResponse.model_validate(note)


@router.put("/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(
    project_id: UUID,
    knowledge_id: UUID,
    data: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Knowledge).where(Knowledge.id == knowledge_id, Knowledge.project_id == project_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Knowledge not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)

    await db.commit()
    await db.refresh(note)
    return KnowledgeResponse.model_validate(note)


@router.delete("/{knowledge_id}", status_code=204)
async def delete_knowledge(
    project_id: UUID,
    knowledge_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Knowledge).where(Knowledge.id == knowledge_id, Knowledge.project_id == project_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Knowledge not found")

    await db.delete(note)
    await db.commit()