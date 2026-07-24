"""Project initialization service.

Serialises the full init pipeline:
  story_core -> worldview -> characters -> outline (volumes + chapters).
Each step is idempotent: if the upstream data already exists the step is
skipped rather than re-created.
"""
import json
import re
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.app_config import AppConfig
from app.models.character import Character
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.volume import Volume
from app.models.worldview import Worldview
from app.services.ai_service import AIService


class InitState:
    """Holds mutable init progress while the pipeline is running."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.step = "idle"
        self.status = "idle"  # idle | running | completed | failed
        self.error = ""
        self.details: dict = {}
        self.skipped_steps: list[str] = []


def _load_prompt(ai: AIService, name: str) -> dict:
    return ai._load_prompt(name)


def _extract_json(text: str) -> dict | list:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip())
    brace_start = cleaned.find("{")
    brace_end = cleaned.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        cleaned = cleaned[brace_start : brace_end + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        bracket_start = cleaned.find("[")
        bracket_end = cleaned.rfind("]")
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            cleaned = cleaned[bracket_start : bracket_end + 1]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw": text}


async def _ensure_ai_configured(db: AsyncSession) -> None:
    result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config or not config.config:
        raise HTTPException(400, "AI 未配置，请先在设置中添加模型供应商")
    active = config.config.get("active_provider")
    providers = config.config.get("providers", [])
    if not active or not providers:
        raise HTTPException(400, "AI 未配置，请先在设置中选择激活的模型供应商")
    active_provider = next((p for p in providers if p.get("name") == active), None)
    if not active_provider or not active_provider.get("api_key"):
        raise HTTPException(400, "AI 未配置：激活的供应商缺少 API Key")


async def _ensure_project(db: AsyncSession, project_id: str) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _has_story_core(project: Project) -> bool:
    if not project.story_core:
        return False
    keys = ["core_conflict", "theme", "one_sentence", "summary", "raw"]
    return any(project.story_core.get(k) for k in keys)


def _has_worldview(project: Project, worldviews: list[Worldview]) -> bool:
    return len(worldviews) > 0


def _has_characters(project: Project, characters: list[Character]) -> bool:
    return len(characters) > 0


async def _generate_story_core(
    db: AsyncSession,
    project: Project,
    ai: AIService,
    state: InitState,
    params: dict,
) -> str:
    state.step = "story_core"
    state.status = "running"
    prompt = _load_prompt(ai, "story_core")
    genre = params.get("genre") or project.genre or ""
    theme = params.get("theme") or ""
    style = params.get("style") or ""
    ref = params.get("reference_patterns")
    reference_context = ""
    if ref:
        if isinstance(ref, dict):
            reference_context = f"\n\n### 参考书拆解结果（请吸收其中的结构/节奏/设定手法）\n{json.dumps(ref, ensure_ascii=False)}"
        else:
            reference_context = f"\n\n### 参考书拆解结果\n{ref}"
    messages = [
        {"role": "system", "content": prompt["system"]},
        {
            "role": "user",
            "content": prompt["user"].format(
                name=project.name,
                description=project.description or "",
                genre=genre,
            )
            + (
                f"\n\n### 主题倾向\n{theme}" if theme else ""
            )
            + (
                f"\n\n### 写作风格要求\n{style}" if style else ""
            )
            + reference_context,
        },
    ]
    client = await ai._build_client(db)
    try:
        content = await client.chat(messages, temperature=0.8)
    finally:
        await client.close()
    state.details["story_core"] = {"type": "generated", "length": len(content)}
    return content


async def _save_story_core(db: AsyncSession, project: Project, content: str, ai: AIService, state: InitState) -> None:
    parsed = _extract_json(content)
    if not isinstance(parsed, dict):
        parsed = {"raw": content}
    parsed.setdefault("core_conflict", None)
    parsed.setdefault("theme", None)
    parsed.setdefault("innovation", None)
    parsed.setdefault("one_sentence", None)
    parsed.setdefault("versions", [])
    old_version = int((project.story_core or {}).get("_version", 0) or 0)
    old_history = list((project.story_core or {}).get("_history", []))
    if old_version > 0:
        old_history.append(
            {
                "version": old_version,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "data": {k: v for k, v in (project.story_core or {}).items() if not k.startswith("_")},
            }
        )
    new_sc: dict = dict(parsed)
    new_sc["_version"] = old_version + 1
    new_sc["_history"] = old_history
    new_sc["_init_at"] = datetime.now(timezone.utc).isoformat()
    project.story_core = new_sc
    await db.commit()
    state.details["story_core_saved"] = True


async def _generate_and_save_worldview(
    db: AsyncSession, project: Project, ai: AIService, state: InitState
) -> None:
    state.step = "worldview"
    state.status = "running"
    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    content = await ai.generate_worldview(db, project, story_core_text)
    parsed = _extract_json(content)
    if not isinstance(parsed, dict):
        parsed = {"description": content}
    name = parsed.get("name") or f"{project.name or '项目'}的世界观"
    description = parsed.get("description") or parsed.get("overview") or "暂无描述"
    rules = parsed.get("rules") or []
    timeline = parsed.get("timeline") or []
    result = await db.execute(select(Worldview).where(Worldview.project_id == str(project.id)))
    worldview = result.scalar_one_or_none()
    if worldview:
        worldview.name = name
        worldview.description = description
        worldview.rules = rules
        worldview.timeline = timeline
    else:
        worldview = Worldview(project_id=str(project.id), name=name, description=description, rules=rules, timeline=timeline)
        db.add(worldview)
        await db.flush()
    await db.commit()
    state.details["worldview"] = {"type": "generated", "name": name, "rules": len(rules), "timeline": len(timeline)}
    # Knowledge extraction is best-effort and intentionally omitted here to keep init fast and reliable.


async def _generate_and_save_characters(
    db: AsyncSession, project: Project, ai: AIService, state: InitState
) -> None:
    state.step = "characters"
    state.status = "running"
    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    result = await db.execute(select(Worldview).where(Worldview.project_id == str(project.id)))
    worldview = result.scalar_one_or_none()
    worldview_text = worldview.description if worldview else "暂无世界观设定"
    content = await ai.generate_characters(db, project, story_core_text, worldview_text)
    parsed = _extract_json(content)
    if not isinstance(parsed, list):
        parsed = []
    # Remove old characters created during this init so repeated runs stay idempotent.
    await db.execute(delete(Character).where(Character.project_id == str(project.id)))
    for item in parsed:
        if not isinstance(item, dict):
            continue
        db.add(
            Character(
                project_id=str(project.id),
                name=item.get("name") or "未命名角色",
                role_type=item.get("role_type") or "supporting",
                personality=item.get("personality"),
                background=item.get("background"),
                appearance=item.get("appearance"),
                relationships=item.get("relationships"),
                arc=item.get("arc"),
            )
        )
    await db.commit()
    state.details["characters"] = {"type": "generated", "count": len(parsed)}


async def _generate_and_save_outline(
    db: AsyncSession, project: Project, ai: AIService, state: InitState
) -> None:
    state.step = "outline"
    state.status = "running"
    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    wv_result = await db.execute(select(Worldview).where(Worldview.project_id == str(project.id)))
    worldview = wv_result.scalar_one_or_none()
    worldview_text = worldview.description if worldview else "暂无世界观设定"
    ch_result = await db.execute(select(Character).where(Character.project_id == str(project.id)))
    characters = list(ch_result.scalars().all())
    content = await ai.generate_outline(db, project, story_core_text, worldview_text, characters)
    # Persist the raw outline on the project as additional context so downstream
    # pages (OutlinePage / volume/chapter views) can consume it.
    project.context = dict(project.context or {})
    project.context["outline_raw"] = content
    await db.commit()
    state.details["outline"] = {"type": "generated", "length": len(content)}
    # Structured outline parsing (volumes + chapter outlines) can be wired later.
    # For now the full outline text is stored and available to the outline page.


async def init_project(
    db: AsyncSession,
    project_id: str,
    init_params: dict,
    progress_channel: Optional[AsyncIterator] = None,
) -> dict:
    """Run the full initialization pipeline for a project.

    Parameters
    ----------
    db
        Active async database session.
    project_id
        Project identifier (UUID string or valid UUID).
    init_params
        Dict with keys: genre, theme, style, reference_patterns (optional).
    progress_channel
        Optional async iterator callback support; currently progress is written
        into *state* and exposed by :func:`get_init_progress`.
    """
    await _ensure_ai_configured(db)
    project = await _ensure_project(db, project_id)

    # Resolve genre template: set genre text + template_id on project
    genre_text = init_params.get("genre") or project.genre or ""
    if genre_text:
        project.genre = genre_text
        from app.models.genre_template import GenreTemplate
        try:
            t_result = await db.execute(
                select(GenreTemplate).where(GenreTemplate.name == genre_text)
            )
            tmpl = t_result.scalar_one_or_none()
            if tmpl:
                project.template_id = tmpl.id
        except Exception:
            pass
        await db.flush()
    await db.flush()

    ai = AIService()
    state = InitState(project_id)
    state.status = "running"

    try:
        # Step 0: refresh related rows from DB inside the current transaction.
        wv_result = await db.execute(select(Worldview).where(Worldview.project_id == str(project.id)))
        worldviews = list(wv_result.scalars().all())
        ch_result = await db.execute(select(Character).where(Character.project_id == str(project.id)))
        characters = list(ch_result.scalars().all())

        # Step 1: story_core
        if not _has_story_core(project):
            content = await _generate_story_core(db, project, ai, state, init_params)
            await _save_story_core(db, project, content, ai, state)
        else:
            state.skipped_steps.append("story_core")
            state.details["story_core"] = {"type": "skipped", "reason": "existing data present"}

        # Re-fetch in case downstream endpoints wrote concurrently.
        wv_result = await db.execute(select(Worldview).where(Worldview.project_id == str(project.id)))
        worldviews = list(wv_result.scalars().all())

        # Step 2: worldview
        if not _has_worldview(project, worldviews):
            await _generate_and_save_worldview(db, project, ai, state)
        else:
            state.skipped_steps.append("worldview")
            state.details["worldview"] = {"type": "skipped", "reason": "existing data present"}

        # Step 3: characters
        ch_result = await db.execute(select(Character).where(Character.project_id == str(project.id)))
        characters = list(ch_result.scalars().all())
        if not _has_characters(project, characters):
            await _generate_and_save_characters(db, project, ai, state)
        else:
            state.skipped_steps.append("characters")
            state.details["characters"] = {"type": "skipped", "reason": "existing data present"}

        # Step 4: outline
        existing_outline = (project.context or {}).get("outline_raw")
        if not existing_outline:
            await _generate_and_save_outline(db, project, ai, state)
        else:
            state.skipped_steps.append("outline")
            state.details["outline"] = {"type": "skipped", "reason": "existing data present"}

        project.pipeline_stage = "init"
        await db.commit()
        state.status = "completed"
        return _progress_payload(state)

    except HTTPException:
        raise
    except Exception as exc:
        state.status = "failed"
        state.error = str(exc)
        try:
            await db.rollback()
        except Exception:
            pass
        return _progress_payload(state)


def _progress_payload(state: InitState) -> dict:
    return {
        "project_id": state.project_id,
        "step": state.step,
        "status": state.status,
        "error": state.error,
        "skipped_steps": state.skipped_steps,
        "details": state.details,
    }


async def get_init_progress(project_id: str) -> dict:
    """Return the latest init progress stored in the project context.

    During an active run, this reads the last payload written by
    :func:`init_project`; when no init has happened it returns a fresh idle
    payload.
    """
    async for db in get_db():
        try:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if not project:
                return {"project_id": project_id, "status": "not_found", "error": "Project not found"}
            context = project.context or {}
            payload = context.get("_init_progress")
            if payload and isinstance(payload, dict):
                return payload
            # Derive current readiness from persisted data.
            wv = await db.execute(select(Worldview).where(Worldview.project_id == project_id))
            has_wv = bool(wv.scalar_one_or_none())
            ch = await db.execute(select(Character).where(Character.project_id == project_id))
            has_ch = bool(ch.scalar_one_or_none())
            has_sc = bool(_has_story_core(project))
            has_outline = bool(context.get("outline_raw"))
            return {
                "project_id": project_id,
                "status": "completed"
                if all([has_sc, has_wv, has_ch, has_outline])
                else "not_started",
                "step": "outline" if has_outline else ("characters" if has_ch else ("worldview" if has_wv else ("story_core" if has_sc else "idle"))),
                "skipped_steps": [],
                "details": {
                    "story_core": "present" if has_sc else "missing",
                    "worldview": "present" if has_wv else "missing",
                    "characters": "present" if has_ch else "missing",
                    "outline": "present" if has_outline else "missing",
                },
            }
        finally:
            await db.close()
