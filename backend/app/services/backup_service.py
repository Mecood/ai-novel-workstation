"""
Backup / restore service for an entire project.

Uses SQLAlchemy + SQLite only — no external AI or vector-store dependencies.
Backs up / restores every project-scoped table so that a JSON export can
recreate the full project state on import.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.worldview import Worldview
from app.models.knowledge import Knowledge
from app.models.foreshadowing import Foreshadowing
from app.models.story_event import StoryEvent
from app.models.volume import Volume
from app.models.chapter_contract import ChapterContract
from app.models.chapter_commit import ChapterCommit
from app.models.contract_audit_log import ContractAuditLog
from app.models.override_contract import OverrideContract
from app.models.chase_debt import ChaseDebt
from app.models.debt_event import DebtEvent
from app.models.reading_power import ChapterReadingPower
from app.models.review_report import ReviewReport
from app.models.memory_item import MemoryItem
from app.models.prompt_template import PromptTemplate
from app.models.skill import ProjectSkill
from app.models.project_asset import ProjectAsset
from app.models.deconstruction_history import DeconstructionHistory
from app.models.pipeline_state import PipelineState


# Ordered so parent rows are removed before their children on restore,
# and inserted before their children on restore.
_MODEL_PHASES: list[tuple[Any, int, int]] = [
    (Project, 1, 0),
    # Roots: FK -> projects
    (Chapter, 2, 0),
    (Volume, 2, 1),
    (Character, 2, 2),
    (Worldview, 2, 3),
    (Knowledge, 2, 4),
    (PipelineState, 2, 5),
    (ReviewReport, 2, 6),
    (PromptTemplate, 2, 7),
    (ProjectSkill, 2, 8),
    (ProjectAsset, 2, 9),
    (DeconstructionHistory, 2, 10),
    (ChapterReadingPower, 2, 11),
    (ChaseDebt, 2, 12),
    (OverrideContract, 2, 13),
    # Child rows referencing the roots above
    (StoryEvent, 3, 0),
    (Foreshadowing, 3, 1),
    (ChapterContract, 3, 2),
    (DebtEvent, 3, 3),
    # Deepest: chapters, contracts and debts may be deleted, so clean last
    (ChapterCommit, 4, 0),
    (ContractAuditLog, 4, 1),
]

_MODEL_BY_TABLE: dict[str, Any] = {m.__tablename__: m for m, _, _ in _MODEL_PHASES}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now().isoformat()


def _format_date(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _serialize_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    return _format_date(v)


def _row_to_dict(obj: Any) -> dict:
    return {
        c.name: _serialize_value(getattr(obj, c.name))
        for c in obj.__table__.columns
    }


def _row_to_insert_data(data: dict, model: Any) -> dict:
    out: dict[str, Any] = {}
    for c in model.__table__.columns:
        key = c.name
        if key not in data:
            continue
        v = data[key]
        if v is None:
            out[key] = None
            continue
        col_type_name = type(c.type).__name__
        # Primary-key UUID columns: keep user IDs so FK chains survive
        if key == "id" and isinstance(v, str):
            try:
                out[key] = uuid.UUID(v)
            except (ValueError, AttributeError):
                out[key] = v
            continue
        if col_type_name == "DateTime" and isinstance(v, str):
            try:
                out[key] = datetime.fromisoformat(v)
            except (ValueError, TypeError):
                out[key] = v
            continue
        if col_type_name == "Numeric" and isinstance(v, (int, float)):
            out[key] = Decimal(str(v))
            continue
        out[key] = v
    return out


async def _fetch_table(db: AsyncSession, model: Any) -> list[dict]:
    pk_cols = [c for c in model.__table__.primary_key.columns]
    stmt = select(model)
    if pk_cols:
        stmt = stmt.order_by(*pk_cols)
    rows = await db.execute(stmt)
    return [_row_to_dict(o) for o in rows.scalars().all()]

async def _fetch_project_scoped(db: AsyncSession, model: Any, project_id: uuid.UUID) -> list[dict]:
    if "project_id" not in model.__table__.c:
        return []
    pk_cols = [c for c in model.__table__.primary_key.columns]
    query = select(model).where(model.project_id == project_id)
    if pk_cols:
        query = query.order_by(*pk_cols)
    rows = await db.execute(query)
    return [_row_to_dict(o) for o in rows.scalars().all()]


async def backup_project(project_id: str) -> dict:
    """Load an entire project from the database and return a serializable dict."""
    pid = uuid.UUID(project_id)
    async with __import__(
        "app.core.database", fromlist=["async_session"]
    ).async_session() as db:
        return await _backup_project_inner(db, pid)


async def _backup_project_inner(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Core backup logic given an existing session."""
    row = await db.execute(select(Project).where(Project.id == project_id))
    project = row.scalar_one_or_none()
    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    payload: Dict[str, Any] = {
        "project": _row_to_dict(project),
        "backup_time": _iso_now(),
        "backup_format_version": 1,
    }

    for model, _, _ in _MODEL_PHASES:
        if model is Project:
            continue
        if "project_id" in model.__table__.c:
            rows = await _fetch_project_scoped(db, model, project_id)
        else:
            # Non-project tables (none expected, but be safe): include all.
            rows = await _fetch_table(db, model)
        payload[model.__tablename__] = rows
    return payload


