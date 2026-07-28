"""Plot dashboard API — 聚合时间线 + 伏笔 → 剧情复盘数据。"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.story_event import StoryEvent
from app.models.foreshadowing import Foreshadowing

from app.services.plot_dashboard_service import get_plot_dashboard

router = APIRouter(tags=["plot_dashboard"])


@router.get("/projects/{project_id}/plot/dashboard")
async def plot_dashboard(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """返回剧情复盘看板数据。"""
    result = await db.execute(
        select(Project).where(Project.id == str(project_id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    try:
        data = await get_plot_dashboard(db, str(project_id))
    except Exception as e:
        raise HTTPException(500, str(e))

    return data
