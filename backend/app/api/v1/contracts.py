"""合同系统 API 路由 — 写前签约 + 写后提交。"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.chapter import Chapter
from app.services.ai_service import AIService
from app.models.chapter_contract import ChapterContract, ContractStatus
from app.models.chapter_commit import ChapterCommit
from app.services.contract_service import ContractService
router = APIRouter(
    prefix="/projects/{project_id}/chapters/{chapter_number}",
    tags=["contracts"],
)
ai_service = AIService()
contract_service = ContractService(ai_service)


# ── 1) 签署契约 ─────────────────────────────────────────────────────────
@router.post("/contract/sign")
async def sign_contract(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """
    写前签约：根据大纲细纲+世界观+角色设定生成契约并签署。
    返回：契约详情（含 required_nodes, optional_nodes, constraints, forbidden_zones）
    """
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

    result = await contract_service.sign_contract(db, project, chapter)
    await db.commit()
    return result


# ── 2) 获取契约 ─────────────────────────────────────────────────────────
@router.get("/contract")
async def get_contract(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """获取一章的最新契约。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    contract = await contract_service.get_contract(
        db, str(project_id), chapter_number
    )
    if not contract:
        raise HTTPException(404, "该章节尚未签署契约")
    return contract


# ── 3) 提交章节 ─────────────────────────────────────────────────────────
@router.post("/commit")
async def commit_chapter(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """
    提交章节：汇总审查结果+履行结果+提取结果，判定通过/拒绝。
    返回：提交记录（含 status, rejection_reasons, fulfillment_result, review_result）
    """
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

    result = await contract_service.commit_chapter(db, project, chapter)
    await db.commit()

    # 触发阶段推进
    try:
        from app.services.pipeline_advancer import PipelineAdvancer
        advancer = PipelineAdvancer(db)
        await advancer.check_and_advance(str(project_id), trigger="commit_completed")
    except Exception:
        pass

    # 同步更新契约状态（如果 commit 改了契约 status）
    # 已在 commit_chapter 内部处理

    return result


# ── 4) 获取提交记录 ─────────────────────────────────────────────────────
@router.get("/commit")
async def get_commit(
    project_id: UUID,
    chapter_number: int,
    version: int | None = Query(None, description="指定版本号，不传则取最新"),
    db: AsyncSession = Depends(get_db),
):
    """获取一章的提交记录，默认取最新版本。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    commit = await contract_service.get_commit(
        db, str(project_id), chapter_number, version=version
    )
    if not commit:
        raise HTTPException(404, "该章节尚未提交")
    return commit


# ── 5) 提交历史（可选） ─────────────────────────────────────────────────
@router.get("/commit/history")
async def get_commit_history(
    project_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """获取一章的所有提交历史。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    return await contract_service.get_commit_history(
        db, str(project_id), chapter_number
    )


# ── 6) 审计日志 ───────────────────────────────────────────────────
@router.get("/contract/audit")
async def get_audit_logs(
    project_id: UUID,
    chapter_number: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    获取章节契约审计日志（append-only）。
    记录所有契约变更：CREATE / UPDATE / STATUS_CHANGE / COMMIT。
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    return await contract_service.get_audit_logs(
        db, str(project_id), chapter_number, limit=limit
    )


# ════════════════════════════════════════════════════════════════════════
# 项目级路由：全局契约概览
# ════════════════════════════════════════════════════════════════════════
project_router = APIRouter(prefix="/projects/{project_id}", tags=["contracts"])


@project_router.get("/contracts/all")
async def list_all_contracts(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取项目所有章节的契约概览。"""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    project_id_str = str(project_id)

    # 1) 查询项目所有章节（按章节号升序）
    chapters_result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = chapters_result.scalars().all()

    # 2) 批量查询所有契约 + 最新提交记录（只查本项目）
    contracts_result = await db.execute(
        select(ChapterContract)
        .where(ChapterContract.project_id == project_id_str)
        .order_by(ChapterContract.chapter_number)
    )
    contracts_by_chapter = {
        c.chapter_number: c for c in contracts_result.scalars().all()
    }

    commits_result = await db.execute(
        select(ChapterCommit)
        .where(ChapterCommit.project_id == project_id_str)
        .order_by(ChapterCommit.chapter_number, ChapterCommit.commit_version.desc())
    )
    # 取每章最新版本提交
    latest_commits_by_chapter: dict[int, ChapterCommit] = {}
    for commit in commits_result.scalars().all():
        if commit.chapter_number not in latest_commits_by_chapter:
            latest_commits_by_chapter[commit.chapter_number] = commit

    # 3) 组装返回数据
    result = []
    for ch in chapters:
        cnum = ch.chapter_number
        contract = contracts_by_chapter.get(cnum)
        commit = latest_commits_by_chapter.get(cnum)

        contract_status = "pending"  # 未签署
        if contract:
            contract_status = contract.status  # signed / fulfilled / rejected

        submit_status = "pending"  # 未提交
        if commit:
            submit_status = commit.status  # accepted / rejected

        result.append({
            "chapter_number": cnum,
            "chapter_title": ch.title,
            "contract_status": contract_status,
            "submit_status": submit_status,
            "has_contract": contract is not None,
            "has_commit": commit is not None,
        })

    return {
        "total": len(result),
        "signed": sum(1 for r in result if r["contract_status"] == "signed"),
        "submitted": sum(
            1 for r in result if r["submit_status"] in ("accepted", "rejected")
        ),
        "accepted": sum(1 for r in result if r["submit_status"] == "accepted"),
        "rejected": sum(1 for r in result if r["submit_status"] == "rejected"),
        "contracts": result,
    }