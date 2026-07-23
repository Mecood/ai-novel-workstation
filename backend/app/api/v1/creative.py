"""创意组合引擎 API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.services.creative_engine import IdeaCombinator, PlotFramework

router = APIRouter(prefix="/projects/{project_id}/creative")


@router.post("/combine")
async def creative_combine(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    complexity: str = Query(default="medium", pattern="^(high|medium|low)$", description="组合复杂度 high/medium/low"),
):
    """生成创意组合。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    combinator = IdeaCombinator()
    combination = combinator.combine(project.genre, complexity)
    idea_prompt = combinator.generate_idea_prompt(combination)

    return {
        "combination": combination,
        "idea_prompt": idea_prompt,
        "genre": project.genre,
        "complexity": complexity,
    }


@router.get("/frameworks")
async def list_frameworks(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    name: str | None = Query(None, description="指定框架名称"),
):
    """获取情节框架列表或指定框架详情。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    frameworks = PlotFramework()

    if name:
        framework = frameworks.get_framework(name)
        if not framework:
            raise HTTPException(404, f"框架 '{name}' 不存在")
        return {"framework": framework}

    return {
        "frameworks": frameworks.get_all_frameworks(),
        "recommended": frameworks.recommend_for_genre(project.genre),
    }