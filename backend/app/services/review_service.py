"""
Structured review service — 5-dimension quality review for chapters.
Each dimension runs as an independent LLM call (parallel via asyncio.gather).
"""
import json
import re
from typing import Any

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_client import AIClient
from app.services.ai_service import AIService
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.worldview import Worldview
from app.models.character import Character


# ── Dimension definitions ──────────────────────────────────────────────
DIMENSIONS = [
    "设定一致性",
    "时间线",
    "叙事连贯",
    "角色一致性",
    "逻辑",
]

# Severity -> score penalty
SEVERITY_PENALTY = {
    "critical": 35,
    "high": 15,
    "medium": 6,
    "low": 2,
}

# Human-readable labels for each dimension
DIMENSION_LABELS_CN = {
    "设定一致性": "Setting Consistency",
    "时间线": "Timeline",
    "叙事连贯": "Narrative Coherence",
    "角色一致性": "Character Consistency",
    "逻辑": "Logic",
}

# ── Dimension prompts ──────────────────────────────────────────────────

DIMENSION_PROMPTS = {
    "设定一致性": (
        "你是一位小说设定审查员。请检查本章内容与项目世界观设定的一致性。\n\n"
        "### 世界观设定\n{worldview}\n\n"
        "### 本章内容\n{chapter_content}\n\n"
        "请检查以下方面：\n"
        "- 场景、地点、时代背景是否与世界观设定一致\n"
        "- 魔法/科技/超自然规则是否被遵守\n"
        "- 社会结构、文化习俗是否有矛盾\n"
        "- 是否有新引入的设定与已有设定冲突\n\n"
        "输出严格JSON格式（不要markdown包裹）：\n"
        '{{\n'
        '  "dimension": "设定一致性",\n'
        '  "score": 100,\n'
        '  "issues": [\n'
        '    {{\n'
        '      "severity": "critical|high|medium|low",\n'
        '      "location": "位置描述",\n'
        '      "description": "问题描述",\n'
        '      "evidence": "原文证据",\n'
        '      "fix_hint": "修复建议",\n'
        '      "blocking": true/false\n'
        '    }}\n'
        '  ],\n'
        '  "summary": "本维度简要评价"\n'
        '}}'
    ),
    "时间线": (
        "你是一位小说时间线审查员。请检查本章内容的时间线一致性。\n\n"
        "### 已有章节摘要\n{chapter_summaries}\n\n"
        "### 本章内容\n{chapter_content}\n\n"
        "请检查以下方面：\n"
        "- 时间顺序是否合理（季节、日夜、日期）\n"
        "- 事件之间的时间间隔是否合理\n"
        "- 角色年龄、经历的时间跨度是否一致\n"
        "- 是否有时间悖论或逻辑矛盾\n\n"
        "输出严格JSON格式（不要markdown包裹）：\n"
        '{{\n'
        '  "dimension": "时间线",\n'
        '  "score": 100,\n'
        '  "issues": [\n'
        '    {{\n'
        '      "severity": "critical|high|medium|low",\n'
        '      "location": "位置描述",\n'
        '      "description": "问题描述",\n'
        '      "evidence": "原文证据",\n'
        '      "fix_hint": "修复建议",\n'
        '      "blocking": true/false\n'
        '    }}\n'
        '  ],\n'
        '  "summary": "本维度简要评价"\n'
        '}}'
    ),
    "叙事连贯": (
        "你是一位小说叙事审查员。请检查本章的叙事连贯性。\n\n"
        "### 核心故事设定\n{story_core}\n\n"
        "### 已有章节摘要\n{chapter_summaries}\n\n"
        "### 本章内容\n{chapter_content}\n\n"
        "请检查以下方面：\n"
        "- 情节是否自然衔接前一章\n"
        "- 是否有突然的情节断裂或跳跃\n"
        "- 伏笔是否得到合理回应\n"
        "- 叙事视角是否保持一致\n"
        "- 情感节奏是否连贯\n\n"
        "输出严格JSON格式（不要markdown包裹）：\n"
        '{{\n'
        '  "dimension": "叙事连贯",\n'
        '  "score": 100,\n'
        '  "issues": [\n'
        '    {{\n'
        '      "severity": "critical|high|medium|low",\n'
        '      "location": "位置描述",\n'
        '      "description": "问题描述",\n'
        '      "evidence": "原文证据",\n'
        '      "fix_hint": "修复建议",\n'
        '      "blocking": true/false\n'
        '    }}\n'
        '  ],\n'
        '  "summary": "本维度简要评价"\n'
        '}}'
    ),
    "角色一致性": (
        "你是一位小说角色审查员。请检查本章中角色的行为是否符合已有设定。\n\n"
        "### 角色设定\n{characters}\n\n"
        "### 已有章节摘要\n{chapter_summaries}\n\n"
        "### 本章内容\n{chapter_content}\n\n"
        "请检查以下方面：\n"
        "- 角色言行是否符合其性格设定\n"
        "- 角色关系是否与已有设定一致\n"
        "- 角色能力/知识水平是否一致\n"
        "- 角色称呼、关系称谓是否有误\n"
        "- 是否有角色OOC（Out of Character）问题\n\n"
        "输出严格JSON格式（不要markdown包裹）：\n"
        '{{\n'
        '  "dimension": "角色一致性",\n'
        '  "score": 100,\n'
        '  "issues": [\n'
        '    {{\n'
        '      "severity": "critical|high|medium|low",\n'
        '      "location": "位置描述",\n'
        '      "description": "问题描述",\n'
        '      "evidence": "原文证据",\n'
        '      "fix_hint": "修复建议",\n'
        '      "blocking": true/false\n'
        '    }}\n'
        '  ],\n'
        '  "summary": "本维度简要评价"\n'
        '}}'
    ),
    "逻辑": (
        "你是一位小说逻辑审查员。请检查本章内容的逻辑合理性。\n\n"
        "### 核心故事设定\n{story_core}\n\n"
        "### 已有章节摘要\n{chapter_summaries}\n\n"
        "### 本章内容\n{chapter_content}\n\n"
        "请检查以下方面：\n"
        "- 因果关系是否合理\n"
        "- 角色行为动机是否充分\n"
        "- 情节发展是否有逻辑漏洞\n"
        "- 物理/自然法则是否被违反（除非有设定解释）\n"
        "- 对话逻辑是否自洽\n\n"
        "输出严格JSON格式（不要markdown包裹）：\n"
        '{{\n'
        '  "dimension": "逻辑",\n'
        '  "score": 100,\n'
        '  "issues": [\n'
        '    {{\n'
        '      "severity": "critical|high|medium|low",\n'
        '      "location": "位置描述",\n'
        '      "description": "问题描述",\n'
        '      "evidence": "原文证据",\n'
        '      "fix_hint": "修复建议",\n'
        '      "blocking": true/false\n'
        '    }}\n'
        '  ],\n'
        '  "summary": "本维度简要评价"\n'
        '}}'
    ),
}


