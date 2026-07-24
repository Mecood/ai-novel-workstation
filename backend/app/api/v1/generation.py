"""AI generation API routes with SSE streaming."""
import json
import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.core.config import settings
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.character import Character
from app.models.chapter import Chapter
from app.models.volume import Volume
from app.models.knowledge import Knowledge
from app.services.ai_service import AIService
from app.services.vector_search import VectorSearchService
from app.services.version_service import version_service

# ── Phase 7a：骨架强制检查 ──────────────────────────────────────────
def _has_valid_skeleton(chapter: Chapter) -> tuple[bool, str]:
    """检查章节是否有有效骨架。返回 (ok, message)。"""
    skeleton = chapter.skeleton or {}
    cbn = skeleton.get("cbn")
    cpns = skeleton.get("cpns")
    cen = skeleton.get("cen")
    # 至少要有 CBN 的 5 节拍 或 任一非空骨架部分
    cbn_ok = cbn and len(cbn.get("beats", [])) == 5
    cpns_ok = cpns and cpns.get("promises")
    cen_ok = cen and cen.get("events")
    if cbn_ok or cpns_ok or cen_ok:
        return True, ""
    return False, (
        "第 {num} 章未定义骨架。请先在写作工作区填写 CBN（5节拍）/ "
        "CPNs（承诺清单）/ CEN（事件清单）后再生成章节。"
    ).format(num=chapter.chapter_number)


router = APIRouter(prefix="/projects/{project_id}")
ai_service = AIService()
vector_service = VectorSearchService(
    persist_dir=settings.storage_path,
    siliconflow_api_key=settings.SILICONFLOW_API_KEY or "",
)


async def _save_knowledge(
    db: AsyncSession,
    project_id: str,
    items: list[dict],
    source_type: str,
    source_id: str | None = None,
):
    """Save extracted knowledge items to database."""
    for item in items:
        if not item.get("title") or not item.get("content"):
            continue
        kn = Knowledge(
            project_id=project_id,
            title=item["title"],
            content=item["content"],
            category=item.get("category", "general"),
            tags=item.get("tags", []),
            source="auto",
            source_type=source_type,
            source_id=source_id,
        )
        db.add(kn)
    await db.commit()


def _extract_json(text: str):
    """Extract JSON from AI response, stripping markdown code fences if present."""
    # Try parsing the raw text first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Strip ```json ... ``` or ``` ... ```
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', text.strip())
    cleaned = re.sub(r'\n?```\s*$', '', cleaned.strip())
    # Try to find JSON object in case there's extra text before/after
    brace_start = cleaned.find('{')
    brace_end = cleaned.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        cleaned = cleaned[brace_start:brace_end + 1]
    return json.loads(cleaned)


