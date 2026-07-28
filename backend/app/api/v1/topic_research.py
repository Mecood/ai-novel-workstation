"""选题调研 API 路由"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.topic_research import research_topic

router = APIRouter(prefix="/projects", tags=["topic-research"])


@router.get("/topic/research")
async def research(
    genre: str = Query(..., description="题材"),
    project_name: str = Query("", description="参考书名"),
    db: AsyncSession = Depends(get_db),
):
    """AI 选题调研——分析题材市场趋势，推荐 3 个切入点方案。"""
    if not genre.strip():
        raise HTTPException(400, "必须提供题材参数")
    return await research_topic(db, genre=genre.strip(), project_name=project_name.strip())