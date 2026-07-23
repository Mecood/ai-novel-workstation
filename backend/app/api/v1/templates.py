"""
题材模板 CRUD API。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.genre_template import GenreTemplate
from app.schemas.genre_template import GenreTemplateResponse

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[GenreTemplateResponse])
async def list_templates(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """列出所有题材模板，可按类别筛选。"""
    query = select(GenreTemplate).order_by(GenreTemplate.name)
    if category:
        query = query.where(GenreTemplate.category == category)
    result = await db.execute(query)
    return [GenreTemplateResponse.model_validate(t) for t in result.scalars().all()]


@router.get("/{template_id}", response_model=GenreTemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取单个模板详情。"""
    result = await db.execute(
        select(GenreTemplate).where(GenreTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return GenreTemplateResponse.model_validate(template)