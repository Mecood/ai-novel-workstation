"""
导出 API：将小说导出为 Microsoft Word (.docx)。

端点
----
POST /projects/{project_id}/export/full
    导出项目下全部章节（封面 + 所有章节正文）。
POST /projects/{project_id}/export/chapter/{chapter_id}
    导出单个章节。
"""

from __future__ import annotations

import urllib.parse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter

router = APIRouter(prefix="/projects", tags=["export"])


@router.post("/{project_id}/export/full")
async def export_full_docx(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """导出全部章节为 .docx。"""
    project = (
        (await db.execute(select(Project).where(Project.id == project_id)))
        .scalar_one_or_none()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.asc())
    )
    chapters = result.scalars().all()

    from app.services.export_service import build_docx_bytes

    body = build_docx_bytes(project.name, chapters)

    safe_name = project.name.replace("/", "_").replace("\\", "_")
    filename = f"{safe_name}_full.docx"
    encoded_filename = urllib.parse.quote(filename)
    return StreamingResponse(
        iter([body]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{encoded_filename}"'},
    )


@router.post("/{project_id}/export/chapter/{chapter_id}")
async def export_chapter_docx(
    project_id: UUID,
    chapter_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """导出单个章节为 .docx。"""
    project = (
        (await db.execute(select(Project).where(Project.id == project_id)))
        .scalar_one_or_none()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Chapter)
        .where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    from app.services.export_service import build_docx_bytes

    body = build_docx_bytes(project.name, [chapter])

    safe_project = project.name.replace("/", "_").replace("\\", "_")
    safe_title = (chapter.title or "未命名").replace("/", "_").replace("\\", "_")
    filename = f"{safe_project}_{safe_title}.docx"
    encoded_filename = urllib.parse.quote(filename)
    return StreamingResponse(
        iter([body]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{encoded_filename}"'},
    )
