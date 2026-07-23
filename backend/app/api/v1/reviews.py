"""
三层评审 API（Phase 7b）。

将原单层 5 维审查升级为 L1 硬指标 → L2 5 维审查 → L3 终审 + 反幻觉 3 定律。
接口路由与响应格式保持向后兼容，响应额外扩展 `tiered_results` 字段。
"""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.review_report import ReviewReport
from app.services.ai_service import AIService
from app.services.review_service import ReviewService, _count_severities
from app.services.tiered_review_service import TieredReviewService

router = APIRouter(prefix="/projects/{project_id}", tags=["reviews"])

ai_service = AIService()
review_service = ReviewService(ai_service)
tiered_review_service = TieredReviewService(ai_service)


# ── POST: Trigger tiered review (SSE stream) ───────────────────────────
@router.post("/chapters/{chapter_number}/review")
async def trigger_review(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a tiered review (L1 → L2 → L3). Returns SSE stream with progress."""
    # Verify project
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify chapter
    chapter_result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    if not chapter.content:
        raise HTTPException(status_code=400, detail="Chapter has no content to review")

    async def event_stream():
        try:
            # L1 开始
            yield f"data: {json.dumps({'type': 'progress', 'message': 'L1 硬指标检查...', 'tier': 'l1', 'phase': 'start'})}\n\n"

            tiered_results: dict[str, Any] = await tiered_review_service.run_tiered_review(
                db, project, chapter
            )

            l1_status = tiered_results["l1"]["status"]
            yield f"data: {json.dumps({'type': 'progress', 'message': f'L1 完成: {l1_status}', 'tier': 'l1', 'phase': 'complete', 'status': l1_status})}\n\n"

            if l1_status == "FAIL":
                # L1 不通过，直接保存并返回
                pass
            else:
                # L2 开始
                yield f"data: {json.dumps({'type': 'progress', 'message': 'L2 5 维审查...', 'tier': 'l2', 'phase': 'start'})}\n\n"
                l2 = tiered_results.get("l2")
                if l2:
                    l2_score = l2.get("overall_score", 0)
                    l2_blocking = l2.get("blocking_count", 0)
                    yield f"data: {json.dumps({'type': 'progress', 'message': f'L2 完成: 评分 {l2_score}, {l2_blocking} 个阻断', 'tier': 'l2', 'phase': 'complete', 'score': l2_score, 'blocking_count': l2_blocking})}\n\n"

                # L3 开始
                yield f"data: {json.dumps({'type': 'progress', 'message': 'L3 终审中...', 'tier': 'l3', 'phase': 'start'})}\n\n"
                l3 = tiered_results.get("l3")
                if l3:
                    verdict = l3.get("verdict", "REVISE")
                    yield f"data: {json.dumps({'type': 'progress', 'message': f'L3 裁决: {verdict}', 'tier': 'l3', 'phase': 'complete', 'verdict': verdict})}\n\n"

            # 保存到数据库
            yield f"data: {json.dumps({'type': 'progress', 'message': '正在保存...', 'tier': None, 'phase': 'saving'})}\n\n"

            # Upsert: check if a review already exists for this chapter
            existing_result = await db.execute(
                select(ReviewReport).where(
                    ReviewReport.project_id == project_id,
                    ReviewReport.chapter_number == chapter_number,
                )
            )
            existing = existing_result.scalar_one_or_none()

            # 构建兼容性报告（tiered_results 中包含所有数据）
            l2 = tiered_results.get("l2") or {}
            l3 = tiered_results.get("l3") or {}

            if existing:
                # 更新现有
                existing.overall_score = l2.get("overall_score", 0.0)
                existing.dimension_scores = l2.get("dimension_scores", {})
                existing.severity_counts = _count_severities(l2.get("issues", []))
                existing.issues = l2.get("issues", [])
                existing.blocking_count = l2.get("blocking_count", 0)
                existing.summary = l3.get("summary", l2.get("summary", ""))
                existing.tiered_results = tiered_results
            else:
                review_record = ReviewReport(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    overall_score=l2.get("overall_score", 0.0),
                    dimension_scores=l2.get("dimension_scores", {}),
                    severity_counts=_count_severities(l2.get("issues", [])),
                    issues=l2.get("issues", []),
                    blocking_count=l2.get("blocking_count", 0),
                    summary=l3.get("summary", l2.get("summary", "")),
                    tiered_results=tiered_results,
                )
                db.add(review_record)

            await db.commit()

            yield f"data: {json.dumps({'type': 'complete', 'tiered_results': tiered_results})}\n\n"

            # 触发阶段推进
            try:
                from app.services.pipeline_advancer import PipelineAdvancer
                advancer = PipelineAdvancer(db)
                await advancer.check_and_advance(str(project_id), trigger="review_complete")
            except Exception:
                pass

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── GET: Retrieve review report for a chapter ──────────────────────────
@router.get("/chapters/{chapter_number}/review")
async def get_review_report(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the quality review report for a specific chapter."""
    result = await db.execute(
        select(ReviewReport).where(
            ReviewReport.project_id == project_id,
            ReviewReport.chapter_number == chapter_number,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No review found for this chapter")

    return {
        "id": str(report.id),
        "project_id": str(report.project_id),
        "chapter_number": report.chapter_number,
        "overall_score": float(report.overall_score),
        "dimension_scores": report.dimension_scores or {},
        "severity_counts": report.severity_counts or {},
        "issues": report.issues or [],
        "blocking_count": report.blocking_count or 0,
        "summary": report.summary or "",
        "report_file": report.report_file,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "tiered_results": report.tiered_results or None,
    }


# ── GET: Quality trend across chapters ─────────────────────────────────
@router.get("/reviews/trend")
async def get_review_trend(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the overall score trend across reviewed chapters."""
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(ReviewReport)
        .where(ReviewReport.project_id == project_id)
        .order_by(ReviewReport.chapter_number.asc())
    )
    reports = result.scalars().all()

    if not reports:
        return {"chapters": [], "scores": []}

    return {
        "chapters": [r.chapter_number for r in reports],
        "scores": [float(r.overall_score) for r in reports],
    }


# ── Phase 15.2：用户裁决 blocking 问题 ──────────────────────────────
@router.post("/reviews/{review_id}/decide")
async def decide_review(
    project_id: UUID,
    review_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """用户裁决 blocking 问题。
    decision: accept=跳过继续, reject=回退修改, modify=指定修改方案
    """
    result = await db.execute(
        select(ReviewReport).where(
            ReviewReport.id == review_id,
            ReviewReport.project_id == project_id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Review report not found")

    decision = body.get("decision", "accept")
    user_note = body.get("user_note", "")

    report.user_decision = decision
    report.user_note = user_note
    await db.commit()
    await db.refresh(report)

    return {
        "review_id": str(report.id),
        "decision": decision,
        "user_note": user_note,
        "chapter_number": report.chapter_number,
    }


# ── GET: Per-dimension score trend ─────────────────────────────────────
@router.get("/reviews/dimensions")
async def get_dimension_trend(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get per-dimension average score trend across reviewed chapters."""
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(ReviewReport)
        .where(ReviewReport.project_id == project_id)
        .order_by(ReviewReport.chapter_number.asc())
    )
    reports = result.scalars().all()

    if not reports:
        return {"chapters": [], "dimensions": {}}

    # Collect dimension names from all reports
    all_dimensions: set[str] = set()
    for r in reports:
        scores = r.dimension_scores or {}
        all_dimensions.update(scores.keys())

    dimensions_data: dict[str, list[float | None]] = {d: [] for d in sorted(all_dimensions)}

    for r in reports:
        scores = r.dimension_scores or {}
        for d in dimensions_data:
            dimensions_data[d].append(float(scores.get(d, 0)))

    return {
        "chapters": [r.chapter_number for r in reports],
        "dimensions": dimensions_data,
    }