async def restore_project(project_id: str, data: dict) -> int:
    """Replace all project-scoped data for project_id; returns rows inserted."""
    pid = uuid.UUID(project_id)
    async with __import__(
        "app.core.database", fromlist=["async_session"]
    ).async_session() as db:
        return await _restore_project_inner(db, pid, data)


async def _restore_project_inner(
    db: AsyncSession, project_id: uuid.UUID, data: dict
) -> int:
    proj_row = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    if proj_row.scalar_one_or_none() is None:
        raise ValueError(f"Project not found: {project_id}")

    # Remove project-scoped rows deepest-first (children before parents).
    for model, _, _ in reversed(_MODEL_PHASES):
        if model is Project:
            continue
        if "project_id" in model.__table__.c:
            rows = await db.execute(
                select(model).where(model.project_id == project_id)
            )
            for row in rows.scalars().all():
                db.delete(row)
    total = 0
    for model, _, _ in _MODEL_PHASES:
        if model is Project:
            continue
        for rd in data.get(model.__tablename__, []):
            kwargs = _row_to_insert_data(rd, model)
            # Skip rows whose project_id points elsewhere (import hygiene).
            if "project_id" in kwargs and kwargs["project_id"] != project_id:
                continue
            db.add(model(**kwargs))
            total += 1

    await db.commit()

    # Sweep orphaned references to now-deleted chapters / contracts / debts.
    # (chapter_ids and contract_ids in restore payload are preserved, so most
    # relationships stay intact; this only catches rows with stale FKs.)
    await _sweep_orphans(db, project_id)
    await db.commit()
    return total


# Tables whose rows may reference chapters/contracts/debts that were deleted.
_ORPHAN_MODELS: list[Any] = [
    PipelineState,
    MemoryItem,
    PromptTemplate,
    ProjectSkill,
    ProjectAsset,
    DeconstructionHistory,
    ChapterReadingPower,
    ChaseDebt,
    ReviewReport,
    StoryEvent,
    Foreshadowing,
    ChapterContract,
    DebtEvent,
    ContractAuditLog,
    ChapterCommit,
]


async def _sweep_orphans(db: AsyncSession, project_id: uuid.UUID) -> None:
    """Delete project rows whose FK targets no longer exist in this project."""
    id_lookups: dict[str, set[Any]] = {}
    for table in ("chapters", "chapter_contracts", "chase_debts"):
        model = _MODEL_BY_TABLE.get(table)
        if model is None:
            continue
        rows = await db.execute(
            select(model).where(model.project_id == project_id)
        )
        id_lookups[table] = {
            uuid.UUID(str(r.id)) for r in rows.scalars().all() if r.id is not None
        }

    for model in _ORPHAN_MODELS:
        if "project_id" not in model.__table__.c:
            continue
        rows = await db.execute(
            select(model).where(model.project_id == project_id)
        )
        for row in rows.scalars().all():
            keep = True
            for target_table, attr in [
                ("chapters", "chapter_id"),
                ("chapter_contracts", "contract_id"),
                ("chase_debts", "debt_id"),
            ]:
                lookup = id_lookups.get(target_table)
                if lookup is None:
                    continue
                fid = getattr(row, attr, None)
                if fid is not None and uuid.UUID(str(fid)) not in lookup:
                    keep = False
                    break
            if not keep:
                db.delete(row)
