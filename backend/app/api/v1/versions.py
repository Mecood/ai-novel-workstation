from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.project import Project
from app.schemas.chapter import ChapterResponse
from app.schemas.version import (
    VersionDetailResponse,
    VersionEntryResponse,
    VersionHistoryResponse,
    VersionRestoreResponse,
)

router = APIRouter(prefix="/projects/{project_id}/chapters/{chapter_id}/versions", tags=["versions"])


def _hash_of(entry: dict) -> str:
    """Recompute a 16-char SHA-256 hash from a history entry so the listing is self-consistent."""
    import hashlib
    import json

    content = entry.get("content")
    if isinstance(content, dict):
        content_text = content.get("text", "") or ""
    elif isinstance(content, str):
        content_text = content
    else:
        content_text = json.dumps(content, ensure_ascii=False) if content else ""
    return hashlib.sha256(content_text.encode("utf-8")).hexdigest()[:16]


def _entry_response(entry: dict) -> VersionEntryResponse:
    return VersionEntryResponse(
        version=entry.get("version", 0),
        content_hash=_hash_of(entry),
        word_count=entry.get("word_count", 0),
        saved_at=datetime.fromisoformat(entry.get("saved_at", datetime.now(timezone.utc).isoformat())),
    )


def _detail_response(entry: dict) -> VersionDetailResponse:
    return VersionDetailResponse(
        version=entry.get("version", 0),
        content_hash=_hash_of(entry),
        word_count=entry.get("word_count", 0),
        content=entry.get("content"),
        saved_at=datetime.fromisoformat(entry.get("saved_at", datetime.now(timezone.utc).isoformat())),
    )


def _resolve_chapter(project_id: UUID, chapter_id: UUID, project: Project, chapter: Chapter | None):
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")


@router.get("", response_model=VersionHistoryResponse)
async def list_versions(
    project_id: UUID,
    chapter_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    _resolve_chapter(project_id, chapter_id, project, chapter)

    history = chapter._history or []
    # Return newest first (the head of the list is the most recent snapshot).
    versions = [_entry_response(e) for e in reversed(history)]
    return VersionHistoryResponse(
        chapter_id=str(chapter.id),
        current_version=chapter._version,
        versions=versions,
    )


@router.get("/{version}", response_model=VersionDetailResponse)
async def get_version(
    project_id: UUID,
    chapter_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    _resolve_chapter(project_id, chapter_id, project, chapter)

    history = chapter._history or []
    for entry in history:
        if entry.get("version") == version:
            return _detail_response(entry)
    raise HTTPException(status_code=404, detail=f"Version {version} not found")


@router.post("/{version}/restore", response_model=ChapterResponse)
async def restore_version(
    project_id: UUID,
    chapter_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    _resolve_chapter(project_id, chapter_id, project, chapter)

    history = chapter._history or []
    target = None
    for entry in history:
        if entry.get("version") == version:
            target = entry
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    previous_version = chapter._version
    # Snapshot the current (pre-restore) state into history first.
    import hashlib
    import json

    if chapter._history is None:
        chapter._history = []
    pre_restore_content = chapter.content
    if isinstance(pre_restore_content, dict):
        pre_restore_text = pre_restore_content.get("text", "") or ""
    elif isinstance(pre_restore_content, str):
        pre_restore_text = pre_restore_content
    else:
        pre_restore_text = json.dumps(pre_restore_content, ensure_ascii=False) if pre_restore_content else ""
    pre_restore_snapshot = {
        "version": chapter._version,
        "content": pre_restore_content,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "word_count": chapter.word_count,
        "content_hash": hashlib.sha256(pre_restore_text.encode("utf-8")).hexdigest()[:16],
    }
    chapter._history = (chapter._history or []) + [pre_restore_snapshot]

    # Restore the target version content.
    restored_content = target.get("content")
    chapter.content = restored_content
    chapter.word_count = target.get("word_count", chapter.word_count)
    chapter._version = chapter._version + 1

    await db.commit()
    await db.refresh(chapter)
    return ChapterResponse.model_validate(chapter)
