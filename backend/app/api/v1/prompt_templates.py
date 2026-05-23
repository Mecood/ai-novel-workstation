from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
)

router = APIRouter(prefix="/projects/{project_id}/prompt-templates", tags=["prompt-templates"])


@router.post("", response_model=PromptTemplateResponse, status_code=201)
async def create_prompt_template(
    project_id: UUID,
    data: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    template = PromptTemplate(
        project_id=project_id,
        name=data.name,
        category=data.category,
        system_prompt=data.system_prompt,
        user_prompt_template=data.user_prompt_template,
        parameters=data.parameters,
        is_default=data.is_default,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return PromptTemplateResponse.model_validate(template)


@router.get("", response_model=list[PromptTemplateResponse])
async def list_prompt_templates(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.project_id == project_id)
        .order_by(PromptTemplate.updated_at.desc())
    )
    templates = result.scalars().all()
    return [PromptTemplateResponse.model_validate(t) for t in templates]


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    project_id: UUID,
    template_id: UUID,
    data: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.project_id == project_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)
    return PromptTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=204)
async def delete_prompt_template(
    project_id: UUID,
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.project_id == project_id,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    await db.delete(template)
    await db.commit()
