"""Pipeline Stage Advancer — auto-advances project through pipeline stages."""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select, func, and_, update, Column, String, DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import GUID, Base
from app.core.config import settings
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.character import Character
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.review_report import ReviewReport
from app.models.chapter_commit import ChapterCommit, CommitStatus
from app.models.pipeline_state import PipelineState


class PipelineStage(str, Enum):
    INIT = "init"
    PLAN = "plan"
    WRITE = "write"
    REVIEW = "review"
    COMMIT = "commit"
    COMPLETED = "completed"


# Stage transition edges: (from, to) with condition check function
STAGE_ORDER = [
    PipelineStage.INIT,
    PipelineStage.PLAN,
    PipelineStage.WRITE,
    PipelineStage.REVIEW,
    PipelineStage.COMMIT,
    PipelineStage.COMPLETED,
]


def _get_next_stage(current: PipelineStage) -> Optional[PipelineStage]:
    idx = STAGE_ORDER.index(current)
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return None


class PipelineTransition(Base):
    """Log of pipeline stage transitions."""
    __tablename__ = "pipeline_transitions"

    id = Column(GUID, primary_key=True, default=str(uuid.uuid4))
    project_id = Column(GUID, nullable=False)
    from_stage = Column(String(50), nullable=False)
    to_stage = Column(String(50), nullable=False)
    trigger = Column(String(100), nullable=True)
    triggered_by = Column(String(20), nullable=True, default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __init__(self, project_id: str, from_stage: str, to_stage: str,
                 trigger: str = "", triggered_by: str = "system"):
        self.project_id = project_id
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.trigger = trigger
        self.triggered_by = triggered_by


# ============================================================
# PipelineAdvancer — core logic
# ============================================================

class PipelineAdvancer:
    """Checks stage conditions and advances projects through the pipeline."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_and_advance(self, project_id: str, trigger: str = "") -> Optional[dict]:
        """Check conditions for current stage and advance if possible.
        Returns transition info if advanced, None otherwise.
        Idempotent — calling multiple times won't double-advance.
        """
        # Respect auto_advance_enabled toggle (Phase 9)
        proj_result = await self.db.execute(
            select(Project.pipeline_stage, Project.auto_advance_enabled)
            .where(Project.id == project_id)
        )
        row = proj_result.one_or_none()
        if not row:
            return None

        if not row.auto_advance_enabled:
            return None

        try:
            current_stage = PipelineStage(row.pipeline_stage)
        except (ValueError, TypeError):
            current_stage = PipelineStage.INIT

        # Already at the end
        if current_stage == PipelineStage.COMPLETED:
            return None

        next_stage = _get_next_stage(current_stage)
        if not next_stage:
            return None

        # Check condition for advancement
        condition_met = await self._check_condition(current_stage, project_id)
        if not condition_met:
            return None

        # Advance
        await self.db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(pipeline_stage=next_stage.value)
        )

        # Log transition
        transition = PipelineTransition(
            project_id=project_id,
            from_stage=current_stage.value,
            to_stage=next_stage.value,
            trigger=trigger,
        )
        self.db.add(transition)

        # ── Phase 14.2: 持久化流水线状态 ────────────────────────────
        await self._update_state(project_id, next_stage)

        await self.db.commit()

        return {
            "from_stage": current_stage.value,
            "to_stage": next_stage.value,
            "trigger": trigger,
            "message": f"{current_stage.value} → {next_stage.value}",
        }

    async def _check_condition(self, current: PipelineStage, project_id: str) -> bool:
        """Check if we can advance from current stage."""
        if current == PipelineStage.INIT:
            # Need worldview + characters
            wv = await self._count(Worldview, project_id)
            ch = await self._count(Character, project_id)
            return wv > 0 and ch > 0

        elif current == PipelineStage.PLAN:
            # Need volumes + chapters with outline
            vol = await self._count(Volume, project_id)
            outlined = await self._count_outlined_chapters(project_id)
            return vol > 0 and outlined > 0

        elif current == PipelineStage.WRITE:
            # Need at least one chapter written
            written = await self._count_written_chapters(project_id)
            return written > 0

        elif current == PipelineStage.REVIEW:
            # Need reviewed chapters with no blocking issues
            reviewed = await self._count_reviewed(project_id)
            blocking = await self._count_blocking(project_id)
            return reviewed > 0 and blocking == 0

        elif current == PipelineStage.COMMIT:
            # Need at least one accepted commit
            accepted = await self._count_accepted_commits(project_id)
            return accepted > 0

        return False

    async def _count(self, model, project_id: str) -> int:
        r = await self.db.execute(
            select(func.count(model.id))
            .where(model.project_id == project_id)
        )
        return r.scalar() or 0

    async def _count_outlined_chapters(self, project_id: str) -> int:
        r = await self.db.execute(
            select(func.count(Chapter.id))
            .where(Chapter.project_id == project_id, Chapter.outline_detail.isnot(None))
        )
        return r.scalar() or 0

    async def _count_written_chapters(self, project_id: str) -> int:
        r = await self.db.execute(
            select(func.count(Chapter.id))
            .where(Chapter.project_id == project_id, Chapter.content.isnot(None))
        )
        return r.scalar() or 0

    async def _count_reviewed(self, project_id: str) -> int:
        r = await self.db.execute(
            select(func.count(ReviewReport.id))
            .where(ReviewReport.project_id == project_id)
        )
        return r.scalar() or 0

    async def _count_blocking(self, project_id: str) -> int:
        r = await self.db.execute(
            select(func.coalesce(func.sum(ReviewReport.blocking_count), 0))
            .where(ReviewReport.project_id == project_id)
        )
        return int(r.scalar() or 0)

    async def _count_accepted_commits(self, project_id: str) -> int:
        r = await self.db.execute(
            select(func.count(ChapterCommit.id))
            .where(ChapterCommit.project_id == project_id, ChapterCommit.status == CommitStatus.ACCEPTED)
        )
        return r.scalar() or 0

    async def get_transitions(self, project_id: str, limit: int = 20) -> list[dict]:
        """Get recent transition history for a project."""
        from sqlalchemy.orm import Session
        result = await self.db.execute(
            select(PipelineTransition)
            .where(PipelineTransition.project_id == project_id)
            .order_by(PipelineTransition.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(r.id),
                "from_stage": r.from_stage,
                "to_stage": r.to_stage,
                "trigger": r.trigger,
                "triggered_by": r.triggered_by,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    # ── Phase 14.2: 流水线状态持久化 ──────────────────────────────────

    async def _get_or_create_state(self, project_id: str) -> PipelineState:
        """获取或创建项目的持久化流水线状态。"""
        result = await self.db.execute(
            select(PipelineState).where(PipelineState.project_id == project_id)
        )
        state = result.scalar_one_or_none()
        if not state:
            state = PipelineState(
                project_id=project_id,
                current_stage=PipelineStage.INIT.value,
            )
            self.db.add(state)
            await self.db.flush()
        return state

    async def _update_state(self, project_id: str, stage: PipelineStage) -> PipelineState:
        """更新流水线状态并持久化。"""
        state = await self._get_or_create_state(project_id)
        state.current_stage = stage.value
        state.last_advanced_at = datetime.now(timezone.utc)
        state.pipeline_runs = (state.pipeline_runs or 0) + 1
        state.updated_at = datetime.now(timezone.utc)
        # 不直接 commit，让调用方统一 commit
        return state