@router.post("/story-core/generate")
async def generate_story_core(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate story core for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Save current version and history BEFORE generating
    old_version = int((project.story_core or {}).get("_version", 0) or 0)
    old_history = list((project.story_core or {}).get("_history", []))

    content = await ai_service.generate_story_core(db, project)

    try:
        new_sc = _extract_json(content)
    except json.JSONDecodeError:
        new_sc = {"raw": content}

    # Merge version tracking into the new story core
    new_version = old_version + 1
    # Save current state to history (before overwriting)
    if old_version > 0:
        old_snapshot = {
            "version": old_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": {k: v for k, v in (project.story_core or {}).items() if not k.startswith("_")},
        }
        old_history.append(old_snapshot)

    new_sc["_version"] = new_version
    new_sc["_based_on"] = {}
    new_sc["_history"] = old_history
    project.story_core = new_sc
    await db.commit()

    # Mark downstream stale
    await version_service.mark_downstream_stale(db, project_id, "story_core")

    return {"content": content, "version": new_version}


@router.post("/worldview/generate")
async def generate_worldview(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate worldview for a project."""
    project = await db.get(Project, project_id)
    if not project or not project.story_core:
        raise HTTPException(404, "Project or story core not found")

    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    content = await ai_service.generate_worldview(db, project, story_core_text)

    try:
        parsed = _extract_json(content)
    except (json.JSONDecodeError, ValueError):
        parsed = {"description": content}

    name = parsed.get("name") or f"{project.name or '项目'}的世界观"
    description = (
        parsed.get("description")
        or parsed.get("overview")
        or "暂无描述"
    )
    rules = parsed.get("rules") or []
    timeline = parsed.get("timeline") or []

    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()

    # Version management: get upstream versions
    upstream_versions = await version_service.get_upstream_versions(db, project_id)
    based_on = {"story_core": upstream_versions.get("story_core", 0)}

    if worldview:
        # Save old version to history before updating
        await version_service.save_and_bump(db, worldview, based_on)
        worldview.name = name
        worldview.description = description
        worldview.rules = rules
        worldview.timeline = timeline
    else:
        worldview = Worldview(
            project_id=project_id,
            name=name,
            description=description,
            rules=rules,
            timeline=timeline,
        )
        db.add(worldview)
        await db.flush()
        await version_service.save_and_bump(db, worldview, based_on)

    # Clear stale flag
    worldview._stale = "false"
    await db.commit()

    # Mark downstream stale
    await version_service.mark_downstream_stale(db, project_id, "worldview")
    await db.commit()

    # Auto-extract knowledge from worldview
    try:
        kn_items = await ai_service.extract_knowledge(db, content, "世界观设定")
        await _save_knowledge(db, project_id, kn_items, "worldview", str(worldview.id))
    except Exception:
        pass  # Don't fail generation if knowledge extraction fails

    return {"content": content, "version": worldview._version}


@router.post("/characters/generate")
async def generate_characters(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate characters for a project."""
    project = await db.get(Project, project_id)
    if not project or not project.story_core:
        raise HTTPException(404, "Project or story core not found")

    # Get or generate worldview
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()

    story_core_text = json.dumps(project.story_core, ensure_ascii=False)
    worldview_text = worldview.description if worldview else "暂无世界观设定"

    content = await ai_service.generate_characters(db, project, story_core_text, worldview_text)

    try:
        parsed = _extract_json(content)
    except (json.JSONDecodeError, ValueError):
        parsed = []

    if not isinstance(parsed, list):
        parsed = []

    # Save batch snapshot of current characters before deleting
    existing_chars_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    existing_chars = list(existing_chars_result.scalars().all())
    batch_snapshot = []
    if existing_chars:
        current_version = max((c._version or 0 for c in existing_chars), default=0)
        for c in existing_chars:
            batch_snapshot.append({
                "name": c.name,
                "role_type": c.role_type,
                "personality": c.personality,
                "background": c.background,
                "appearance": c.appearance,
                "relationships": c.relationships,
                "arc": c.arc,
            })

    await db.execute(delete(Character).where(Character.project_id == project_id))

    # Version management: get upstream versions for new characters
    upstream_versions = await version_service.get_upstream_versions(db, project_id)
    char_version = int(upstream_versions.get("characters", 0) or 0) + 1
    based_on = {
        "story_core": upstream_versions.get("story_core", 0),
        "worldview": upstream_versions.get("worldview", 0),
    }

    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "未命名角色"
        role_type = item.get("role_type") or "supporting"
        personality = item.get("personality")
        background = item.get("background")
        appearance = item.get("appearance")
        relationships = item.get("relationships")
        arc = item.get("arc")
        db.add(Character(
            project_id=project_id,
            name=name,
            role_type=role_type,
            personality=personality,
            background=background,
            appearance=appearance,
            relationships=relationships,
            arc=arc,
            _version=char_version,
            _based_on=based_on,
            _stale="false",
            _history=[{
                "version": current_version if existing_chars else 0,
                "created_at": datetime.now(timezone.utc).isoformat() if 'datetime' in dir() else "",
                "based_on": {},
                "data": batch_snapshot,
            }] if batch_snapshot else [],
        ))
    await db.commit()

    # Mark downstream stale
    await version_service.mark_downstream_stale(db, project_id, "characters")
    await db.commit()

    # Auto-extract knowledge from characters
    try:
        kn_items = await ai_service.extract_knowledge(db, content, "角色设定")
        await _save_knowledge(db, project_id, kn_items, "character")
    except Exception:
        pass

    return {"content": content, "version": char_version}


@router.post("/chapters/generate")
async def generate_chapter(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream generate a new chapter with semantic context retrieval."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Get worldview
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()

    # Get characters
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = list(result.scalars().all())

    # Get existing chapters
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.desc())
    )
    chapters = list(result.scalars().all())
    next_number = (chapters[0].chapter_number + 1) if chapters else 1

    story_core_text = json.dumps(project.story_core, ensure_ascii=False) if project.story_core else ""
    worldview_text = worldview.description if worldview else ""

    # Build AI client for vector search
    client = await ai_service._build_client(db)

    # 向量检索：获取与当前章节相关的历史内容（语义搜索）
    vector_context = ""
    try:
        vector_context = await vector_service.get_context_for_chapter(
            project_id, f"第{next_number}章", max_chunks=5,
            use_rerank=bool(settings.SILICONFLOW_API_KEY),
            ai_client=client,
        )
    except Exception:
        vector_context = ""  # Fallback: 向量检索失败不影响章节生成

    await client.close()

    # Look up outline detail for the target chapter (from AI-generated outline)
    outline_detail = None
    for ch in chapters:
        if ch.chapter_number == next_number and ch.outline_detail:
            outline_detail = ch.outline_detail
            break

    # ── Phase 7a：写前骨架检查 ────────────────────────────────────────
    target_chapter = None
    for ch in chapters:
        if ch.chapter_number == next_number:
            target_chapter = ch
            break
    if target_chapter is not None:
        ok, msg = _has_valid_skeleton(target_chapter)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)

    async def event_generator():
        full_content = ""
        # 读取上一章检测到的风格指导
        style_guidance = (project.context or {}).get("style_guidance")
        async for chunk in ai_service.generate_chapter_stream(
            db, project, next_number, story_core_text,
            worldview_text, characters, chapters, vector_context,
            outline_detail=outline_detail,
            style_guidance=style_guidance,
        ):
            full_content += chunk
            yield {"data": json.dumps({"type": "chunk", "text": chunk})}

        # Generate title and summary from the content
        title = f"第{next_number}章"
        summary = ""
        try:
            meta = await ai_service.generate_chapter_meta(db, full_content, next_number)
            if meta.get("title"):
                title = meta["title"]
            if meta.get("summary"):
                summary = meta["summary"]
        except Exception:
            pass  # Fallback to default title

        # Save chapter to database
        upstream_versions = await version_service.get_upstream_versions(db, project_id)
        based_on = {
            "story_core": upstream_versions.get("story_core", 0),
            "worldview": upstream_versions.get("worldview", 0),
            "characters": upstream_versions.get("characters", 0),
        }
        chapter = Chapter(
            project_id=project_id,
            chapter_number=next_number,
            title=title,
            content={"text": full_content},
            summary=summary,
            word_count=len(full_content),
            status="generated",
            _version=1,
            _based_on=based_on,
            _stale="false",
        )
        db.add(chapter)
        await db.commit()

        # ── Phase 14.3：风格检测 → 存入 project 上下文 ──────────────
        try:
            from app.services.ai_flavor_detector import detect_ai_flavor
            flavor_result = detect_ai_flavor(full_content)
            if flavor_result.get("score", 0) > 30:
                style_guidance = flavor_result.get("style_guidance", [])
                if not style_guidance:
                    style_guidance = [
                        i.get("suggestion", "") for i in flavor_result.get("issues", [])
                        if i.get("severity") in ("severe", "medium")
                    ][:5]
                # 存到 project 的 context 字段供下一章使用
                existing = project.context or {}
                existing["style_guidance"] = style_guidance
                existing["last_ai_flavor_score"] = flavor_result["score"]
                project.context = existing
                await db.commit()
        except Exception:
            pass  # 不影响主流程

        # ── Phase 17.5：投影写入（章节生成后写入记忆）─────────────
        try:
            from app.services.projection_writer import ProjectionWriter
            proj = ProjectionWriter(db, project_id)
            await proj.write_summary(next_number, title, summary)
            # 写入角色当前状态快照
            for c in characters:
                if c.background:
                    await proj.write_state_snapshot(
                        next_number, c.name, "background", c.background,
                    )
        except Exception:
            pass  # 不影响主流程

        # ── Phase 13.1：自动触发流水线 ──────────────────────────────
        try:
            from app.api.v1.auto_pipeline import _run_auto_pipeline
            yield {"data": json.dumps({
                "type": "info",
                "message": "章节生成完成，开始自动流水线审查...",
            })}
            async for event in _run_auto_pipeline(
                db, UUID(project_id), chapter.id,
                skip_final_commit=True,
            ):
                yield {"data": json.dumps(event)}
        except Exception as e:
            # 流水线失败不影响章节保存
            yield {"data": json.dumps({
                "type": "pipeline_error",
                "data": {"error": str(e)},
            })}

        yield {"data": json.dumps({
            "type": "done",
            "chapter_id": str(chapter.id),
            "chapter_number": next_number,
            "title": title,
            "word_count": len(full_content),
        })}

    return EventSourceResponse(event_generator())