# ── Helpers ────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    """Extract the first JSON object from text, tolerating markdown fences."""
    # Remove markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    # Find the first { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _extract_content(chapter: Chapter) -> str:
    """Extract readable text content from a chapter."""
    if isinstance(chapter.content, dict):
        return json.dumps(chapter.content, ensure_ascii=False, indent=2)
    if isinstance(chapter.content, str):
        return chapter.content
    return str(chapter.content or "")


def _calc_overall_score(dimension_scores: dict[str, float], issues: list[dict]) -> float:
    """Calculate overall score: weighted average of dimension scores.
    
    Dimension scores already reflect issue penalties (AI deducts per problem),
    so we do NOT double-penalize here. The issues are just for reporting.
    """
    if not dimension_scores:
        return 100.0
    # Weight: dimensions with more blocking/critical issues get extra weight
    # but default to equal weight when no issues
    weights: dict[str, float] = {dim: 1.0 for dim in dimension_scores}
    for issue in issues:
        dim = issue.get("dimension", "")
        if dim in weights:
            sev = issue.get("severity", "low")
            extra = {"critical": 0.5, "high": 0.3, "medium": 0.1, "low": 0.0}
            weights[dim] += extra.get(sev, 0)
    total_weight = sum(weights.values())
    weighted_sum = sum(
        dimension_scores[dim] * weights[dim] for dim in dimension_scores
    )
    return round(weighted_sum / total_weight, 2)


