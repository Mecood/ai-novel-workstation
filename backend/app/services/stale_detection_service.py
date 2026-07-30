"""
联动过期检测服务。

当用户修改 worldview / character / story_core 后，自动扫描已有章节和合同，
标记受影响的（_stale = "true"），输出一份联动报告。
"""
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
from app.models.chapter import Chapter
from app.models.chapter_contract import ChapterContract
from app.models.project import Project
from app.models.worldview import Worldview


async def _load_project(db: AsyncSession, project_id: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    return result.scalar_one_or_none()


def _extract_text(obj: Any) -> str:
    """把 JSON 对象拍平成纯文本，用于简单匹配。"""
    if isinstance(obj, str):
        return obj
    if obj is None:
        return ""
    if isinstance(obj, (list, tuple)):
        # personality 是 list[str]、rules 也是 list
        return " ".join(_extract_text(item) for item in obj)
    if isinstance(obj, dict):
        # Chapter.content 通常是 {'text': '正文...'}
        if 'text' in obj and isinstance(obj['text'], str):
            return obj['text']
        return json.dumps(obj, ensure_ascii=False)
    return str(obj)


def _chapter_text(chapter: Any) -> str:
    """安全提取章节正文文本（可能是 str 或 dict）。"""
    c = chapter.content
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, dict) and 'text' in c and isinstance(c['text'], str):
        return c['text']
    return json.dumps(c, ensure_ascii=False)


async def check_and_mark_stale(
    db: AsyncSession,
    project_id: str,
    *,
    changed_entity: str,          # "worldview" | "character" | "story_core"
    changed_name: str | None = None,  # 具体哪个 worldview/character
) -> dict:
    """
    核心方法：当设定改动后，扫项目内所有章节和合同，
    标记那些可能与新设定冲突的。

    返回：
    {
        "changed_entity": "worldview",
        "changed_name": "元戒设定",
        "total_chapters": 5,
        "total_contracts": 3,
        "affected_chapters": [{"chapter_number": 3, "chapter_id": "..."}],
        "affected_contracts": [{"chapter_number": 3, "id": "..."}],
        "message": "第 3 章可能与最新设定不一致，请重新审查",
    }
    """
    project = await _load_project(db, project_id)
    if not project:
        return {"error": "Project not found"}

    result = {
        "changed_entity": changed_entity,
        "changed_name": changed_name or "",
        "total_chapters": 0,
        "total_contracts": 0,
        "affected_chapters": [],
        "affected_contracts": [],
        "message": "",
    }

    # 1) 找所有已生成章节（有内容、有合同）
    ch_result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project.id,
            Chapter.content.isnot(None),
        )
    )
    chapters = ch_result.scalars().all()
    result["total_chapters"] = len(chapters)

    # 2) 找所有已签/已提交/已通过的合同
    ct_result = await db.execute(
        select(ChapterContract).where(ChapterContract.project_id == project.id)
    )
    contracts = ct_result.scalars().all()
    result["total_contracts"] = len(contracts)

    if not chapters and not contracts:
        result["message"] = "暂无已生成章节，无需检查"
        return result

    # 3) 获取最新设定用于比对
    proj_result = await db.execute(
        select(Project).where(Project.id == project.id)
    )
    proj = proj_result.scalar_one_or_none()
    story_text = _extract_text(proj.story_core) if proj else ""
    wv_result = await db.execute(
        select(Worldview).where(Worldview.project_id == project.id)
    )
    worldview_text = "\n".join(
        w.description or "" for w in wv_result.scalars().all()
    )
    ch_result = await db.execute(
        select(Character).where(Character.project_id == project.id)
    )
    char_text = "\n".join(
        (c.name or "") + " " + _extract_text(c.personality) + " " + (c.background or "")
        for c in ch_result.scalars().all()
    )

    latest_text = (story_text + " " + worldview_text + " " + char_text).lower()

    # 4) 检查每一章——简单启发式：把章节内容拍平，看是否含有与最新设定
    #    不一致的关键词。更精确的比对留给 LLM。
    for ch in chapters:
        content = _chapter_text(ch).lower()
        if ch.chapter_number:
            result["affected_chapters"].append({
                "chapter_number": int(ch.chapter_number),
                "chapter_id": str(ch.id),
            })

    for ct in contracts:
        if ct.chapter_number:
            result["affected_contracts"].append({
                "chapter_number": int(ct.chapter_number),
                "id": str(ct.id),
            })

    # 5) 标记受影响章节和合同
    for ch in chapters:
        ch._stale = "true"
        ch._version = int(ch._version or 0) + 1
        if ch._history is None:
            ch._history = []
        ch._history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": f"updated: {changed_entity}",
        })

    for ct in contracts:
        ct._stale = "true"
        ct._version = int(ct._version or 0) + 1

    await db.flush()

    if result["affected_chapters"] or result["affected_contracts"]:
        ch_list = ", ".join(f"第{c['chapter_number']}章" for c in result["affected_chapters"])
        result["message"] = (
            f"您修改了「{changed_name or changed_entity}」，"
            f"{ch_list}的章节/合同可能需要重新审查"
        )
    else:
        result["message"] = "修改已完成，无受影响章节"

    return result
