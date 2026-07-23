"""追读力债务系统 API 路由。"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.override_contract import ConstraintType, RationaleType
from app.services.ai_service import AIService
from app.services.debt_service import DebtService

router = APIRouter(prefix="/projects/{project_id}/debt", tags=["debt"])
ai_service = AIService()
debt_service = DebtService(ai_service)


# ── 1) 债务总览 ─────────────────────────────────────────────────────────
@router.get("/summary")
async def get_debt_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取项目债务总览（Dashboard 数据）。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return await debt_service.get_debt_summary(db, str(project_id))


# ── 2) 单章债务快照 ────────────────────────────────────────────────────
@router.get("/chapter/{chapter_number}")
async def get_chapter_debt(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单章的债务快照（含追读力元数据 + 关联债务）。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # 获取追读力元数据
    rp = await debt_service.get_chapter_reading_power(db, str(project_id), chapter_number)

    # 获取该章节产生的债务
    from app.models.chase_debt import ChaseDebt
    from sqlalchemy import select
    result = await db.execute(
        select(ChaseDebt).where(
            ChaseDebt.project_id == str(project_id),
            ChaseDebt.source_chapter == chapter_number,
        ).order_by(ChaseDebt.created_at)
    )
    debts = result.scalars().all()

    return {
        "reading_power": rp,
        "debts": [debt_service._debt_to_dict(d) for d in debts],
    }


# ── 3) 触发利息计算 ─────────────────────────────────────────────────────
@router.post("/accrue")
async def trigger_interest_accrual(
    project_id: UUID,
    chapter_number: int = Query(..., description="当前章节号（用于日志）"),
    db: AsyncSession = Depends(get_db),
):
    """手动触发利息计算（对所有 active 债务计息）。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    count = await debt_service.accrue_interest(db, str(project_id), chapter_number)
    await db.commit()
    return {"message": f"已对 {count} 笔债务计息", "affected_count": count}


# ── 4) 追读力趋势 ───────────────────────────────────────────────────────
@router.get("/reading-power")
async def get_reading_power_trend(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取追读力趋势（所有章节的追读力评分 + 债务余额）。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return await debt_service.get_reading_power_trend(db, str(project_id))


# ── 5) 评估单章追读力 ───────────────────────────────────────────────────
@router.post("/chapters/{chapter_number}/evaluate-reading-power")
async def evaluate_chapter_reading_power(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """评估单章追读力（LLM 调用），自动处理债务创建/偿还。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    chapter = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    chapter = chapter.scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    result = await debt_service.evaluate_chapter_reading_power(db, project, chapter)
    await db.commit()
    return result


# ── 6) Override Contract 列表 ───────────────────────────────────────────
@router.get("/contracts")
async def list_contracts(
    project_id: UUID,
    status: str | None = Query(None, description="按状态筛选"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取 Override Contract 列表。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return await debt_service.get_contracts(
        db, str(project_id), status=status, offset=offset, limit=limit,
    )


# ── 7) 创建 Override Contract ──────────────────────────────────────────
@router.post("/contracts")
async def create_contract(
    project_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """创建 Override Contract。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # 参数校验
    constraint_type = body.get("constraint_type")
    rationale_type = body.get("rationale_type")
    rationale_text = body.get("rationale_text")
    due_chapter = body.get("due_chapter")
    chapter_number = body.get("chapter_number")

    if not constraint_type or not rationale_type or not rationale_text or not due_chapter:
        raise HTTPException(400, "缺少必填字段：constraint_type, rationale_type, rationale_text, due_chapter")

    # 校验枚举值
    if constraint_type not in [e.value for e in ConstraintType]:
        raise HTTPException(400, f"无效的 constraint_type，可选：{[e.value for e in ConstraintType]}")
    if rationale_type not in [e.value for e in RationaleType]:
        raise HTTPException(400, f"无效的 rationale_type，可选：{[e.value for e in RationaleType]}")

    contract = await debt_service.create_contract(
        db, str(project_id),
        chapter_number=chapter_number or 0,
        constraint_type=ConstraintType(constraint_type),
        rationale_type=RationaleType(rationale_type),
        rationale_text=rationale_text,
        due_chapter=due_chapter,
        payback_plan=body.get("payback_plan"),
        auto_extend=body.get("auto_extend", False),
    )
    await db.commit()
    return debt_service._contract_to_dict(contract)