def _count_severities(issues: list[dict]) -> dict[str, int]:
    """Count issues by severity level."""
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for issue in issues:
        sev = issue.get("severity", "low")
        if sev in counts:
            counts[sev] += 1
    return counts


def _count_blocking(issues: list[dict]) -> int:
    """Count blocking issues."""
    return sum(1 for i in issues if i.get("blocking", False))


# ── Main service ───────────────────────────────────────────────────────

class ReviewService:
    """5-dimension structured review service."""

    def __init__(self, ai_service: AIService):
        self._ai_service = ai_service

    async def _call_dimension(
        self,
        db: AsyncSession,
        dimension: str,
        chapter_content: str,
        story_core: str,
        worldview: str,
        characters: str,
        chapter_summaries: str,
    ) -> dict:
        """Call AI for a single dimension review."""
        prompt_template = DIMENSION_PROMPTS[dimension]
        user_prompt = prompt_template.format(
            chapter_content=chapter_content[:3000],
            story_core=story_core or "（无）",
            worldview=worldview or "（无）",
            characters=characters or "（无）",
            chapter_summaries=chapter_summaries or "（无）",
        )

        system_prompt = (
            "你是一位专业的小说质量审查员。请严格按照要求的JSON格式输出审查结果。\n"
            "评分规则：100分起评，每个问题根据严重程度减分。\n"
            "severity级别：critical（严重矛盾，-35分）、high（明显问题，-15分）、"
            "medium（一般问题，-6分）、low（细微问题，-2分）。\n"
            "blocking=true表示该问题会阻断剧情，必须修复。\n"
            "每个issue必须包含：severity, location, description, evidence, fix_hint, blocking字段。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        client = await self._ai_service._build_client(db)
        try:
            result = await client.chat(
                messages, temperature=0.3, max_tokens=4096
            )
            parsed = _extract_json(str(result))
            if parsed is None:
                # Fallback: return a minimal valid result
                return {
                    "dimension": dimension,
                    "score": 100,
                    "issues": [],
                    "summary": "审查结果解析失败，请重试。",
                }
            return parsed
        finally:
            await client.close()

    async def review_chapter(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict:
        """Run full 5-dimension review on a chapter. Returns the review report dict."""
        # Gather context
        story_core = json.dumps(project.story_core or {}, ensure_ascii=False)
        worldview_text = await self._get_worldview_text(db, project.id)
        characters_text = await self._get_characters_text(db, project.id)
        chapter_summaries = await self._get_chapter_summaries(db, project.id, chapter.chapter_number)
        chapter_content = _extract_content(chapter)

        # Run all 5 dimensions in parallel
        tasks = [
            self._call_dimension(
                db, dim, chapter_content, story_core,
                worldview_text, characters_text, chapter_summaries,
            )
            for dim in DIMENSIONS
        ]
        dimension_results = await asyncio.gather(*tasks)

        # Aggregate results
        dimension_scores: dict[str, float] = {}
        all_issues: list[dict] = []
        dimension_summaries: list[str] = []

        for result in dimension_results:
            dim_name = result.get("dimension", "未知")
            score = result.get("score", 100)
            dimension_scores[dim_name] = float(score)
            issues = result.get("issues", [])
            for issue in issues:
                issue["dimension"] = dim_name
            all_issues.extend(issues)
            summary = result.get("summary", "")
            if summary:
                dimension_summaries.append(f"【{dim_name}】{summary}")

        # Sort issues: blocking first, then by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_issues.sort(key=lambda i: (
            0 if i.get("blocking", False) else 1,
            severity_order.get(i.get("severity", "low"), 99),
        ))

        overall_score = _calc_overall_score(dimension_scores, all_issues)
        severity_counts = _count_severities(all_issues)

        report = {
            "project_id": str(project.id),
            "chapter_number": chapter.chapter_number,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "severity_counts": severity_counts,
            "issues": all_issues,
            "blocking_count": _count_blocking(all_issues),
            "summary": "\n\n".join(dimension_summaries),
        }

        # ── Phase 7a：骨架覆盖率评估（追加为第六个"软维度"） ────────
        skeleton_eval = await self._evaluate_skeleton_coverage(
            chapter, chapter_content)
        report["skeleton_coverage"] = skeleton_eval

        # 若覆盖率 < 60%，添加一条 warning 级别的 issue
        if skeleton_eval.get("coverage_ratio") is not None:
            if skeleton_eval["coverage_ratio"] < 0.6:
                report["issues"].insert(0, {
                    "dimension": "骨架覆盖率",
                    "severity": "warning",
                    "location": "整体章节结构",
                    "description": skeleton_eval["message"],
                    "evidence": "",
                    "fix_hint": "对照骨架面板，补充未覆盖的节拍/承诺/事件。",
                    "blocking": False,
                })
                report["severity_counts"]["warning"] = (
                    report["severity_counts"].get("warning", 0) + 1
                )

        return report

    # ── Context helpers ──────────────────────────────────────────────────

    async def _get_worldview_text(self, db: AsyncSession, project_id) -> str:
        result = await db.execute(
            select(Worldview).where(Worldview.project_id == project_id)
        )
        worldviews = result.scalars().all()
        if not worldviews:
            return ""
        parts = []
        for w in worldviews:
            rules = "\n".join(f"  - {r}" for r in (w.rules or []))
            timeline = json.dumps(w.timeline or [], ensure_ascii=False)
            parts.append(
                f"### {w.name}\n"
                f"描述：{w.description}\n"
                f"规则：\n{rules}\n"
                f"时间线：{timeline}"
            )
        return "\n\n".join(parts)

    async def _get_characters_text(self, db: AsyncSession, project_id) -> str:
        result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = result.scalars().all()
        if not characters:
            return ""
        parts = []
        for c in characters:
            personality = ", ".join(c.personality if isinstance(c.personality, list) else [])
            relationships = json.dumps(c.relationships or [], ensure_ascii=False)
            parts.append(
                f"- {c.name}（{c.role_type}）\n"
                f"  性格：{personality}\n"
                f"  背景：{c.background}\n"
                f"  外貌：{c.appearance}\n"
                f"  关系：{relationships}"
            )
        return "\n".join(parts)

    async def _get_chapter_summaries(self, db: AsyncSession, project_id, current_chapter: int) -> str:
        result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number.asc())
        )
        chapters = result.scalars().all()
        parts = []
        for ch in chapters:
            if ch.chapter_number == current_chapter:
                continue
            summary = ch.summary or "（无摘要）"
            parts.append(f"第{ch.chapter_number}章 {ch.title}：{summary}")
        return "\n".join(parts) if parts else "（无已有章节）"

    # ── Phase 7a：骨架覆盖率评估 ───────────────────────────────────
    async def _evaluate_skeleton_coverage(
        self,
        chapter: Chapter,
        chapter_content: str,
    ) -> dict:
        """计算 CBN/CPNs/CEN 骨架覆盖率。"""
        skeleton = chapter.skeleton or {}
        cbn = skeleton.get("cbn", {}) or {}
        cpns = skeleton.get("cpns", {}) or {}
        cen = skeleton.get("cen", {}) or {}

        beats: list[dict] = cbn.get("beats", []) or []
        promises: list[dict] = cpns.get("promises", []) or []
        events: list[dict] = cen.get("events", []) or []
        total = len(beats) + len(promises) + len(events)

        if total == 0:
            return {
                "coverage_ratio": None,
                "covered_count": 0,
                "total_count": 0,
                "message": "无骨架定义，无法评估覆盖率",
            }

        covered = (
            sum(1 for b in beats if b.get("covered") or b.get("status") in ("covered", "done"))
            + sum(1 for p in promises if p.get("status") in ("paid_off", "resolved", "covered", "done"))
            + sum(1 for e in events if e.get("covered") or e.get("status") in ("covered", "done"))
        )
        coverage = round(covered / total, 2)
        return {
            "coverage_ratio": coverage,
            "covered_count": covered,
            "total_count": total,
            "message": f"骨架覆盖率 {coverage:.0%}（{covered}/{total}）"
            + (", 低于 60%，请检查内容是否偏离骨架。" if coverage < 0.6 else "，骨架覆盖良好。"),
        }