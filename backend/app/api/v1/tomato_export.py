"""
P5B: Tomato export API
"""
from typing import Annotated
from fastapi import APIRouter, Depends, Body, Query, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.chapter import Chapter
from app.services.tomato_service import TomatoExporter

router = APIRouter(prefix="/tomato", tags=["tomato"])


@router.get("/export/{project_id}")
async def tomato_export(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """导出番茄小说格式的纯文本"""
    chapters = (
        (await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
            ).order_by(Chapter.chapter_number)
        ))
        .scalars().all()
    )

    if not chapters:
        raise HTTPException(404, "项目无章节")

    # 找出项目名称
    from app.models.project import Project
    proj = (
        (await db.execute(
            select(Project).where(Project.id == project_id)
        ))
        .scalars().first()
    )

    exporter = TomatoExporter()
    result = exporter.export_project(
        project_name=str(proj.name) if proj else "未命名",
        chapters=[
            {
                "chapter_number": ch.chapter_number,
                "title": str(ch.title),
                "content": str(ch.content) if ch.content is not None else "",
            }
            for ch in chapters
        ],
    )

    return {
        "project_name": result.project_name,
        "chapter_count": result.chapter_count,
        "total_chars": result.total_chars,
        "text": result.text,
    }


@router.post("/zhuque-check")
async def zhuque_check(
    chapter_text: Annotated[str, Body()],
):
    """朱雀检测 — 评估番茄 AI 过审概率"""
    # 尝试加载朱雀检测器
    try:
        from app.services.zhuque_detector import get_zhuque_detector
        detector = get_zhuque_detector()
    except Exception:
        return {"error": "朱雀检测器未部署，请先运行 zhuque_setup.py"}

    exporter = TomatoExporter(zhuque_detector=detector)
    result = await exporter.check_with_zhuque(chapter_text)
    return result