@router.post("/outline/generate")
async def generate_outline(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """AI generate a full outline (volumes + chapter outlines)."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Get worldview
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()

    # Get characters
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = list(result.scalars().all())

    story_core_text = json.dumps(project.story_core, ensure_ascii=False) if project.story_core else ""
    worldview_text = worldview.description if worldview else "暂无世界观设定"

    content = await ai_service.generate_outline(
        db, project, story_core_text, worldview_text, characters
    )

    # Parse and save
    try:
        parsed = _extract_json(content)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            422,
            f"AI 返回的大纲 JSON 解析失败（可能是内容截断），请重试。错误：{e}"
        )

    volumes_data = parsed.get("volumes", [])
    if not volumes_data:
        raise HTTPException(
            422,
            "AI 返回的大纲没有包含卷信息，请重试。原始内容：" + content[:500]
        )

    # Clear existing volumes and chapters
    existing_volumes = await db.execute(
        select(Volume).where(Volume.project_id == project_id)
    )
    for v in existing_volumes.scalars().all():
        await db.delete(v)

    existing_chapters = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id)
    )
    for c in existing_chapters.scalars().all():
        await db.delete(c)

    # Version management: get upstream versions
    upstream_versions = await version_service.get_upstream_versions(db, project_id)
    based_on = {
        "story_core": upstream_versions.get("story_core", 0),
        "worldview": upstream_versions.get("worldview", 0),
        "characters": upstream_versions.get("characters", 0),
    }
    outline_version = 1

    chapters_created = 0
    for vol_idx, vol_data in enumerate(volumes_data, 1):
        title = vol_data.get("title") or f"第{vol_idx}卷"
        description = vol_data.get("description") or ""
        highlight_rhythm = vol_data.get("highlight_rhythm")
        emotion_arc = vol_data.get("emotion_arc")
        foreshadowing_notes = vol_data.get("foreshadowing_notes")
        twists = vol_data.get("twists")

        volume = Volume(
            project_id=project_id,
            volume_number=vol_idx,
            title=title,
            description=description,
            chapter_start=chapters_created + 1,
            highlight_rhythm=highlight_rhythm,
            emotion_arc=emotion_arc,
            foreshadowing_notes=foreshadowing_notes,
            twists=twists,
            _version=outline_version,
            _based_on=based_on,
            _stale="false",
        )
        db.add(volume)
        await db.flush()

        chapter_data = vol_data.get("chapters", [])
        for ch_idx, ch_data in enumerate(chapter_data, 1):
            ch_title = ch_data.get("title") or f"第{ch_idx}章"
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapters_created + 1,
                title=ch_title,
                content={"text": ""},
                summary="",
                outline_detail={
                    "opening": ch_data.get("opening", ""),
                    "events": ch_data.get("events", ""),
                    "purpose": ch_data.get("purpose", ""),
                    "conflict": ch_data.get("conflict", ""),
                    "character_arc": ch_data.get("character_arc", ""),
                    "pacing": ch_data.get("pacing", ""),
                    "hooks": ch_data.get("hooks", ""),
                    "highlights": ch_data.get("highlights", ""),
                    "suspense": ch_data.get("suspense", ""),
                },
                status="outlined",
                _version=outline_version,
                _based_on=based_on,
                _stale="false",
            )
            db.add(chapter)
            chapters_created += 1

        # Update volume end
        volume.chapter_end = chapters_created

    await db.commit()

    return {
        "content": content,
        "volumes_created": len(volumes_data),
        "chapters_created": chapters_created,
    }


@router.post("/consistency/check")
async def check_consistency(
    project_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Check consistency of the latest chapter against existing content."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Get latest chapter
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.desc())
        .limit(1)
    )
    latest_chapter = result.scalar_one_or_none()
    if not latest_chapter:
        raise HTTPException(400, "No chapters to check")

    # Get all chapters
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.asc())
    )
    all_chapters = list(result.scalars().all())

    # Get worldview and characters for context
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()

    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = list(result.scalars().all())

    # Build existing content summary
    existing_content = []
    if project.story_core:
        existing_content.append({"type": "story_core", "data": project.story_core})
    if worldview:
        existing_content.append({"type": "worldview", "data": worldview.description})
    for c in characters:
        existing_content.append({"type": "character", "data": c.name, "details": c.background})
    for ch in all_chapters[:-1]:  # Exclude the latest
        existing_content.append({"type": "chapter", "number": ch.chapter_number, "summary": ch.summary})

    chapter_text = latest_chapter.content.get("text", "") if isinstance(latest_chapter.content, dict) else str(latest_chapter.content)

    result = await ai_service.check_consistency(db, chapter_text, existing_content)
    return {"content": result}


@router.post("/chapters/{chapter_id}/regenerate")
async def regenerate_chapter(
    project_id: str,
    chapter_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream regenerate an existing chapter in place, replacing its content."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Load target chapter
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    # Get worldview
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()

    # Get characters
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = list(result.scalars().all())

    # Get other chapters (exclude the one being regenerated)
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id, Chapter.id != chapter_id)
        .order_by(Chapter.chapter_number.desc())
    )
    other_chapters = list(result.scalars().all())

    story_core_text = json.dumps(project.story_core, ensure_ascii=False) if project.story_core else ""
    worldview_text = worldview.description if worldview else ""
    target_number = chapter.chapter_number

    async def event_generator():
        full_content = ""
        async for chunk in ai_service.generate_chapter_stream(
            db, project, target_number, story_core_text,
            worldview_text, characters, other_chapters,
            outline_detail=chapter.outline_detail,
        ):
            full_content += chunk
            yield {"data": json.dumps({"type": "chunk", "text": chunk})}

        # Update chapter content in place
        # Save old version to history first
        await version_service.save_and_bump(db, chapter, based_on={
            "story_core": int((project.story_core or {}).get("_version", 0) or 0),
            "worldview": worldview._version or 0 if worldview else 0,
            "characters": max((c._version or 0 for c in other_chapters), default=0),
        })
        chapter.content = {"text": full_content}
        chapter.word_count = len(full_content)
        chapter._stale = "false"
        await db.commit()

        # Auto-extract knowledge from regenerated chapter
        try:
            kn_items = await ai_service.extract_knowledge(db, full_content, "章节内容")
            await _save_knowledge(db, project_id, kn_items, "chapter", str(chapter_id))
        except Exception:
            pass

        yield {"data": json.dumps({
            "type": "done",
            "chapter_id": str(chapter_id),
            "chapter_number": target_number,
            "word_count": len(full_content),
        })}

    return EventSourceResponse(event_generator())


# ── AI味检测 & 去AI味 ──


@router.post("/chapters/{chapter_id}/detect-ai")
async def detect_ai_flavor(
    project_id: str,
    chapter_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """检测章节的AI味程度，返回评分和问题列表。"""
    from app.services.ai_flavor_detector import detect_ai_flavor as detect

    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    chapter_text = chapter.content.get("text", "") if isinstance(chapter.content, dict) else str(chapter.content)
    return detect(chapter_text)


@router.post("/chapters/{chapter_id}/de-ai")
async def de_ai_chapter(
    project_id: str,
    chapter_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """流式去AI味改写：读取章节内容 → AI改写 → 替换原文。"""
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    original_text = chapter.content.get("text", "") if isinstance(chapter.content, dict) else str(chapter.content)
    if not original_text.strip():
        raise HTTPException(400, "章节内容为空")

    async def event_generator():
        full_content = ""
        async for chunk in ai_service.de_ai_rewrite_stream(db, original_text):
            full_content += chunk
            yield {"data": json.dumps({"type": "chunk", "text": chunk})}

        # 替换章节内容（保存旧版本到历史）
        await version_service.save_and_bump(db, chapter, based_on={})
        chapter.content = {"text": full_content}
        chapter.word_count = len(full_content)
        await db.commit()

        yield {"data": json.dumps({
            "type": "done",
            "chapter_id": str(chapter_id),
            "chapter_number": chapter.chapter_number,
            "word_count": len(full_content),
        })}

    return EventSourceResponse(event_generator())


# ── Version Restore Endpoints ──


@router.post("/story-core/restore/{version}")
async def restore_story_core(
    project_id: str,
    version: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Restore story_core to a specific version."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    success = version_service.restore_story_core_version(project, version)
    if not success:
        raise HTTPException(404, f"Version {version} not found in history")

    # Mark downstream stale after restoring
    await version_service.mark_downstream_stale(db, project_id, "story_core")
    await db.commit()

    return {"success": True, "version": version, "story_core": project.story_core}


@router.post("/worldview/restore/{version}")
async def restore_worldview(
    project_id: str,
    version: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Restore worldview to a specific version."""
    result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldview = result.scalar_one_or_none()
    if not worldview:
        raise HTTPException(404, "Worldview not found")

    success = await version_service.restore_node_version(db, worldview, version)
    if not success:
        raise HTTPException(404, f"Version {version} not found in history")

    await version_service.mark_downstream_stale(db, project_id, "worldview")
    await db.commit()

    return {"success": True, "version": worldview._version}


@router.post("/characters/restore/{version}")
async def restore_characters(
    project_id: str,
    version: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Restore all characters to a specific version batch."""
    result = await db.execute(
        select(Character)
        .where(Character.project_id == project_id)
        .limit(1)
    )
    char = result.scalar_one_or_none()
    if not char:
        raise HTTPException(404, "No characters found")

    # For characters, restore from the first character's history (batch snapshot)
    history = char._history or []
    target = None
    for h in history:
        if h.get("version") == version:
            target = h
            break
    if not target:
        raise HTTPException(404, f"Version {version} not found in history")

    # Delete current characters and recreate from snapshot
    await db.execute(delete(Character).where(Character.project_id == project_id))

    for char_data in target.get("data", []):
        db.add(Character(
            project_id=project_id,
            **{k: v for k, v in char_data.items() if k not in ("id", "project_id")},
            _version=version,
            _based_on=target.get("based_on", {}),
            _stale="false",
        ))

    await version_service.mark_downstream_stale(db, project_id, "characters")
    await db.commit()

    return {"success": True, "version": version}


# ── Context Agent：五段式写作任务书 ──────────────────────────────────


@router.get("/chapters/{chapter_number}/task-book")
async def get_writing_task_book(
    project_id: str,
    chapter_number: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """生成并返回指定章节的五段式写作任务书。"""
    from app.services.context_agent_service import ContextAgentService

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # 获取章节信息
    result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    chapter = result.scalar_one_or_none()

    agent = ContextAgentService(db, project_id, chapter_number)
    task_book = await agent.build_writing_task_book()

    return {
        "project_id": project_id,
        "chapter_number": chapter_number,
        "chapter_title": chapter.title if chapter else "",
        "chapter_status": chapter.status if chapter else "unknown",
        "task_book": task_book,
    }
