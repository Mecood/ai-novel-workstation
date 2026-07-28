"""
Backup / restore API for a whole project.

Endpoints
---------
GET  /backup/{project_id}
    JSON download with Content-Disposition: attachment.
POST /backup/{project_id}
    Restore project data from a JSON body.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.services.backup_service import backup_project, restore_project

router = APIRouter(prefix="/projects", tags=["backup"])


def _safe_name(name: str | None) -> str:
    safe = (name or "project").replace(" ", "_")
    for ch in r"\/:*?\"<>|":
        safe = safe.replace(ch, "_")
    return safe


@router.get("/backup/{project_id}")
async def get_backup(project_id: str) -> Response:
    """Export the entire project as a JSON backup file."""
    # Validate the project exists first.
    project_name: str | None = None
    async for db in get_db():
        from sqlalchemy import select

        row = await db.execute(select(Project).where(Project.id == project_id))
        project = row.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        project_name = project.name
        break

    try:
        payload = await backup_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    safe = _safe_name(project_name)
    # HTTP header values must be latin-1; percent-encode any non-ascii chars
    filename_bytes = f"project-{safe}-{date_str}.json".encode("utf-8")
    filename_escaped = "".join(
        f"%{b:02X}" if b > 127 else chr(b) for b in filename_bytes
    )
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename*="utf-8\'\'{filename_escaped}"',
            "Content-Type": "application/json; charset=utf-8",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/backup/{project_id}")
async def post_backup(
    project_id: str,
    data: dict,
) -> dict:
    """Restore a project from a backup JSON body."""
    async for db in get_db():
        from sqlalchemy import select

        row = await db.execute(select(Project).where(Project.id == project_id))
        if not row.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
        break

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    if "project" not in data:
        raise HTTPException(status_code=400, detail="Backup data missing 'project' field")

    try:
        count = await restore_project(project_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"restored_count": count}
