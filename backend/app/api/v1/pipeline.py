"""Pipeline Dashboard — aggregated status API for the 5-stage pipeline."""
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.worldview import Worldview
from app.models.character import Character
from app.models.volume import Volume
from app.models.review_report import ReviewReport
from app.models.story_event import StoryEvent
from app.models.chase_debt import ChaseDebt, DebtStatus
from app.models.reading_power import ChapterReadingPower
from app.models.override_contract import OverrideContract, ContractStatus as OvContractStatus
from app.models.chapter_contract import ChapterContract, ContractStatus as ChContractStatus
from app.models.chapter_commit import ChapterCommit, CommitStatus
from app.services.pipeline_advancer import PipelineAdvancer, PipelineTransition

router = APIRouter(prefix="/projects/{project_id}", tags=["pipeline"])


def _compute_stages(data: dict) -> list[dict]:
    """Compute 5-stage pipeline status from aggregated data."""
    worldview_count = data.get("worldview_count", 0)
    character_count = data.get("character_count", 0)
    total_chapters = data.get("total_chapters", 0)
    chapters_with_outline = data.get("chapters_with_outline", 0)
    chapters_written = data.get("chapters_written", 0)
    total_words = data.get("total_words", 0)
    reviewed_chapters = data.get("reviewed_chapters", 0)
    total_blocking = data.get("total_blocking", 0)
    event_count = data.get("event_count", 0)
    signed_contracts = data.get("signed_contracts", 0)
    accepted_commits = data.get("accepted_commits", 0)

    stages = []

    # Stage 1: Init — project exists, worldview + characters created
    init_checks = [worldview_count > 0, character_count > 0]
    init_done = sum(1 for v in init_checks if v)
    if init_done == len(init_checks):
        stages.append({"id": "init", "label": "初始化", "status": "completed", "progress": {"current": init_done, "total": len(init_checks)}})
    elif init_done > 0:
        stages.append({"id": "init", "label": "初始化", "status": "running", "progress": {"current": init_done, "total": len(init_checks)}})
    else:
        stages.append({"id": "init", "label": "初始化", "status": "pending", "progress": {"current": 0, "total": len(init_checks)}})

    # Stage 2: Plan — volumes + outline created
    plan_checks = [worldview_count > 0, character_count > 0, data.get("volume_count", 0) > 0, chapters_with_outline > 0]
    plan_done = sum(1 for v in plan_checks if v)
    init_completed = stages[0]["status"] == "completed"
    if plan_done == len(plan_checks):
        stages.append({"id": "plan", "label": "规划", "status": "completed", "progress": {"current": plan_done, "total": len(plan_checks)}})
    elif init_completed and plan_done > 0:
        stages.append({"id": "plan", "label": "规划", "status": "running", "progress": {"current": plan_done, "total": len(plan_checks)}})
    elif init_completed:
        stages.append({"id": "plan", "label": "规划", "status": "pending", "progress": {"current": 0, "total": len(plan_checks)}})
    else:
        stages.append({"id": "plan", "label": "规划", "status": "blocked", "progress": {"current": 0, "total": len(plan_checks)}})

    # Stage 3: Write — chapters written
    plan_completed = stages[1]["status"] == "completed"
    if chapters_written > 0:
        stages.append({"id": "write", "label": "写作", "status": "completed" if total_chapters > 0 and chapters_written >= total_chapters else "running",
                        "progress": {"current": chapters_written, "total": max(total_chapters, 1)}})
    elif plan_completed:
        stages.append({"id": "write", "label": "写作", "status": "pending", "progress": {"current": 0, "total": 1}})
    else:
        stages.append({"id": "write", "label": "写作", "status": "blocked", "progress": {"current": 0, "total": 1}})

    # Stage 4: Review — chapters reviewed
    review_checks = [reviewed_chapters > 0, event_count > 0]
    review_done = sum(1 for v in review_checks if v)
    write_completed = stages[2]["status"] == "completed"
    if total_blocking > 0:
        stages.append({"id": "review", "label": "审查", "status": "error", "progress": {"current": review_done, "total": len(review_checks)},
                        "detail": f"{total_blocking} 个阻断问题待修复"})
    elif review_done == len(review_checks):
        stages.append({"id": "review", "label": "审查", "status": "completed", "progress": {"current": review_done, "total": len(review_checks)}})
    elif write_completed and review_done > 0:
        stages.append({"id": "review", "label": "审查", "status": "running", "progress": {"current": review_done, "total": len(review_checks)}})
    elif write_completed:
        stages.append({"id": "review", "label": "审查", "status": "pending", "progress": {"current": 0, "total": len(review_checks)}})
    else:
        stages.append({"id": "review", "label": "审查", "status": "blocked", "progress": {"current": 0, "total": len(review_checks)}})

    # Stage 5: Commit — contracts signed + commits accepted
    review_completed = stages[3]["status"] == "completed" or stages[3]["status"] == "error"
    if accepted_commits > 0 and signed_contracts > 0:
        stages.append({"id": "commit", "label": "归档", "status": "completed", "progress": {"current": min(accepted_commits, signed_contracts), "total": max(signed_contracts, 1)}})
    elif review_completed and signed_contracts > 0:
        stages.append({"id": "commit", "label": "归档", "status": "running", "progress": {"current": accepted_commits, "total": max(signed_contracts, 1)}})
    elif review_completed:
        stages.append({"id": "commit", "label": "归档", "status": "pending", "progress": {"current": 0, "total": 1}})
    else:
        stages.append({"id": "commit", "label": "归档", "status": "blocked", "progress": {"current": 0, "total": 1}})

    return stages


