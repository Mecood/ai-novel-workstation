"""
多任务分析服务 — 编排 4 种批量 AI 分析任务。
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.review_report import ReviewReport
from app.models.character import Character
from app.models.worldview import Worldview
from app.models.foreshadowing import Foreshadowing
from app.services.ai_service import AIService


TASK_PROMPTS: dict[str, dict[str, str]] = {
    "structure_analysis": {
        "system": (
            "你是一位小说结构分析师。请对给定章节的节奏和叙事弧进行评估。"
            "从以下维度输出分析结果（每项1-10分）：\n"
            "1. pacing（节奏）：章节推进是否合适，有无拖沓或过快\n"
            "2. tension_arc（张力弧线）：冲突的建立-加剧-释放是否清晰\n"
            "3. chapter_role（章节职责）：该章在全书结构中承担的功能是否明确\n"
            "4. hook_strength（钩子强度）：结尾是否有吸引读者继续阅读的钩子\n"
            "另外输出 issues（具体问题列表，每条含 description+severity）和 summary。"
        ),
        "user": (
            "【书籍概要】{project_info}\n\n"
            "【章节正文（第{chapter_number}章）】\n{chapter_text}\n\n"
            "请对该章节进行结构分析，返回严格 JSON 格式：\n"
            '{{"dimension_scores":{{"pacing":0,"tension_arc":0,"chapter_role":0,"hook_strength":0}},'
            '"overall_score":0,"issues":[{{"description":"","severity":"info"}}],'
            '"summary":""}}'
        ),
    },
    "character_extract": {
        "system": (
            "你是一位小说角色分析师。请从给定章节正文中识别角色描写的变化。"
            "检查：\n"
            "1. 角色出场（首次出现 vs 再出现）\n"
            "2. 角色状态变化（外貌/能力/情绪/关系的变化）\n"
            "3. 角色行为是否符合已有设定\n"
            "如果某个角色的表现与已有角色档案冲突，记录为 issue（severity=high）。"
        ),
        "user": (
            "【已有角色档案】\n{characters_info}\n\n"
            "【章节正文（第{chapter_number}章）】\n{chapter_text}\n\n"
            "请提取本章节中涉及的角色信息变化，返回严格 JSON 格式：\n"
            '{{"characters":['
            '{{"name":"","role":"","status_change":"","appearance":"new"|"recurring",'
            '"behavior_consistent":true,"issues":[{{"description":"","severity":"info"}}]}}],'
            '"summary":""}}'
        ),
    },
    "timeline_extract": {
        "system": (
            "你是一位小说时间线分析师。请从给定章节正文中提取时间事件。"
            "识别：事件类型（战斗/对话/转折/环境变化等）、发生时间关系（之前/同时/之后）、"
            "与现有时间线的一致性。"
        ),
        "user": (
            "【书籍时间线（已有事件）】\n{timeline_info}\n\n"
            "【章节正文（第{chapter_number}章）】\n{chapter_text}\n\n"
            "请提取本章节中的时间事件，返回严格 JSON 格式：\n"
            '{{"events":[{{"name":"","type":"","chapter":0,"chapter_line":"L1-L2",'
            '"before_event":"","after_event":"","description":""}}],'
            '"timeline_consistent":true,"issues":[{{"description":"","severity":"info"}}],'
            '"summary":""}}'
        ),
    },
}


def _safe_char_desc(c: Character) -> str:
    """安全获取角色描述。"""
    personality = c.personality
    if isinstance(personality, dict):
        return personality.get('description', '')[:100]
    if isinstance(personality, list):
        return str(personality)[:100]
    return str(personality or '')[:100]

def _gather_project_context(project: Project, characters: list[Character],
                            worldviews: list[Worldview]) -> str:
    parts = [f"书名：{project.name}（{project.genre}）"]
    ctx = project.context or {}
    if ctx.get("story_core"):
        sc = ctx.get("story_core", {}) if isinstance(ctx.get("story_core"), dict) else {}
        for k in ("theme", "summary", "core_conflict", "highlights", "tone"):
            v = sc.get(k)
            if v:
                parts.append(f"[{k}] {v}" if isinstance(v, str) else f"[{k}] {json.dumps(v, ensure_ascii=False)}")
    if characters:
        char_info = "\n".join(
            f"- {c.name}（{c.role_type}）：{_safe_char_desc(c)}"
            for c in characters
        )
        parts.append(f"角色档案（{len(characters)}人）：\n{char_info}")
    if worldviews:
        wv_info = "\n".join(f"- {w.name}：{(w.description or '')[:120]}" for w in worldviews)
        parts.append(f"世界观：\n{wv_info}")
    return "\n\n".join(parts)


def _gather_characters_info(characters: list[Character]) -> str:
    if not characters:
        return "（暂无角色档案）"
    lines = []
    for c in characters:
        lines.append(f"- {c.name}（{c.role_type}）：")
        if c.background:
            lines.append(f"  背景：{c.background[:150]}")
        if c.personality:
            lines.append(f"  性格：{json.dumps(c.personality, ensure_ascii=False)[:150]}")
        if c.relationships:
            lines.append(f"  关系：{json.dumps(c.relationships, ensure_ascii=False)[:120]}")
    return "\n".join(lines)


def _gather_timeline_info(project_id: str) -> str:
    return "（时间线数据由本分析任务自行提取）"


class AnalysisService:
    """多任务分析编排器。"""

    def __init__(self, ai_service: AIService | None = None):
        self.ai_service = ai_service or AIService()

    async def run_batch_analysis(
        self,
        db: AsyncSession,
        project_id: str,
        task_types: list[str],
        chapter_range: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """执行批量分析任务，返回报告列表。"""
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        # 收集上下文
        char_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters: list[Character] = list(char_result.scalars())
        wv_result = await db.execute(
            select(Worldview).where(Worldview.project_id == project_id)
        )
        worldviews: list[Worldview] = list(wv_result.scalars())

        project_context = _gather_project_context(project, characters, worldviews)
        characters_info = _gather_characters_info(characters)
        timeline_info = _gather_timeline_info(project_id)

        # 确定章节范围
        chapter_result = await db.execute(
            select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number.asc())
        )
        chapters: list[Chapter] = list(chapter_result.scalars())
        if chapter_range and len(chapter_range) == 2:
            start_ch, end_ch = int(chapter_range[0]), int(chapter_range[1])
            chapters = [c for c in chapters if start_ch <= c.chapter_number <= end_ch]
        # 只分析有内容的章节
        chapters = [c for c in chapters if c.content]

        reports: list[dict[str, Any]] = []
        for task_type in task_types:
            if task_type not in TASK_PROMPTS:
                continue
            prompts = TASK_PROMPTS[task_type]
            for chapter in chapters:
                content = chapter.content
                chapter_text = ""
                if isinstance(content, dict):
                    chapter_text = content.get("text", "") or ""
                elif isinstance(content, str):
                    chapter_text = content
                else:
                    chapter_text = str(content) if content else ""

                if not chapter_text.strip():
                    continue

                user_content = prompts["user"].format(
                    chapter_number=chapter.chapter_number,
                    chapter_text=chapter_text[:8000],
                    project_info=project_context,
                    characters_info=characters_info,
                    timeline_info=timeline_info,
                )

                report_entry: dict[str, Any] = {
                    "task_type": task_type,
                    "chapter_number": chapter.chapter_number,
                    "chapter_id": str(chapter.id),
                    "status": "running",
                    "chapter_title": chapter.title,
                }
                try:
                    client = await self.ai_service._build_client(db)
                    ai_raw = await client.chat(
                        messages=[
                            {"role": "system", "content": prompts["system"]},
                            {"role": "user", "content": user_content},
                        ],
                        max_tokens=4096,
                    )
                    # 尝试解析 JSON
                    parsed = self._parse_json_from_ai(ai_raw)
                    report_entry.update({
                        "status": "complete",
                        "result": parsed,
                        "overall_score": parsed.get("overall_score") if isinstance(parsed, dict) else None,
                        "issues": parsed.get("issues", []) if isinstance(parsed, dict) else [],
                        "summary": parsed.get("summary", "") if isinstance(parsed, dict) else str(ai_raw)[:300],
                    })
                    # 持久化到 review_reports
                    async with async_session() as persist_db:
                        await self._persist_report(
                            persist_db, project_id, chapter, task_type, parsed
                        )
                except Exception as e:
                    report_entry.update({
                        "status": "error",
                        "error": str(e),
                    })
                reports.append(report_entry)

        return reports

    @staticmethod
    async def _persist_report(
        db: AsyncSession,
        project_id: str,
        chapter: Chapter,
        task_type: str,
        result: dict[str, Any],
    ) -> None:
        existing = await db.execute(
            select(ReviewReport).where(
                ReviewReport.project_id == project_id,
                ReviewReport.chapter_number == chapter.chapter_number,
                ReviewReport.task_type == task_type,
            )
        )
        existing_report = existing.scalar_one_or_none()
        if existing_report:
            existing_report.overall_score = float(result.get("overall_score", 0))
            existing_report.issues = result.get("issues", [])
            existing_report.dimension_scores = result.get("dimension_scores", {})
            existing_report.summary = result.get("summary", "")
            existing_report.tiered_results = {"analysis_result": result}
        else:
            existing_report = ReviewReport(
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_number=chapter.chapter_number,
                task_type=task_type,
                overall_score=float(result.get("overall_score", 0)),
                issues=result.get("issues", []),
                dimension_scores=result.get("dimension_scores", {}),
                summary=result.get("summary", ""),
                tiered_results={"analysis_result": result},
            )
            db.add(existing_report)
        await db.commit()

    @staticmethod
    def _parse_json_from_ai(text: str) -> dict[str, Any]:
        """从 AI 输出中提取 JSON。"""
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        # 尝试找内嵌的 JSON 代码块
        start = text.find("{")
        if start >= 0:
            # 找匹配的 }
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break
        return {"raw_text": text[:2000]}

    async def get_analysis_history(
        self,
        db: AsyncSession,
        project_id: str,
        task_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取已保存的分析历史。"""
        query = select(ReviewReport).where(
            ReviewReport.project_id == project_id,
            ReviewReport.task_type.isnot(None),
        )
        if task_type:
            query = query.where(ReviewReport.task_type == task_type)
        result = await db.execute(query.order_by(ReviewReport.chapter_number.asc()))
        reports = result.scalars().all()
        return [
            {
                "id": str(r.id),
                "task_type": r.task_type,
                "chapter_number": r.chapter_number,
                "overall_score": float(r.overall_score) if r.overall_score else None,
                "issues": r.issues or [],
                "dimension_scores": r.dimension_scores or {},
                "summary": r.summary or "",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
