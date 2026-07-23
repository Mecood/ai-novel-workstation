"""Phase 7a：全自动串联流水线（SSE 流）
串联 review_service → extraction_service → debt_service.evaluate_chapter_reading_power() → contract_service.commit_chapter()。
以 SSE 流逐阶段推送进度，每步失败跳过继续。

关键设计：每个阶段使用独立 AsyncSession，避免一个阶段失败导致整个 session
回滚、后续阶段级联失败。SQLite 不支持真正的并发写，stage 间串行即可。
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db, engine as db_engine
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.review_report import ReviewReport
from app.services.ai_service import AIService
from app.services.review_service import ReviewService
from app.services.extraction_service import ExtractionService
from app.services.debt_service import DebtService
from app.services.contract_service import ContractService

router = APIRouter(tags=["auto-pipeline"])

# ── 流水线阶段枚举 ────────────────────────────────────────────────────
PIPELINE_STAGES = ["review", "extraction", "debt", "commit"]
STAGE_LABELS: dict[str, str] = {
    "review": "审查",
    "extraction": "提取",
    "debt": "评估",
    "commit": "提交",
}

# ── 阶段独立 session 工厂 ─────────────────────────────────────────────
_stage_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


def _new_stage_session() -> AsyncSession:
    """为每个流水线阶段创建独立 session，互不干扰。"""
    return _stage_session()


# ── SSE 帮助函数 ──────────────────────────────────────────────────────
def _sse_event(event_type: str, data: dict) -> str:
    """构造 SSE 数据行（外层 JSON 包）。"""
    payload = json.dumps({
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False)
    return f"data: {payload}\n\n"


def _sse_progress(stage: str, status: str, detail: dict | None = None) -> str:
    """流水线进度事件（前端用于更新进度条）。"""
    payload = json.dumps({
        "type": "progress",
        "stage": stage,
        "status": status,
        "detail": detail or {},
    }, ensure_ascii=False)
    return f"data: {payload}\n\n"


# ── 核心端点 ──────────────────────────────────────────────────────────
async def _run_auto_pipeline(
    db: AsyncSession,
    project_id: UUID,
    chapter_id: UUID,
    *,
    skip_final_commit: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    可复用的流水线执行器。返回 SSE 事件字典。
    供 generation.generate_chapter 串联调用，也可独立作为 auto_pipeline API。

    每个阶段使用独立 session，避免级联回滚。
    """
    # 校验（用注入的主 session）
    project = (await db.execute(
        select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        yield {"type": "pipeline_error", "data": {"error": "Project not found"}}
        return
    chapter = (await db.execute(
        select(Chapter).where(Chapter.id == chapter_id,
                              Chapter.project_id == project_id))).scalar_one_or_none()
    if not chapter:
        yield {"type": "pipeline_error", "data": {"error": "Chapter not found"}}
        return

    # 依赖注入
    ai_service = AIService()
    review_service = ReviewService(ai_service)
    extraction_service = ExtractionService(ai_service)
    debt_service = DebtService(ai_service)
    contract_service = ContractService(ai_service)

    stage_results: dict[str, dict] = {}

    yield {"type": "pipeline_start", "data": {
        "project_id": str(project_id),
        "chapter_id": str(chapter_id),
        "chapter_number": chapter.chapter_number,
        "stages": PIPELINE_STAGES,
    }}

    try:
        # ── Stage 1: 审查 ────────────────────────────────────────
        yield {"type": "progress", "stage": "review", "status": "running",
               "detail": {"label": STAGE_LABELS["review"]}}
        report: dict | None = None
        try:
            s = _new_stage_session()
            try:
                report = await review_service.review_chapter(s, project, chapter)
                rr = ReviewReport(
                    project_id=project.id,
                    chapter_number=chapter.chapter_number,
                    chapter_id=chapter.id,
                    overall_score=report["overall_score"],
                    dimension_scores=report["dimension_scores"],
                    issues=report["issues"],
                    severity_counts=report["severity_counts"],
                    blocking_count=report["blocking_count"],
                    summary=report["summary"],
                )
                s.add(rr)
                await s.commit()
                report["report_id"] = str(rr.id)
            except Exception:
                await s.rollback()
                raise
            finally:
                await s.close()
            stage_results["review"] = {"status": "ok", "result": report}
            yield {"type": "review_complete", "data": {
                "report_id": str(rr.id),
                "overall_score": report["overall_score"],
                "blocking_count": report.get("blocking_count", 0),
            }}
        except Exception as e:
            stage_results["review"] = {"status": "error", "error": str(e)}
            yield {"type": "review_complete", "data": {"error": str(e), "overall_score": None}}

        yield {"type": "progress", "stage": "review", "status": "done",
               "detail": {"score": report.get("overall_score") if report else None}}

        # ── Stage 2: 提取 ────────────────────────────────────────
        yield {"type": "progress", "stage": "extraction", "status": "running",
               "detail": {"label": STAGE_LABELS["extraction"]}}
        extract_result: dict | None = None
        try:
            s = _new_stage_session()
            try:
                extract_result = await extraction_service.extract_events(s, project, chapter)
                await s.commit()
            except Exception:
                await s.rollback()
                raise
            finally:
                await s.close()
            stage_results["extraction"] = {"status": "ok", "result": extract_result}
            yield {"type": "extraction_complete", "data": {
                "event_count": extract_result.get("event_count", 0),
                "knowledge_items": extract_result.get("knowledge_items", 0),
            }}
        except Exception as e:
            stage_results["extraction"] = {"status": "error", "error": str(e)}
            yield {"type": "extraction_complete", "data": {"error": str(e)}}

        yield {"type": "progress", "stage": "extraction", "status": "done",
               "detail": {"event_count": extract_result.get("event_count", 0) if extract_result else 0}}

        # ── Stage 3: 债务评估 ────────────────────────────────────
        yield {"type": "progress", "stage": "debt", "status": "running",
               "detail": {"label": STAGE_LABELS["debt"]}}
        debt_result: dict | None = None
        try:
            s = _new_stage_session()
            try:
                debt_result = await debt_service.evaluate_chapter_reading_power(
                    s, project, chapter)
                await s.commit()
            except Exception:
                await s.rollback()
                raise
            finally:
                await s.close()
            stage_results["debt"] = {"status": "ok", "result": debt_result}
            yield {"type": "debt_complete", "data": {
                "reading_power_score": debt_result.get("reading_power_score"),
                "debt_created": debt_result.get("debt_created"),
            }}
        except Exception as e:
            stage_results["debt"] = {"status": "error", "error": str(e)}
            yield {"type": "debt_complete", "data": {"error": str(e)}}

        yield {"type": "progress", "stage": "debt", "status": "done",
               "detail": {"score": debt_result.get("reading_power_score") if debt_result else None}}

        # ── Stage 4: 提交检查 ────────────────────────────────────
        yield {"type": "progress", "stage": "commit", "status": "running",
               "detail": {"label": STAGE_LABELS["commit"]}}
        commit_result: dict | None = None
        try:
            s = _new_stage_session()
            try:
                commit_result = await contract_service.commit_chapter(s, project, chapter)
                if not skip_final_commit:
                    await s.commit()
            except Exception:
                await s.rollback()
                raise
            finally:
                await s.close()
            stage_results["commit"] = {"status": "ok", "result": commit_result}
            yield {"type": "commit_complete", "data": {"status": commit_result.get("status")}}
        except Exception as e:
            stage_results["commit"] = {"status": "error", "error": str(e)}
            yield {"type": "commit_complete", "data": {"error": str(e)}}

        yield {"type": "progress", "stage": "commit", "status": "done",
               "detail": {"status": commit_result.get("status") if commit_result else None}}

        # ── 触发阶段推进 ───────────────────────────────────────────
        try:
            from app.services.pipeline_advancer import PipelineAdvancer
            s = _new_stage_session()
            try:
                advancer = PipelineAdvancer(s)
                await advancer.check_and_advance(str(project_id), trigger="auto_pipeline_complete")
                await s.commit()
            except Exception:
                await s.rollback()
            finally:
                await s.close()
        except Exception:
            pass

        # ── 完成事件 ───────────────────────────────────────────────
        final_status = (
            "completed"
            if all(sr.get("status") == "ok" for sr in stage_results.values())
            else "completed_with_errors"
        )
        yield {"type": "pipeline_complete", "data": {
            "status": final_status,
            "stages": stage_results,
        }}

    except Exception as e:
        yield {"type": "pipeline_error", "data": {"error": str(e)}}

    yield {"type": "done", "data": {}}


@router.post("/projects/{project_id}/chapters/{chapter_id}/auto-pipeline",
             response_class=StreamingResponse)
async def auto_pipeline(
    project_id: UUID,
    chapter_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    全自动串联流水线：审查 → 提取 → 债务评估 → 提交检查。
    返回 SSE 流，每阶段完成后推送类型事件 + 进度事件。
    出错不阻塞：捕获异常、推送 error 事件，跳过当前阶段继续下一阶段。
    """
    from typing import AsyncGenerator

    async def stream_sse() -> AsyncGenerator[str, None]:
        async for event in _run_auto_pipeline(db, project_id, chapter_id):
            event_type = event.get("type", "event")
            if event_type == "progress":
                # progress 事件特殊格式
                payload = json.dumps({
                    "type": "progress",
                    "stage": event.get("stage"),
                    "status": event.get("status"),
                    "detail": event.get("detail", {}),
                }, ensure_ascii=False)
            else:
                payload = json.dumps({
                    "type": event_type,
                    "data": event.get("data", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(stream_sse(), media_type="text/event-stream")
