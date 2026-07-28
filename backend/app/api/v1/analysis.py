"""
多任务分析编排器 API。路由 /api/v1/projects/{id}/analysis/
POST /run  — 触发批量分析
GET  /history — 查询分析历史
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.services.ai_service import AIService
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/projects/{project_id}/analysis", tags=["analysis"])

ai_service = AIService()
analysis_service = AnalysisService(ai_service)

@router.post("/run")
async def run_analysis(
    project_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """触发批量 AI 分析任务。同步执行后返回报告。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    task_types = body.get("task_types") or []
    chapter_range = body.get("chapter_range")

    try:
        reports = await analysis_service.run_batch_analysis(
            db, str(project_id), task_types, chapter_range
        )
    except Exception as e:
        return {"error": str(e), "reports": []}

    status_map = {"running": 0, "complete": 0, "error": 0}
    for r in reports:
        s = r.get("status", "running")
        status_map[s] = status_map.get(s, 0) + 1

    return {
        "status_map": status_map,
        "total": len(reports),
        "reports": reports,
    }

@router.get("/history")
async def get_analysis_history(
    project_id: UUID,
    task_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取已保存的分析历史报告。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    try:
        history = await analysis_service.get_analysis_history(
            db, str(project_id), task_type
        )
    except Exception as e:
        return {"error": str(e), "items": []}
    return {"count": len(history), "items": history}