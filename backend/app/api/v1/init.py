"""Project initialization API routes with SSE progress streaming."""
import json
from datetime import datetime, timezone
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.services.init_service import init_project, get_init_progress


class InitRequest(BaseModel):
    genre: str
    theme: str
    style: str = ""
    reference_patterns: dict | None = None


router = APIRouter(prefix="/projects/{project_id}/init", tags=["init"])


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _step_status(result: dict, key: str) -> str:
    details = result.get("details") or {}
    val = details.get(key)
    if isinstance(val, dict) and val.get("type") == "generated":
        return "completed"
    return "skipped" if val else "unknown"


async def _run_and_stream(
    project_id: str,
    params: dict,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """Execute init_project while emitting SSE events for progress."""
    yield _sse_event({
        "type": "start",
        "project_id": project_id,
        "step": "preparing",
        "status": "running",
        "message": "正在开始项目初始化...",
    })
    try:
        result = await init_project(db, project_id, params)
    except HTTPException as exc:
        yield _sse_event({
            "type": "error",
            "status": "failed",
            "error": exc.detail if hasattr(exc, "detail") else str(exc),
        })
        yield _sse_done()
        return
    except Exception as exc:
        yield _sse_event({
            "type": "error",
            "status": "failed",
            "error": str(exc),
        })
        yield _sse_done()
        return

    # Persist the final payload so get_init_progress can return it later.
    # Reuse the request's session instead of opening a second connection.
    try:
        proj = await db.get(Project, project_id)
        if proj:
            proj.context = dict(proj.context or {})
            proj.context["_init_progress"] = result
            proj.updated_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:
        pass  # persistence failure must not break the stream response

    if result["status"] == "failed":
        yield _sse_event({
            "type": "error",
            "status": "failed",
            "step": result.get("step"),
            "error": result.get("error"),
            "details": result.get("details"),
        })
    else:
        for step in ("story_core", "worldview", "characters", "outline"):
            yield _sse_event({
                "type": "step",
                "step": step,
                "status": _step_status(result, step),
                "details": result.get("details", {}).get(step),
            })
        yield _sse_event({
            "type": "done",
            "status": "completed",
            "step": "complete",
            "skipped_steps": result.get("skipped_steps", []),
            "message": "项目初始化完成，可以开始创作了！",
        })
    yield _sse_done()


@router.post("", response_model=None)
async def trigger_init(
    project_id: str,
    data: InitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Trigger full project initialization with SSE progress streaming."""
    params = {
        "genre": data.genre,
        "theme": data.theme,
        "style": data.style,
        "reference_patterns": data.reference_patterns,
    }
    return StreamingResponse(
        _run_and_stream(project_id, params, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/progress")
async def query_progress(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Query the latest initialization progress for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await get_init_progress(project_id)