@router.get("/pipeline")
async def get_pipeline_status(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Aggregate all data sources and return 5-stage pipeline status."""
    # Verify project
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_id_str = str(project_id)

    # --- Gather all data in parallel ---
    import asyncio

    async def _count(model, extra_where=None):
        q = select(func.count(model.id)).where(model.project_id == project_id_str)
        if extra_where:
            q = q.where(*extra_where)
        r = await db.execute(q)
        return r.scalar() or 0

    async def _sum_words():
        r = await db.execute(
            select(func.coalesce(func.sum(Chapter.word_count), 0))
            .where(Chapter.project_id == project_id_str)
        )
        return int(r.scalar() or 0)

    async def _chapters_with_outline():
        r = await db.execute(
            select(func.count(Chapter.id))
            .where(Chapter.project_id == project_id_str, Chapter.outline_detail.isnot(None))
        )
        return r.scalar() or 0

    async def _total_blocking():
        r = await db.execute(
            select(func.coalesce(func.sum(ReviewReport.blocking_count), 0))
            .where(ReviewReport.project_id == project_id_str)
        )
        return int(r.scalar() or 0)

    async def _signed_contracts():
        r = await db.execute(
            select(func.count(ChapterContract.id))
            .where(
                ChapterContract.project_id == project_id_str,
                ChapterContract.status.in_([ChContractStatus.SIGNED, ChContractStatus.FULFILLED]),
            )
        )
        return r.scalar() or 0

    async def _accepted_commits():
        r = await db.execute(
            select(func.count(ChapterCommit.id))
            .where(ChapterCommit.project_id == project_id_str, ChapterCommit.status == CommitStatus.ACCEPTED)
        )
        return r.scalar() or 0

    async def _active_debts():
        r = await db.execute(
            select(func.count(ChaseDebt.id))
            .where(
                ChaseDebt.project_id == project_id_str,
                ChaseDebt.status.in_([DebtStatus.ACTIVE, DebtStatus.OVERDUE]),
            )
        )
        return r.scalar() or 0

    async def _overdue_debts():
        r = await db.execute(
            select(func.count(ChaseDebt.id))
            .where(ChaseDebt.project_id == project_id_str, ChaseDebt.status == DebtStatus.OVERDUE)
        )
        return r.scalar() or 0

    async def _total_balance():
        r = await db.execute(
            select(func.coalesce(func.sum(ChaseDebt.current_amount), 0))
            .where(ChaseDebt.project_id == project_id_str, ChaseDebt.status == DebtStatus.ACTIVE)
        )
        return float(r.scalar() or 0)

    async def _avg_review_score():
        r = await db.execute(
            select(func.coalesce(func.avg(ReviewReport.overall_score), 0))
            .where(ReviewReport.project_id == project_id_str)
        )
        return float(r.scalar() or 0)

    (
        worldview_count, character_count, volume_count, total_chapters,
        chapters_written, total_words, chapters_with_outline_cnt,
        reviewed_chapters, total_blocking,
        signed_contracts, accepted_commits,
        active_debt_count, overdue_debt_count, total_balance,
        avg_review_score,
    ) = await asyncio.gather(
        _count(Worldview), _count(Character), _count(Volume), _count(Chapter),
        _count(Chapter, [Chapter.status != "draft" if hasattr(Chapter, 'status') else Chapter.id.isnot(None)]),
        _sum_words(), _chapters_with_outline(),
        _count(ReviewReport), _total_blocking(),
        _signed_contracts(), _accepted_commits(),
        _active_debts(), _overdue_debts(), _total_balance(), _avg_review_score(),
    )

    data = {
        "worldview_count": worldview_count,
        "character_count": character_count,
        "volume_count": volume_count,
        "total_chapters": total_chapters,
        "chapters_written": chapters_written,
        "total_words": total_words,
        "chapters_with_outline": chapters_with_outline_cnt,
        "reviewed_chapters": reviewed_chapters,
        "total_blocking": total_blocking,
        "event_count": reviewed_chapters,
        "signed_contracts": signed_contracts,
        "accepted_commits": accepted_commits,
        "active_debt_count": active_debt_count,
        "overdue_debt_count": overdue_debt_count,
        "total_balance": total_balance,
        "avg_review_score": avg_review_score,
    }

    stages = _compute_stages(data)

    # Build pipeline logs (last 10 events across all tables)
    logs: list[dict] = []

    # Recent chapters
    ch_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id_str)
        .order_by(Chapter.created_at.desc()).limit(5)
    )
    for ch in ch_result.scalars().all():
        logs.append({
            "time": ch.created_at.isoformat() if ch.created_at else "",
            "type": "chapter",
            "message": f"第{ch.chapter_number}章 「{ch.title}」 — {ch.word_count}字",
        })

    # Recent reviews
    rv_result = await db.execute(
        select(ReviewReport).where(ReviewReport.project_id == project_id_str)
        .order_by(ReviewReport.created_at.desc()).limit(5)
    )
    for rv in rv_result.scalars().all():
        logs.append({
            "time": rv.created_at.isoformat() if rv.created_at else "",
            "type": "review",
            "message": f"第{rv.chapter_number}章 审查 — 评分{float(rv.overall_score):.1f}（{rv.blocking_count}个阻断）",
        })

    # Recent commits
    cm_result = await db.execute(
        select(ChapterCommit).where(ChapterCommit.project_id == project_id_str)
        .order_by(ChapterCommit.created_at.desc()).limit(5)
    )
    for cm in cm_result.scalars().all():
        logs.append({
            "time": cm.created_at.isoformat() if cm.created_at else "",
            "type": "commit",
            "message": f"第{cm.chapter_number}章 提交 — {cm.status}",
        })

    # Sort logs by time, newest first, limit 20
    logs.sort(key=lambda x: x.get("time", ""), reverse=True)
    logs = logs[:20]

    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "genre": project.genre,
            "status": project.status,
        },
        "stages": stages,
        "stats": {
            "worldviews": worldview_count,
            "characters": character_count,
            "volumes": volume_count,
            "chapters": total_chapters,
            "chapters_written": chapters_written,
            "total_words": total_words,
            "reviewed_chapters": reviewed_chapters,
            "avg_review_score": round(avg_review_score, 1),
            "active_debts": active_debt_count,
            "overdue_debts": overdue_debt_count,
            "debt_balance": round(total_balance, 2),
            "signed_contracts": signed_contracts,
            "accepted_commits": accepted_commits,
        },
        "logs": logs,
    }


# ── GET: Pipeline transition history ─────────────────────────────────────
@router.get("/pipeline/transitions")
async def get_pipeline_transitions(
    project_id: UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get recent pipeline stage transition history for a project."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    advancer = PipelineAdvancer(db)
    rows = await advancer.get_transitions(str(project_id), limit)
    # Ensure message field for API consumers
    return [
        {**r, "message": f"{r['from_stage']} → {r['to_stage']}"}
        for r in rows
    ]


# ── GET / PATCH: Auto-advance toggle ─────────────────────────────────────
@router.get("/pipeline/auto-advance")
async def get_auto_advance(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return whether auto-advance is enabled for this project."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"auto_advance_enabled": bool(project.auto_advance_enabled)}


@router.patch("/pipeline/auto-advance")
async def set_auto_advance(
    project_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Toggle auto-advance on/off for this project."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    enabled = body.get("auto_advance_enabled", True)
    await db.execute(
        update(Project).where(Project.id == project_id).values(auto_advance_enabled=bool(enabled))
    )
    await db.commit()
    return {"auto_advance_enabled": bool(enabled)}


# ── Phase 14.2: 流水线状态持久化 ──────────────────────────────────────

@router.get("/pipeline/state")
async def get_pipeline_state(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取流水线当前状态（持久化版）。"""
    from app.models.pipeline_state import PipelineState
    from app.services.pipeline_advancer import PipelineStage, PipelineAdvancer

    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 从持久化表读取
    state_result = await db.execute(
        select(PipelineState).where(PipelineState.project_id == project_id)
    )
    state = state_result.scalar_one_or_none()

    # 实时统计
    total_ch = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.project_id == project_id)
    )
    total_chapters = total_ch.scalar() or 0
    reviewed_ch = await db.execute(
        select(func.count(ReviewReport.id)).where(ReviewReport.project_id == project_id)
    )
    reviewed_chapters = reviewed_ch.scalar() or 0
    committed_ch = await db.execute(
        select(func.count(ChapterCommit.id)).where(ChapterCommit.project_id == project_id)
    )
    committed_chapters = committed_ch.scalar() or 0

    return {
        "project_id": str(project_id),
        "current_stage": state.current_stage if state else PipelineStage.INIT.value,
        "last_advanced_at": state.last_advanced_at.isoformat() if state and state.last_advanced_at else None,
        "total_chapters": total_chapters,
        "reviewed_chapters": reviewed_chapters,
        "committed_chapters": committed_chapters,
        "pipeline_runs": state.pipeline_runs if state else 0,
        "error_count": state.error_count if state else 0,
        "last_error": state.last_error if state else None,
        "created_at": state.created_at.isoformat() if state and state.created_at else None,
        "updated_at": state.updated_at.isoformat() if state and state.updated_at else None,
    }