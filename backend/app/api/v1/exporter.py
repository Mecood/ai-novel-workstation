"""
导出 API：以 json/txt/md 格式导出小说内容（安全过滤密钥）。

端点
----
GET /exporter/{project_id}
    ?format=json | txt | md  → 返回格式化文本流。
"""

from __future__ import annotations

import json
import re
import urllib.parse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter

router = APIRouter(prefix="/projects", tags=["exporter_safe"])

# ── Secret key patterns to filter ──────────────────────────────────────
_SECRET_KEYWORDS: list[str] = [
    r"api[_-]?key",
    r"api_key",
    r"secret[_-]?key",
    r"access[_-]?token",
    r"auth[_-]?token",
    r"bearer[_-]?token",
    r"x[_-]?appkey",
    r"x[_-]?app[_-]?key",
    r"x[_-]?app[_-]?keyer",
    r"private[_-]?key",
    r"passw(or)?d",
]

_REDACTED_MARKER = "***REDACTED***"


def _sanitize_text(text: str) -> str:
    """Mask secret-looking key=value / key: value patterns in text."""
    if not text:
        return text
    for kw in _SECRET_KEYWORDS:
        # Pattern: key=anything_not_whitespace or key: anything_not_whitespace
        pattern = re.compile(
            rf"({kw})\s*[:=]\s*\S+",
            re.IGNORECASE,
        )
        text = pattern.sub(rf"\1= {_REDACTED_MARKER}", text)
    return text


def _extract_text(content: object) -> str:
    """Extract plain text from chapter.content (JSON or string)."""
    if content is None:
        return ""
    if isinstance(content, dict):
        return (content.get("text") or content.get("content") or "").strip()
    if isinstance(content, str):
        return content.strip()
    return json.dumps(content, ensure_ascii=False)


def _build_json_output(project_name: str, chapters: list) -> str:
    """Build JSON string for export."""
    data = {
        "project": project_name,
        "chapters": [],
    }
    for ch in chapters:
        text = _extract_text(getattr(ch, "content", None))
        data["chapters"].append(
            {
                "chapter_number": getattr(ch, "chapter_number", None),
                "title": getattr(ch, "title", None) or "未命名",
                "content": _sanitize_text(text),
                "summary": getattr(ch, "summary", "") or "",
                "word_count": getattr(ch, "word_count", 0),
            }
        )
    return json.dumps(data, ensure_ascii=False, indent=2)


def _build_txt_output(project_name: str, chapters: list) -> str:
    """Build plain text output."""
    lines = [f"《{project_name}》", "=" * 40, ""]
    for ch in chapters:
        num = getattr(ch, "chapter_number", None) or 0
        title = getattr(ch, "title", None) or "未命名"
        text = _extract_text(getattr(ch, "content", None))
        lines.append(f"第{num}章  {title}")
        lines.append("-" * 30)
        lines.append(_sanitize_text(text))
        lines.append("")
        lines.append("")
    return "\n".join(lines)


def _build_md_output(project_name: str, chapters: list) -> str:
    """Build Markdown output."""
    lines = [f"# 《{project_name}》", ""]
    for ch in chapters:
        num = getattr(ch, "chapter_number", None) or 0
        title = getattr(ch, "title", None) or "未命名"
        text = _extract_text(getattr(ch, "content", None))
        summary = getattr(ch, "summary", "") or ""
        lines.append(f"## 第{num}章  {title}")
        if summary:
            lines.append(f"> {_sanitize_text(summary)}")
            lines.append("")
        lines.append(_sanitize_text(text))
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


@router.get("/{project_id}/export/safe")
async def export_safe(
    project_id: UUID,
    format: str = Query("json", pattern=r"^(json|txt|md)$"),
    db: AsyncSession = Depends(get_db),
):
    """安全导出：只导出正文文本，不包含 API keys。"""
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

    safe_name = project.name.replace("/", "_").replace("\\", "_")

    if format == "json":
        body = _build_json_output(safe_name, chapters)
        media_type = "application/json; charset=utf-8"
        ext = "json"
    elif format == "txt":
        body = _build_txt_output(safe_name, chapters)
        media_type = "text/plain; charset=utf-8"
        ext = "txt"
    elif format == "md":
        body = _build_md_output(safe_name, chapters)
        media_type = "text/markdown; charset=utf-8"
        ext = "md"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    filename = f"{safe_name}.{ext}"
    encoded = urllib.parse.quote(filename)
    return StreamingResponse(
        iter([body]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{encoded}"'},
    )