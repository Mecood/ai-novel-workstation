import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.app_config import AppConfig
from app.models.project import Project
from app.services.ai_service import AIService

router = APIRouter(prefix="/projects/{project_id}/story-core", tags=["story-core"])
ai_service = AIService()


class StoryCoreData(BaseModel):
    core_conflict: Optional[str] = None
    theme: Optional[str] = None
    innovation: Optional[str] = None
    one_sentence: Optional[str] = None
    versions: list[dict] = []


class StoryCoreResponse(BaseModel):
    story_core: Optional[dict] = None


class GenerateStoryCoreResponse(BaseModel):
    content: str
    parsed: dict


async def _ensure_ai_configured(db: AsyncSession) -> None:
    result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config or not config.config:
        raise HTTPException(status_code=400, detail="AI 未配置，请先在设置中添加模型供应商")

    active = config.config.get("active_provider")
    providers = config.config.get("providers", [])
    if not active or not providers:
        raise HTTPException(status_code=400, detail="AI 未配置，请先在设置中选择激活的模型供应商")

    active_provider = next((p for p in providers if p.get("name") == active), None)
    if not active_provider or not active_provider.get("api_key"):
        raise HTTPException(status_code=400, detail="AI 未配置：激活的供应商缺少 API Key")


@router.get("", response_model=StoryCoreResponse)
async def get_story_core(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return StoryCoreResponse(story_core=project.story_core)


@router.put("", response_model=StoryCoreResponse)
async def update_story_core(
    project_id: UUID,
    data: StoryCoreData,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.story_core = data.model_dump()
    await db.commit()
    await db.refresh(project)
    return StoryCoreResponse(story_core=project.story_core)


@router.post("/generate", response_model=GenerateStoryCoreResponse)
async def generate_story_core(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await _ensure_ai_configured(db)

    content = await ai_service.generate_story_core(project)

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            parsed = {"raw": content}
    except json.JSONDecodeError:
        parsed = {"raw": content}

    parsed.setdefault("core_conflict", None)
    parsed.setdefault("theme", None)
    parsed.setdefault("innovation", None)
    parsed.setdefault("one_sentence", None)
    parsed.setdefault("versions", [])

    return GenerateStoryCoreResponse(content=content, parsed=parsed)
