"""Context Agent: 五段式写作任务书。

纯数据库查询与文本组装，不调用外部 AI。
输入当前项目数据（故事核心、世界观、角色、章纲、前章、伏笔、记忆系统数据），
输出可直接注入 chapter.yaml / user prompt 的五段式写作指令。

五段权重：章纲 > 前文记忆 > 故事核心 > 世界观
"""
from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.character import Character
from app.models.foreshadowing import Foreshadowing
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.memory_item import MemoryItem


class ContextAgentService:
    """五段式任务书生成器。"""

    def __init__(self, db: AsyncSession, project_id: str, chapter_number: int):
        self.db = db
        self.project_id = project_id
        self.chapter_number = chapter_number

    # ── 公共入口 ───────────────────────────────────────────────
    async def build_writing_task_book(self) -> str:
        """生成五段式写作任务书字符串。"""
        project = await self._project()
        chapter = await self._chapter()
        previous_chapters = await self._previous_chapters()
        characters = await self._characters()
        worldviews = await self._worldviews()
        foreshadowings = await self._foreshadowings()
        memory_pack = await self._memory_pack()
        writing_guide = await self._writing_guide(chapter)
        style_section = await self._style_section(project, chapter)

        first_section = self._build_first_section(project, chapter)
        second_section = await self._build_second_section(project, chapter, previous_chapters, characters, worldviews, foreshadowings, memory_pack)
        third_section = self._build_third_section(project, chapter, characters, memory_pack)
        fourth_section = await self._build_fourth_section(project, chapter, style_section, writing_guide, memory_pack)
        fifth_section = self._build_fifth_section(project, chapter, previous_chapters, characters, memory_pack)

        return "\n---\n".join([
            first_section,
            second_section,
            third_section,
            fourth_section,
            fifth_section,
        ])

    # ── 五段内容 ───────────────────────────────────────────────
    def _build_first_section(self, project: Project | None, chapter: Chapter | None) -> str:
        book_name = project.name if project else "本书"
        ch_num = chapter.chapter_number if chapter else self.chapter_number
        ch_title = chapter.title if chapter and chapter.title else "本章"
        purpose = (chapter.outline_detail or {}).get("purpose", "") if chapter else ""

        parts = [
            f"书名：{book_name}",
            f"章号：第{ch_num}章",
            f"本章标题：{ch_title}",
        ]
        if purpose:
            parts.append(f"一句话目标：{purpose}")
        else:
            parts.append("一句话目标：推进主线情节，保持人物状态一致，留下下一章的钩子。")
        return "【开篇委托】\n" + "\n".join(parts)

    async def _build_second_section(
        self,
        project: Project | None,
        chapter: Chapter | None,
        previous_chapters: list[Chapter],
        characters: list[Character],
        worldviews: list[Worldview],
        foreshadowings: list[Foreshadowing],
        memory_pack: dict[str, Any],
    ) -> str:
        ch_num = chapter.chapter_number if chapter else self.chapter_number
        lines = ["【这章的故事】"]

        # 前文摘要（权重：前文记忆 > 故事核心）
        prev_lines = [
            f"第{c.chapter_number}章《{c.title}》：{c.summary or '（前章暂无摘要）'}"
            for c in previous_chapters[-3:]
        ]
        lines.append(f"前文摘要（近{len(prev_lines)}章）：")
        lines.extend(prev_lines if prev_lines else ["无"])

        # 本章目标 / 阻力（权重：章纲）
        detail = (chapter.outline_detail or {}) if chapter else {}
        purpose = detail.get("purpose", "")
        conflict = detail.get("conflict", "")
        lines.append(f"本章目标：{purpose or '（细纲未填写本章目标）'}")
        lines.append(f"本章阻力：{conflict or '（细纲未填写冲突描述）'}")

        # 情节节点（CBN / CPNs / CEN）
        skeleton_lines = []
        skeleton = (chapter.skeleton or {}) if chapter else {}
        cbn = skeleton.get("cbn") or {}
        cpns = skeleton.get("cpns") or {}
        cen = skeleton.get("cen") or {}
        if cbn:
            beats = cbn.get("beats") or cbn.get("nodes") or []
            if beats:
                skeleton_lines.append("CBN（5节拍）：" + " / ".join(str(b) for b in beats if b))
            else:
                skeleton_lines.append("CBN：细纲骨架尚未填写")
        if cpns:
            promises = cpns.get("promises") or []
            if promises:
                skeleton_lines.append("CPNs（承诺清单）：" + " / ".join(str(p) for p in promises if p))
            else:
                skeleton_lines.append("CPNs：细纲承诺尚未填写")
        if cen:
            events = cen.get("events") or []
            if events:
                skeleton_lines.append("CEN（事件清单）：" + " / ".join(str(e) for e in events if e))
            else:
                skeleton_lines.append("CEN：细纲事件尚未填写")
        if skeleton_lines:
            lines.append("情节节点：\n" + "\n".join(f"- {x}" for x in skeleton_lines))
        else:
            lines.append("情节节点：未检测到 CBN / CPNs / CEN，请按细纲的开场、核心事件、钩子推进。")

        # 必须覆盖 / 禁区（优先级：章纲 > 记忆 / 伏笔）
        must_cover = []
        forbidden = []
        if chapter:
            highlights = detail.get("highlights", "")
            suspense = detail.get("suspense", "")
            hooks = detail.get("hooks", "")
            if highlights:
                must_cover.append(f"高光点：{highlights}")
            if suspense:
                must_cover.append(f"悬念：{suspense}")
            if hooks:
                must_cover.append(f"钩子：{hooks}")

        current_foreshadowings = [
            f for f in foreshadowings
            if f.target_chapter == ch_num and f.status not in ("paid_off", "resolved", "closed")
        ]
        for f in current_foreshadowings:
            must_cover.append(f"伏笔安排：{f.title}（{f.description}）")

        # 角色未解决弧线与开放承诺
        sem = memory_pack.get("semantic_memory", [])
        open_loops = [s for s in sem if s.get("category") == "open_loop" and s.get("status") != "resolved"]
        if open_loops:
            must_cover.extend(
                f"{s.get('subject', '伏笔')}：{s.get('value', '')}" for s in open_loops[:5]
            )

        lines.append("必须覆盖：")
        lines.extend(f"- {x}" for x in must_cover) if must_cover else lines.append("- （无）")

        # 禁区：来自世界观硬规则 + 已回收伏笔的反向提醒
        worldview_rules = []
        for wv in self._safe_worldview_texts(worldviews):
            if "规则" in wv or "限制" in wv or "不可" in wv:
                worldview_rules.append(wv)
        paid_off = [f for f in foreshadowings if f.status in ("paid_off", "resolved", "closed")]
        if paid_off:
            forbidden.append("已回收伏笔不要重复当作新事件再推一次。")
        if worldview_rules:
            forbidden.append("世界观硬规则：" + "；".join(worldview_rules[:3]))

        lines.append("禁区：")
        lines.extend(f"- {x}" for x in forbidden) if forbidden else lines.append("- （无）")

        # 跨章约束
        cross_lines = [
            f"保持与第{previous_chapters[-1].chapter_number}章的结尾情绪一致，衔接顺畅。"
            if previous_chapters
            else "作为开篇章节，直接建立人物状态与核心冲突。",
            "不要把前章未完成的冲突在本章一次性解决完，保留延续感。",
            "角色状态不得与最新章节设定相矛盾。",
        ]
        lines.append("跨章约束：")
        lines.extend(f"- {x}" for x in cross_lines)

        return "\n".join(lines)

    def _build_third_section(
        self,
        project: Project | None,
        chapter: Chapter | None,
        characters: list[Character],
        memory_pack: dict[str, Any],
    ) -> str:
        lines = ["【这章的人物】"]
        if not characters:
            lines.append("暂无角色数据。")
            return "\n".join(lines)

        # 角色记忆补充：最新状态 / 关系 / 伏笔
        char_states: dict[str, str] = {}
        char_relationships: dict[str, str] = {}
        for m in memory_pack.get("semantic_memory", []):
            if m.get("category") == "character_state" and m.get("subject") in {c.name for c in characters}:
                char_states.setdefault(m.get("subject", ""), "")
                char_states[m.get("subject", "")] += f"{m.get('field', '')}：{m.get('value', '')}；"
            if m.get("category") == "relationship" and m.get("subject") in {c.name for c in characters}:
                char_relationships.setdefault(m.get("subject", ""), "")
                char_relationships[m.get("subject", "")] += f"{m.get('field', '')}：{m.get('value', '')}；"

        # 角色弧线：从细纲或角色数据提取
        detail = (chapter.outline_detail or {}) if chapter else {}
        arc_hint = detail.get("character_arc", "")

        lines.append("每人一段：")
        for c in characters:
            char_lines = []
            char_lines.append(f"{c.name}（{c.role_type}）")
            char_lines.append(f"状态：{c.background or '（未设置）'}")
            if char_states.get(c.name):
                char_lines.append(f"近期状态：{char_states[c.name].rstrip('；')}")
            if char_relationships.get(c.name):
                char_lines.append(f"关系：{char_relationships[c.name].rstrip('；')}")
            char_lines.append("驱动力：推进本章冲突或承担情绪落点。")
            char_lines.append("本章作用：围绕本章目标完成行动 / 回应 / 转折。")
            if arc_hint:
                char_lines.append(f"弧线提示：{arc_hint}")
            lines.append("\n".join(char_lines))
            lines.append("")

        return "\n".join(lines).rstrip()

    async def _build_fourth_section(
        self,
        project: Project | None,
        chapter: Chapter | None,
        style_section: str,
        writing_guide: str,
        memory_pack: dict[str, Any],
    ) -> str:
        lines = ["【怎么写更顺】"]
        genre = project.genre if project else ""
        ch_num = chapter.chapter_number if chapter else self.chapter_number

        # 风格优先级
        lines.append("风格优先级：")
        if style_section:
            lines.append(style_section)
        elif genre:
            lines.append(f"题材：{genre}；按该题材的节奏、词汇密度与情感温度展开。")
        else:
            lines.append("先稳人物状态，再推进情节，最后留钩子。")

        # 节奏策略（从细纲 pacing 字段读取）
        pacing = ((chapter.outline_detail or {}).get("pacing", "")) if chapter else ""
        if pacing:
            lines.append(f"节奏策略：{pacing}")
        else:
            lines.append("节奏策略：开场进入冲突，中段加深阻力，结尾留下未解问题。")

        # 写作指南片段（来自 writing_guide_service / genre_weighted_style）
        if writing_guide:
            lines.append("写作指南：")
            lines.append(writing_guide)

        # 审查得分趋势 / 阅读压力（从记忆系统读取最近 review / debt）
        trend_lines = []
        for m in memory_pack.get("semantic_memory", []):
            if m.get("category") in ("review_score", "debt_hint", "style_guidance", "ai_flavor_score"):
                trend_lines.append(f"{m.get('subject', '')}.{m.get('field', '')}：{m.get('value', '')}")
        if trend_lines:
            lines.append("审查得分趋势：")
            lines.extend(f"- {x}" for x in trend_lines[:8])
        else:
            lines.append("审查得分趋势：近期无明确审查记录，请优先保证情节推进与人物一致。")

        return "\n".join(lines)

    def _build_fifth_section(
        self,
        project: Project | None,
        chapter: Chapter | None,
        previous_chapters: list[Chapter],
        characters: list[Character],
        memory_pack: dict[str, Any],
    ) -> str:
        lines = ["【收在哪里】"]
        ch_num = chapter.chapter_number if chapter else self.chapter_number
        chapter_count = len(previous_chapters) + 1

        hooks = []
        # 钩子优先来自细纲 suspense / hooks
        detail = (chapter.outline_detail or {}) if chapter else {}
        suspense = detail.get("suspense", "")
        hooks_text = detail.get("hooks", "")
        if suspense:
            hooks.append(f"悬念：{suspense}")
        if hooks_text:
            hooks.append(f"钩子：{hooks_text}")

        # 未解决伏笔 / 开放环作为结尾锚点
        open_loops = [m for m in memory_pack.get("semantic_memory", []) if m.get("category") == "open_loop"]
        if open_loops:
            hooks.append("未回收伏笔锚点：" + " / ".join(f"{m.get('subject', '')}({m.get('value', '')})" for m in open_loops[:3]))

        lines.append("结尾停在什么感觉：")
        if hooks:
            lines.append("停在一处未解决的悬念或一个刚冒头的冲突上，读者能清晰感到下一章必须继续。")
            lines.extend(f"- {h}" for h in hooks)
        else:
            lines.append("停在人物一个明确的未解决选择上，不要在本章内把所有冲突收束干净。")

        lines.append("")
        lines.append("留什么未完感：")
        unfinished = [
            "至少一个问题悬而未决：是冲突未解、人物未决，还是伏笔未回收。",
            "不要让所有线索在本章内全部闭合，保留延续到下一节的动作。",
        ]
        if project:
            unfinished.append(f"与全书主线（{project.name}）保持强关联。")
        lines.extend(f"- {x}" for x in unfinished)

        return "\n".join(lines)

    # ── 数据查询 ───────────────────────────────────────────────
    async def _project(self) -> Project | None:
        result = await self.db.execute(select(Project).where(Project.id == self.project_id))
        return result.scalar_one_or_none()

    async def _chapter(self) -> Chapter | None:
        result = await self.db.execute(
            select(Chapter)
            .where(Chapter.project_id == self.project_id, Chapter.chapter_number == self.chapter_number)
        )
        return result.scalar_one_or_none()

    async def _previous_chapters(self) -> list[Chapter]:
        result = await self.db.execute(
            select(Chapter)
            .where(Chapter.project_id == self.project_id, Chapter.chapter_number < self.chapter_number)
            .order_by(Chapter.chapter_number.desc())
        )
        return list(result.scalars().all())

    async def _characters(self) -> list[Character]:
        result = await self.db.execute(
            select(Character).where(Character.project_id == self.project_id)
        )
        return list(result.scalars().all())

    async def _worldviews(self) -> list[Worldview]:
        result = await self.db.execute(
            select(Worldview).where(Worldview.project_id == self.project_id)
        )
        return list(result.scalars().all())

    async def _foreshadowings(self) -> list[Foreshadowing]:
        result = await self.db.execute(
            select(Foreshadowing).where(Foreshadowing.project_id == self.project_id)
            .order_by(Foreshadowing.target_chapter.asc(), Foreshadowing.created_at.asc())
        )
        return list(result.scalars().all())

    async def _memory_pack(self) -> dict[str, Any]:
        """复用记忆系统数据，避免重复组装。"""
        try:
            from app.services.memory_orchestrator import build_memory_pack_for_chapter
            return await build_memory_pack_for_chapter(
                self.db, self.project_id, self.chapter_number, task_type="write", auto_bootstrap=False,
            )
        except Exception as exc:  # noqa: BLE001
            return {"working_memory": [], "episodic_memory": [], "semantic_memory": [], "stats": {"error": str(exc)}}

    async def _style_section(self, project: Project | None, chapter: Chapter | None) -> str:
        """整合 genre_weighted_style 的风格建议。"""
        try:
            from app.services.genre_weighted_style import GenreStyleWeighter
            genre = project.genre if project and project.genre else "都市日常"
            chapter_type = ((chapter.outline_detail or {}).get("pacing", "normal")) if chapter else "normal"
            weighter = GenreStyleWeighter()
            return weighter.build_style_prompt_section(genre=genre, chapter_type=chapter_type)
        except Exception as exc:  # noqa: BLE001
            return f"风格建议：{exc}"

    async def _writing_guide(self, chapter: Chapter | None) -> str:
        """整合 writing_guide_service 的写作指南。"""
        try:
            from app.services.writing_guide_service import build_writing_prompt_section
            detail = (chapter.outline_detail or {}) if chapter else {}
            chapter_type = detail.get("pacing", "normal")
            pacing_map = {"快": "combat", "极快": "combat", "慢": "emotional", "中速": "normal"}
            chapter_type = pacing_map.get(chapter_type, chapter_type)
            return build_writing_prompt_section(chapter_type=chapter_type, include_anti_ai=True, include_style=True)
        except Exception as exc:  # noqa: BLE001
            return f"写作指南：{exc}"

    @staticmethod
    def _safe_worldview_texts(worldviews: list[Worldview]) -> list[str]:
        parts = []
        for wv in worldviews:
            parts.append(wv.name or "")
            if wv.description:
                parts.append(wv.description)
            for rule in (wv.rules or []):
                if rule:
                    parts.append(rule)
        return parts


def build_writing_task_book(db: AsyncSession, project_id: str, chapter_number: int) -> str:
    """同步调用入口：构建五段式写作任务书。"""
    service = ContextAgentService(db, project_id, chapter_number)
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(service.build_writing_task_book())


def build_writing_task_book_sync(db: AsyncSession, project_id: str, chapter_number: int) -> str:
    """同步包装：仅用于无法 await 的旧调用点。"""
    return build_writing_task_book(db, project_id, chapter_number)
