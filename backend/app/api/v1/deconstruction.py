"""Reference book deconstruction API routes.

Splits a reference novel text into transferable craft patterns,
never original canon facts. Supports quick mode (golden 3 chapters
+ ratings) and deep mode (per-chapter plot nodes → aggregate).
"""
import json
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.deconstruction_history import DeconstructionHistory
from app.services.deconstruction_service import DeconstructionService
from app.core.ai_client import AIClient
from app.models.app_config import AppConfig


router = APIRouter(prefix="/deconstruction", tags=["deconstruction"])


class DeconstructRequest(BaseModel):
    reference_text: str
    analysis_mode: str = "quick"
    target_genre: str = "仙侠"
    reference_title: str = ""


def _build_ai_client(app_config: AppConfig | None) -> AIClient | None:
    """Build AIClient from AppConfig; return None on failure."""
    if not app_config or not app_config.config:
        return None
    providers = app_config.config.get("providers") or []
    active = app_config.config.get("active_provider")
    if isinstance(active, int):
        provider = providers[active] if 0 <= active < len(providers) else None
    else:
        provider = next((p for p in providers if p.get("name") == active), None)
    if not provider:
        return None
    url = provider.get("url")
    api_key = provider.get("api_key")
    model = provider.get("selected_model")
    if not (url and api_key and model):
        return None
    return AIClient(url=url, api_key=api_key, model=model)


@router.post("/analyze")
async def analyze_reference(
    data: DeconstructRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Optional[str] = Query(None, description="关联项目ID，留空则存全局历史"),
):
    """Full analysis (quick or deep mode)."""
    text = data.reference_text
    mode = data.analysis_mode if data.analysis_mode in ("quick", "deep") else "quick"
    if not text or not text.strip():
        raise HTTPException(400, "reference_text is required")

    cfg_result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    app_config = cfg_result.scalar_one_or_none()
    ai_client = _build_ai_client(app_config)

    service = DeconstructionService(ai_client=ai_client)
    result = await service.analyze_reference(
        book_text=text,
        analysis_mode=mode,
        target_genre=data.target_genre,
        reference_title=data.reference_title,
    )

    hist = DeconstructionHistory(
        project_id=project_id,
        reference_title=data.reference_title or "未知参考书",
        analysis_mode=mode,
        raw_result=result,
        target_genre=data.target_genre,
    )
    db.add(hist)
    await db.commit()

    return result


@router.post("/quick")
async def quick_analyze(
    data: DeconstructRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Optional[str] = Query(None),
):
    """Quick mode: golden 3 chapters + overall structure + rating report."""
    text = data.reference_text
    if not text or not text.strip():
        raise HTTPException(400, "reference_text is required")

    cfg_result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    app_config = cfg_result.scalar_one_or_none()
    ai_client = _build_ai_client(app_config)

    service = DeconstructionService(ai_client=ai_client)
    result = await service.analyze_reference(
        book_text=text,
        analysis_mode="quick",
        target_genre=data.target_genre,
        reference_title=data.reference_title,
    )

    hist = DeconstructionHistory(
        project_id=project_id,
        reference_title=data.reference_title or "未知参考书",
        analysis_mode="quick",
        raw_result=result,
        target_genre=data.target_genre,
    )
    db.add(hist)
    await db.commit()

    return result


@router.post("/deep")
async def deep_analyze(
    data: DeconstructRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Optional[str] = Query(None),
):
    """Deep mode: per-chapter plot nodes → aggregate → story arcs."""
    text = data.reference_text
    if not text or not text.strip():
        raise HTTPException(400, "reference_text is required")

    cfg_result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    app_config = cfg_result.scalar_one_or_none()
    ai_client = _build_ai_client(app_config)

    service = DeconstructionService(ai_client=ai_client)
    result = await service.analyze_reference(
        book_text=text,
        analysis_mode="deep",
        target_genre=data.target_genre,
        reference_title=data.reference_title,
    )

    hist = DeconstructionHistory(
        project_id=project_id,
        reference_title=data.reference_title or "未知参考书",
        analysis_mode="deep",
        raw_result=result,
        target_genre=data.target_genre,
    )
    db.add(hist)
    await db.commit()

    return result


@router.get("/history")
async def get_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: Optional[str] = Query(None, description="限定项目；None 返回全局"),
):
    """Get deconstruction history."""
    query = select(DeconstructionHistory).order_by(DeconstructionHistory.created_at.desc())
    if project_id:
        query = query.where(DeconstructionHistory.project_id == project_id)
    result = await db.execute(query.limit(50))
    rows = list(result.scalars().all())
    return [
        {
            "id": str(r.id),
            "reference_title": r.reference_title,
            "analysis_mode": r.analysis_mode,
            "target_genre": r.target_genre,
            "created_at": str(r.created_at),
        }
        for r in rows
    ]


@router.get("/history/{history_id}")
async def get_history_detail(
    history_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get full deconstruction result by history_id."""
    result = await db.execute(
        select(DeconstructionHistory).where(DeconstructionHistory.id == history_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "History not found")
    return item.raw_result
