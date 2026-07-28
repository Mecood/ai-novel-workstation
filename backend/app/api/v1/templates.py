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
from app.services.genre_seed import seed_templates, get_template_by_name

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


@router.post("/seed")
async def run_seed(db: AsyncSession = Depends(get_db)):
    """执行题材模板种子注入（幂等，重复调用不报错）。"""
    from app.models.genre_template import GenreTemplate
    inserted = await seed_templates(db)
    return {"inserted": inserted, "message": f"已注入 {inserted} 个新模板"}


@router.get("/search/{name}")
async def search_template(name: str, db: AsyncSession = Depends(get_db)):
    """按题材名搜索模板配置（用于前端选题）。"""
    result = await db.execute(
        select(GenreTemplate).where(GenreTemplate.name == name)
    )
    t = result.scalar_one_or_none()
    if t:
        return GenreTemplateResponse.model_validate(t)
    # 回退到内置种子数据
    builtin = get_template_by_name(name)
    if builtin:
        return {"name": builtin["name"], "config": builtin["config"],
                "category": "（内置）"}
    raise HTTPException(404, f"未找到题材模板：{name}")
