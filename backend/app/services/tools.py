"""
Agent tool definitions for multi-step AI tool-use loops.

Two responsibilities:
1. get_tool_definitions() -> list of OpenAI-format tool schemas the model sees.
2. TOOL_REGISTRY -> maps tool name to its async executor function,
   so agent_chat can dispatch tool_calls back to real service code.
"""
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.character import Character
from app.models.foreshadowing import Foreshadowing
from app.models.worldview import Worldview
from app.models.volume import Volume


# ---------------------------------------------------------------------------
# OpenAI-compatible tool schemas
# ---------------------------------------------------------------------------
def get_tool_definitions() -> list[dict[str, Any]]:
    """Return the list of tool definitions to pass to the LLM."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_outline_node",
                "description": (
                    "查询指定项目某一章节的大纲节点。返回该章所在卷（volume）的概览、"
                    "章节序号与标题、以及章节大纲明细（outline_detail）。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "项目唯一标识（UUID 字符串）",
                        },
                        "chapter_number": {
                            "type": "integer",
                            "description": "目标章节号，从 1 开始",
                        },
                    },
                    "required": ["project_id", "chapter_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_character_info",
                "description": (
                    "查询指定项目中某角色的详细信息。返回角色定位、性格、背景、"
                    "外貌、人物关系与角色弧线。角色名为精确匹配。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "项目唯一标识（UUID 字符串）",
                        },
                        "character_name": {
                            "type": "string",
                            "description": "角色名称（精确匹配）",
                        },
                    },
                    "required": ["project_id", "character_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_chapter_summary",
                "description": (
                    "查询指定项目某一章的摘要（summary）。"
                    "返回该章的章节号、标题与一句话/段落式摘要。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "项目唯一标识（UUID 字符串）",
                        },
                        "chapter_number": {
                            "type": "integer",
                            "description": "目标章节号，从 1 开始",
                        },
                    },
                    "required": ["project_id", "chapter_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_worldview_info",
                "description": (
                    "按关键词搜索指定项目中的世界观设定条目。"
                    "在名称与描述中做子串匹配，返回所有命中的世界观条目（含名称、"
                    "描述、规则与时间线）。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "项目唯一标识（UUID 字符串）",
                        },
                        "query": {
                            "type": "string",
                            "description": "搜索关键词（子串匹配）",
                        },
                    },
                    "required": ["project_id", "query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_foreshadowing_status",
                "description": (
                    "返回指定项目中所有尚未回收的伏笔列表。"
                    "筛选 status 为 planted / active 的伏笔，"
                    "返回标题、描述、目标章、到期章与状态。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "项目唯一标识（UUID 字符串）",
                        },
                    },
                    "required": ["project_id"],
                },
            },
        },
    ]


# ---------------------------------------------------------------------------
# Registry: tool name -> async(project_id, db, **kwargs) -> str
# ---------------------------------------------------------------------------
async def _tool_get_outline_node(project_id: str, db: AsyncSession, **kwargs: Any) -> str:
    chapter_number: int = int(kwargs["chapter_number"])
    chapter = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    chapter = chapter.scalar_one_or_none()

    # find the volume this chapter belongs to
    volumes = (await db.execute(
        select(Volume).where(Volume.project_id == project_id)
    )).scalars().all()
    volume = None
    for v in volumes:
        if (v.chapter_start is not None and chapter_number >= v.chapter_start  # type: ignore[redundant-expr]
                and (v.chapter_end is None or chapter_number <= v.chapter_end)):  # type: ignore[redundant-expr]
            volume = v
            break

    if not chapter and not volume:
        return json.dumps({
            "error": "not_found",
            "message": f"未找到第 {chapter_number} 章及其所属卷。",
        }, ensure_ascii=False)

    result: dict[str, Any] = {}
    if volume is not None:
        result["volume"] = {
            "volume_number": volume.volume_number,
            "title": volume.title,
            "description": volume.description,
            "chapter_start": volume.chapter_start,
            "chapter_end": volume.chapter_end,
        }
    if chapter is not None:
        result["chapter"] = {
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "outline_detail": chapter.outline_detail or {},
        }
    return json.dumps(result, ensure_ascii=False)


async def _tool_get_character_info(project_id: str, db: AsyncSession, **kwargs: Any) -> str:
    character_name: str = str(kwargs["character_name"])
    character = await db.execute(
        select(Character).where(
            Character.project_id == project_id,
            Character.name == character_name,
        )
    )
    character = character.scalar_one_or_none()
    if not character:
        # also try matching any alias
        result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        for c in result.scalars():
            aliases = c.aliases or []
            if character_name in aliases:
                character = c
                break
        if not character:
            return json.dumps({
                "error": "not_found",
                "message": f"未找到角色「{character_name}」。",
            }, ensure_ascii=False)

    return json.dumps({
        "name": character.name,
        "role_type": character.role_type,
        "personality": character.personality,
        "background": character.background,
        "appearance": character.appearance,
        "relationships": character.relationships or {},
        "arc": character.arc,
        "first_appearance_chapter": character.first_appearance_chapter,
        "last_appearance_chapter": character.last_appearance_chapter,
        "aliases": character.aliases,
        "appearance_chapters": character.appearance_chapters,
    }, ensure_ascii=False)


async def _tool_get_chapter_summary(project_id: str, db: AsyncSession, **kwargs: Any) -> str:
    chapter_number: int = int(kwargs["chapter_number"])
    chapter = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    chapter = chapter.scalar_one_or_none()
    if not chapter:
        return json.dumps({
            "error": "not_found",
            "message": f"未找到第 {chapter_number} 章。",
        }, ensure_ascii=False)

    return json.dumps({
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "summary": chapter.summary,
    }, ensure_ascii=False)


async def _tool_get_worldview_info(project_id: str, db: AsyncSession, **kwargs: Any) -> str:
    query: str = str(kwargs["query"]).strip()
    if not query:
        return json.dumps({
            "error": "invalid_query",
            "message": "搜索关键词不能为空。",
        }, ensure_ascii=False)

    # substring match against name and description
    qlower = query.lower()
    worldviews = (await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )).scalars().all()

    matched = []
    for w in worldviews:
        haystack = (w.name or "") + " " + (w.description or "")
        if qlower in haystack.lower():
            matched.append({
                "id": str(w.id),
                "name": w.name,
                "description": w.description,
                "rules": w.rules,
                "timeline": w.timeline,
            })

    return json.dumps({
        "query": query,
        "count": len(matched),
        "results": matched,
    }, ensure_ascii=False)


async def _tool_get_foreshadowing_status(project_id: str, db: AsyncSession, **kwargs: Any) -> str:
    open_statuses = ["planted", "active"]
    foreshadowings = (await db.execute(
        select(Foreshadowing)
        .where(
            Foreshadowing.project_id == project_id,
            Foreshadowing.status.in_(open_statuses),
        )
        .order_by(Foreshadowing.created_at.desc())
    )).scalars().all()

    results = []
    for f in foreshadowings:
        results.append({
            "id": str(f.id),
            "title": f.title,
            "description": f.description,
            "status": f.status,
            "target_chapter": f.target_chapter,
            "expected_redemption_chapter": f.expected_redemption_chapter,
            "depends_on": f.depends_on,
            "dependency_type": f.dependency_type,
        })

    return json.dumps({
        "project_id": project_id,
        "open_count": len(results),
        "foreshadowings": results,
    }, ensure_ascii=False)


TOOL_REGISTRY: dict[str, Any] = {
    "get_outline_node": _tool_get_outline_node,
    "get_character_info": _tool_get_character_info,
    "get_chapter_summary": _tool_get_chapter_summary,
    "get_worldview_info": _tool_get_worldview_info,
    "get_foreshadowing_status": _tool_get_foreshadowing_status,
}


def get_tool_executor(name: str) -> Any | None:
    """Look up an executor by tool name; returns None if unknown."""
    return TOOL_REGISTRY.get(name)
