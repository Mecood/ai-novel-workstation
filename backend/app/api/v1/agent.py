"""
Agent chat endpoint — multi-step tool-use agent loop.

POST /projects/{project_id}/agent/chat
  payload: { task: str, max_steps?: int, model?: str, temperature?: float }

The endpoint wires the project-scoped tool set (outline/character/summary/
worldview/foreshadowing lookups) into AIClient.agent_chat so the AI can
query project data before composing its reply.
"""
import asyncio
from typing import Any, Mapping

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.ai_client import AIClient
from app.core.database import get_db
from app.models.project import Project
from app.models.app_config import AppConfig
from app.services.tools import TOOL_REGISTRY, get_tool_definitions, get_tool_executor


router = APIRouter(prefix="/projects/{project_id}/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000)
    max_steps: int = Field(10, ge=1, le=20)
    model: str | None = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    system: str | None = None


class AgentStep(BaseModel):
    step: int
    role: str
    content: str = ""
    tool_call_id: str = ""
    tool_name: str | None = None
    tool_result: str = ""


class AgentChatResponse(BaseModel):
    content: str
    total_steps: int
    steps: list[AgentStep]


def _tool_executor(project_id: str) -> Any:
    """Build a (name, kwargs) -> result executor that closes over the project."""

    async def _dispatch(name: str, kwargs: Mapping[str, Any]) -> str:
        executor = get_tool_executor(name)
        if executor is None:
            return f"UNKNOWN tool: {name}"

        db = None
        result: str = ""
        try:
            async for session in get_db():
                db = session
                result = executor(project_id=project_id, db=db, **dict(kwargs))
                if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                    result = await result  # type: ignore[arg-type]
                break
        except Exception as exc:
            result = f"ERROR executing {name}: {exc}"
        finally:
            if db is not None:
                await db.close()
        return str(result)

    return _dispatch


def _build_client_from_provider(provider: dict[str, Any]) -> AIClient:
    """Lifted from AIService._build_client so the endpoint owns its client."""
    url = provider.get("url")
    api_key = provider.get("api_key")
    model = provider.get("selected_model")
    if not url or not api_key:
        raise HTTPException(
            400,
            "AI 提供商配置不完整（缺少 url 或 api_key）",
        )
    if not model:
        raise HTTPException(400, "请在设置页面选择一个模型")
    return AIClient(url=url, api_key=api_key, model=model)


async def _resolve_provider(db: AsyncSession) -> AIClient:
    """Return an AIClient configured with the active provider in AppConfig."""
    result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    app_config = result.scalar_one_or_none()  # type: ignore[assignment]
    config = (app_config.config if app_config else None) or {}  # type: ignore[union-attr]

    active_idx = config.get("active_provider")
    providers = config.get("providers") or []
    if not providers:
        raise HTTPException(
            400,
            "未配置 AI 提供商，请前往设置页面添加并选中一个提供商",
        )
    # Fallback: if no active_provider is set, use the first provider
    if active_idx is None:
        provider = providers[0]
    elif isinstance(active_idx, int):
        provider = providers[active_idx] if 0 <= active_idx < len(providers) else None
    else:
        provider = next(
            (p for p in providers if p.get("name") == active_idx), None
        )
    if not provider:
        raise HTTPException(
            400, f"未找到激活的 AI 提供商：{active_idx}"
        )
    return _build_client_from_provider(provider)


async def _ensure_project(db: AsyncSession, project_id: UUID) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )  # type: ignore[arg-type]
    project = result.scalar_one_or_none()  # type: ignore[assignment]
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/chat")
async def agent_chat(
    project_id: UUID,
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a tool-use agent loop for the project and return the final answer."""
    await _ensure_project(db, project_id)
    project_id_str = str(project_id)

    ai_client = await _resolve_provider(db)
    try:
        tools = get_tool_definitions()
        executor = _tool_executor(project_id_str)
        system = (
            request.system
            or (
                "你是一个小说创作助手，负责根据项目资料（大纲、角色、前章摘要、"
                "世界观、伏笔状态）回答创作相关问题。需要时请先调用工具获取资料。"
            )
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": request.task},
        ]

        final = await ai_client.agent_chat(
            messages=messages,
            tools=tools,
            tool_executor=executor,
            model=request.model,
            temperature=request.temperature,
            max_steps=request.max_steps,
        )

        # Reconstruct a readable step log for transparency.
        steps: list[AgentStep] = []
        step = 1
        for msg in messages:
            role = msg.get("role", "")
            if role == "tool":
                steps.append(
                    AgentStep(
                        step=step,
                        role="tool",
                        content=msg.get("content", ""),
                        tool_call_id=msg.get("tool_call_id", ""),
                        tool_name=msg.get("name"),
                        tool_result=msg.get("content", ""),
                    )
                )
                step += 1

        return AgentChatResponse(
            content=final.get("content") or "",
            total_steps=len(steps),
            steps=steps,
        )
    finally:
        await ai_client.close()


@router.get("/tools")
async def list_agent_tools():
    """Return the tool schemas available to the agent (no DB needed)."""
    return {"tools": get_tool_definitions()}
