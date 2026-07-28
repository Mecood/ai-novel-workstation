"""
P5C: Signing Check API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.character import Character
from app.services.signing_check_service import SigningCheckService
from app.services.ai_service import AIService

router = APIRouter(prefix="/signing", tags=["signing-check"])


@router.get("/check/{project_id}")
async def signing_check(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """签约自测 — 分析前三章"""
    chapters = (
        (await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
            ).order_by(Chapter.chapter_number).limit(3)
        ))
        .scalars().all()
    )

    if not chapters:
        raise HTTPException(404, "该项目无章节")

    proj = (
        (await db.execute(select(Project).where(Project.id == project_id)))
        .scalars().first()
    )

    # 世界观
    wv_rows = (
        (await db.execute(
            select(Worldview).where(Worldview.project_id == project_id)
        ))
        .scalars().all()
    )
    worldview_text = "\n".join(
        str(w.description or "")[:200] for w in wv_rows if w.description is not None
    ) if wv_rows else ""

    # 角色
    chars = (
        (await db.execute(
            select(Character).where(Character.project_id == project_id)
        ))
        .scalars().all()
    )
    char_text = "\n".join(
        f"- {c.name}（{c.role_type}）: {c.background}"
        for c in chars
    ) if chars else ""

    svc = SigningCheckService(ai_service=AIService())
    report = await svc.analyze(
        project_name=str(proj.name) if proj else "未命名",
        chapters=[
            {
                "chapter_number": ch.chapter_number,
                "title": str(ch.title),
                "content": str(ch.content) if ch.content is not None else "",
            }
            for ch in chapters
        ],
        worldview=worldview_text,
        characters=char_text,
    )

    return {
        "total_score": report.total_score,
        "platform": report.platform,
        "pass_threshold": report.pass_threshold,
        "is_pass": report.is_pass,
        "summary": report.summary,
        "top_strength": report.top_strength,
        "top_weakness": report.top_weakness,
        "dimensions": [
            {
                "id": d.id,
                "name": d.name,
                "score": d.score,
                "verdict": d.verdict,
                "analysis": d.analysis,
                "suggestions": d.suggestions,
            }
            for d in report.dimensions
        ],
    }