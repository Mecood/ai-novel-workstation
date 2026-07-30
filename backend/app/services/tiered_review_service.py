"""
三层评审服务 — 将单层 5 维审查拆分为 L1/L2/L3 流水线。

L1: 零 LLM 硬指标检查（字数 / 标题 / 新增实体 / 骨架要求）
L2: LLM 5 维审查（复用 ReviewService）
L3: AI 综合裁决（含反幻觉 3 定律：大纲即法律 / 设定即物理 / 发明需识别）
"""
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import AIService
from app.services.review_service import ReviewService
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.chapter_contract import ChapterContract
from app.models.character import Character
from app.models.worldview import Worldview
from app.models.story_event import StoryEvent


class TieredReviewError(Exception):
    """三层评审过程中的异常。"""
    pass


# ── 反幻觉 3 定律标识 ──────────────────────────────────────────────────
LAWS = {
    "outline_is_law": "大纲即法律",
    "setting_is_physics": "设定即物理",
    "invention_must_be_flagged": "发明需识别",
}


class TieredReviewService:
    """
    三层评审流水线。
    流程: L1 → (若 L1_PASS) L2 → L3。
    若 L1_FAIL，直接返回 L1_FAIL 结果，不执行 L2/L3。
    """

    def __init__(self, ai_service: AIService):
        self._ai_service = ai_service
        self._review_service = ReviewService(ai_service)

    async def run_tiered_review(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """执行完整三层评审，返回 tiered_results dict。"""
        # 1) L1 硬指标检查
        l1_result = await self._run_l1(db, project, chapter)

        # 如果 L1_FAIL，直接返回，不执行 L2/L3
        if l1_result["status"] == "FAIL":
            return {
                "l1": l1_result,
                "l2": None,
                "l3": None,
            }

        # 2) L2 软指标审查（复用现有 5 维审查）
        l2_result = await self._run_l2(db, project, chapter)

        # 3) L3 终审（含反幻觉 3 定律）
        l3_result = await self._run_l3(db, project, chapter, l1_result, l2_result)

        return {
            "l1": l1_result,
            "l2": l2_result,
            "l3": l3_result,
        }

    # ── L1 硬指标检查 ──────────────────────────────────────────────────

    async def _run_l1(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """执行 L1 硬指标检查，返回 L1 结果 dict。"""
        checks: list[dict[str, Any]] = []

        # 1) 字数范围检查
        word_range = self._get_word_count_range(project)
        word_count = chapter.word_count or 0
        content_text = self._extract_chapter_text(chapter)
        actual_word_count = len(content_text) if content_text else word_count
        wc_passed = word_range["min"] <= actual_word_count <= word_range["max"]
        checks.append({
            "name": "word_count",
            "label": "字数检查",
            "passed": wc_passed,
            "detail": f"当前字数 {actual_word_count}，范围 {word_range['min']}-{word_range['max']}",
            "value": actual_word_count,
            "threshold": f"{word_range['min']}-{word_range['max']}",
        })

        # 2) 章节标题检查
        title_passed = bool(chapter.title and chapter.title.strip())
        checks.append({
            "name": "title_not_empty",
            "label": "章节标题",
            "passed": title_passed,
            "detail": f"标题「{chapter.title or '（空）'}」{'不为空' if title_passed else '为空'}",
            "value": chapter.title or "",
        })

        # 3) 新增角色/事件检测
        new_entities_check = await self._check_new_entities(db, project, chapter)
        checks.append(new_entities_check)

        # 4) 骨架要求满足度检查
        skeleton_check = await self._check_skeleton_requirements(db, project, chapter)
        checks.append(skeleton_check)

        # 汇总
        all_passed = all(c["passed"] for c in checks)
        return {
            "status": "PASS" if all_passed else "FAIL",
            "checks": checks,
        }

    @staticmethod
    def _extract_chapter_text(chapter: Chapter) -> str:
        """从 Chapter 中提取可读文本。"""
        if isinstance(chapter.content, dict):
            return chapter.content.get(
                "text", json.dumps(chapter.content, ensure_ascii=False)
            )
        if isinstance(chapter.content, str):
            return chapter.content
        return str(chapter.content or "")

    @staticmethod
    def _get_word_count_range(project: Project) -> dict[str, int]:
        """从项目配置获取字数范围，默认 4300-10000。"""
        story_core = project.story_core or {}
        wc_config = story_core.get("word_count_range", {})
        return {
            "min": wc_config.get("min", 4300),
            "max": wc_config.get("max", 10000),
        }

    async def _check_new_entities(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """
        检测本章是否引入了新角色/事件。
        策略：从 story_events 表中读取本章已提取的事件，
        对比其 entities 与 characters 表的已知角色名，
        不在已知列表中的标记为 invented。
        """
        # 1) 获取本章已提取的事件实体
        events_result = await db.execute(
            select(StoryEvent).where(
                StoryEvent.project_id == project.id,
                StoryEvent.chapter_number == chapter.chapter_number,
            )
        )
        events = events_result.scalars().all()

        # 2) 获取所有已知角色名
        char_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        characters = char_result.scalars().all()
        known_chars: set[str] = {c.name for c in characters}
        for c in characters:
            for alias in (c.aliases or []):
                known_chars.add(alias)

        # 3) 收集所有实体名，区分 invented 和 existing
        all_entities: set[str] = set()
        for ev in events:
            for e in (ev.entities or []):
                all_entities.add(e)

        invented = [e for e in all_entities if e not in known_chars]
        existing = [e for e in all_entities if e in known_chars]

        # 新增角色本身不是失败，只是标记
        passed = True
        return {
            "name": "new_entities",
            "label": "新增角色/事件检测",
            "passed": passed,
            "detail": (
                f"检测到 {len(invented)} 个新角色/事件"
                if invented
                else "未检测到新增角色/事件"
            ),
            "invented": invented,
            "existing": existing,
        }

    async def _check_skeleton_requirements(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """
        检查本章是否满足契约（chapter_contract）中的 required_nodes。
        策略：从 chapter_contracts 表读取本章已签署的契约，
        检查它的 required_nodes 是否被正文覆盖。
        """
        # 1) 获取本章契约
        contract_result = await db.execute(
            select(ChapterContract).where(
                ChapterContract.project_id == project.id,
                ChapterContract.chapter_number == chapter.chapter_number,
                ChapterContract.status.in_(["signed", "fulfilled"]),
            )
        )
        contract = contract_result.scalar_one_or_none()

        if not contract or not contract.required_nodes:
            # 没有契约 -> 该项跳过视作通过
            return {
                "name": "skeleton_requirements",
                "label": "骨架要求满足度",
                "passed": True,
                "detail": "无契约要求，跳过",
                "covered": 0,
                "total": 0,
                "missed": [],
            }

        required = contract.required_nodes
        total = len(required)
        # 2) 简单检测：检查 required_nodes 的 title/description 是否出现在正文
        content_lower = self._extract_chapter_text(chapter).lower()
        covered: list[str] = []
        missed: list[str] = []

        for node in required:
            node_title = (node.get("title") or "").lower()
            node_desc = (node.get("description") or "").lower()
            node_id = node.get("id")
            # 如果 title 或 description 的关键词出现在正文中，视为覆盖
            if node_title and node_title in content_lower:
                covered.append(node_id)
            elif node_desc and any(
                kw in content_lower for kw in node_desc.split()[:5]
            ):
                covered.append(node_id)
            else:
                missed.append(node_id)

        passed = len(missed) == 0
        return {
            "name": "skeleton_requirements",
            "label": "骨架要求满足度",
            "passed": passed,
            "detail": (
                f"required_nodes 覆盖 {len(covered)}/{total}"
                if not passed
                else f"所有 {total} 个 required_nodes 均已覆盖"
            ),
            "covered": len(covered),
            "total": total,
            "missed": missed,
        }

    # ── L2 软指标审查 ──────────────────────────────────────────────────

    async def _run_l2(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """执行 L2 软指标审查，复用 ReviewService 的 review_chapter 逻辑。"""
        report = await self._review_service.review_chapter(db, project, chapter)
        return {
            "dimension_scores": report.get("dimension_scores", {}),
            "overall_score": report.get("overall_score", 0.0),
            "issues": report.get("issues", []),
            "blocking_count": report.get("blocking_count", 0),
            "summary": report.get("summary", ""),
        }

    # ── L3 终审（含反幻觉 3 定律） ─────────────────────────────────────

    async def _run_l3(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        l1_result: dict[str, Any],
        l2_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        L3 终审 — AI 综合判断。
        输入：L1 结果 + L2 报告 + 反幻觉 3 定律检查结果
        输出：PASS / REVISE / REJECT + 理由
        """
        # 1) 执行反幻觉 3 定律检查
        ah_results = await self._run_anti_hallucination_checks(db, project, chapter)

        # 2) 构建 L3 裁决上下文
        l1_checks = l1_result.get("checks", [])
        l1_summary = f"L1: {sum(1 for c in l1_checks if c['passed'])}/{len(l1_checks)} 检查通过"
        l2_blocking = l2_result.get("blocking_count", 0)
        l2_score = l2_result.get("overall_score", 0.0)
        l2_summary = f"L2: 综合评分 {l2_score}，{l2_blocking} 个阻断问题"

        # 3) 汇总反幻觉阻断
        ah_blocking = [c for c in ah_results if c.get("blocking")]
        _has_ah_blocking = len(ah_blocking) > 0  # noqa: F841 保留语义

        # 4) LLM 综合裁决
        verdict_data = await self._call_l3_llm_judge(
            db, project, chapter, l1_result, l2_result, ah_results,
        )

        # 5) 拼接 L3 输出
        return {
            "verdict": verdict_data.get("verdict", "REVISE"),
            "summary": verdict_data.get("summary", ""),
            "blocking_path": verdict_data.get("blocking_path"),
            "anti_hallucination": ah_results,
            "l1_summary": l1_summary,
            "l2_summary": l2_summary,
            "l3_reasoning": verdict_data.get("reasoning", ""),
        }

    async def _call_l3_llm_judge(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        l1_result: dict[str, Any],
        l2_result: dict[str, Any],
        ah_results: list[dict],
    ) -> dict[str, Any]:
        """调用 LLM 做 L3 综合裁决。"""

        l1_checks = l1_result.get("checks", [])
        l1_failures = [c for c in l1_checks if not c["passed"]]
        l2_issues = l2_result.get("issues", [])
        l2_blocking = [i for i in l2_issues if i.get("blocking")]
        ah_blocking = [c for c in ah_results if c.get("blocking")]

        system_prompt = (
            "你是一位小说质量终审裁决员。你的任务是综合 L1 硬指标检查结果、L2 5 维审查报告、"
            "以及反幻觉 3 定律检查结果，给出最终裁决。\n\n"
            "裁决标准：\n"
            "1. PASS：全部通过，或仅存在轻微问题（low severity）\n"
            "2. REVISE：存在可修复的中等问题（medium severity），建议修改后重新提交\n"
            "3. REJECT：存在阻断问题（blocking issue），必须拒绝\n\n"
            "阻断问题自动触发 REJECT：\n"
            "- L2 中存在 blocking=true 的 issue\n"
            "- 反幻觉检查中存在 blocking=true 的违反\n"
            "- L1 中存在 FAIL 项（但 L1_FAIL 时不会执行到 L3）\n\n"
            "输出严格 JSON 格式（不要 markdown 包裹）：\n"
            "{\n"
            '  "verdict": "PASS" | "REVISE" | "REJECT",\n'
            '  "summary": "综合裁决一句话摘要",\n'
            '  "reasoning": "裁决推理过程（100-200字）",\n'
            '  "blocking_path": "l2.blocking_issues[0]" | "l3.anti_hallucination[1]" | null\n'
            "}"
        )

        user_prompt = (
            f"### 项目：{project.name}\\n"
            f"### 第 {chapter.chapter_number} 章：{chapter.title}\\n\\n"
            f"### L1 结果\\n"
            f"通过 {len([c for c in l1_checks if c['passed']])}/{len(l1_checks)} 项检查\\n"
            f"失败项：{json.dumps(l1_failures, ensure_ascii=False)[:500]}\\n\\n"
            f"### L2 结果\\n"
            f"综合评分：{l2_result.get('overall_score', 0)}\\n"
            f"阻断问题数：{len(l2_blocking)}\\n"
            f"阻断问题详情：{json.dumps(l2_blocking, ensure_ascii=False)[:1000]}\\n"
            f"所有问题：{json.dumps(l2_issues, ensure_ascii=False)[:2000]}\\n\\n"
            f"### 反幻觉检查结果\\n"
            f"阻断数：{len(ah_blocking)}\\n"
            f"详情：{json.dumps(ah_results, ensure_ascii=False)[:1000]}\\n\\n"
            "请给出最终裁决："
        )

        client = await self._ai_service._build_client(db)
        try:
            result = str(await client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            ))
            return self._parse_l3_verdict(result)
        finally:
            await client.close()

    def _parse_l3_verdict(self, text: str) -> dict[str, Any]:
        """解析 L3 LLM 裁决 JSON。"""
        text = re.sub(r"```(?:json)?\s*", "", text)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {
                "verdict": "REVISE",
                "summary": "裁决解析失败，默认 REVISE",
                "reasoning": "LLM 输出格式异常，无法解析",
                "blocking_path": None,
            }
        try:
            data = json.loads(match.group())
            return {
                "verdict": data.get("verdict", "REVISE"),
                "summary": str(data.get("summary", "")),
                "reasoning": str(data.get("reasoning", "")),
                "blocking_path": data.get("blocking_path"),
            }
        except Exception:
            return {
                "verdict": "REVISE",
                "summary": "裁决解析失败，默认 REVISE",
                "reasoning": "JSON 解析异常",
                "blocking_path": None,
            }

    # ═══════════════════════════════════════════════════════════════════
    # 反幻觉 3 定律检查
    # ═══════════════════════════════════════════════════════════════════

    async def _run_anti_hallucination_checks(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> list[dict[str, Any]]:
        """
        执行反幻觉 3 定律检查。
        每条定律返回一个检查结果 dict。
        """
        results: list[dict[str, Any]] = []
        # 定律 1：大纲即法律
        law1 = await self._check_outline_is_law(db, project, chapter)
        results.append(law1)
        # 定律 2：设定即物理
        law2 = await self._check_setting_is_physics(db, project, chapter)
        results.append(law2)
        # 定律 3：发明需识别
        law3 = await self._check_invention_must_be_flagged(db, project, chapter)
        results.append(law3)
        return results

    # ── 定律 1：大纲即法律 ──────────────────────────────────────────────

    async def _check_outline_is_law(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """
        大纲即法律 — 比对正文 vs outline_detail，检测偏离度。
        - 从 chapter.outline_detail 获取本章细纲
        - 将细纲的结构化节点与正文内容做语义比对
        - 检测是否有细纲要求的节点完全缺失
        - 检测是否有正文内容与细纲明显矛盾
        """
        _ = db  # noqa: F841 定律 1 仅依赖 chapter 本身
        outline = chapter.outline_detail
        if not outline:
            return {
                "law": "outline_is_law",
                "label": LAWS["outline_is_law"],
                "passed": True,
                "deviation": None,
                "detail": "本章无细纲（outline_detail），跳过检查",
                "blocking": False,
            }

        # 调用 LLM 做偏离度检测
        content = self._extract_chapter_text(chapter)
        prompt = (
            "你是一位小说大纲一致性审查员。请比对本章正文与本章细纲（outline_detail），\n"
            "检测是否存在以下偏离：\n"
            "1. 细纲要求的核心情节节点在正文中完全缺失\n"
            "2. 正文内容与细纲描述明显矛盾（如：细纲写\"林动在古墓突破\"，正文写\"林动在宗门突破\"）\n"
            "3. 正文增加了细纲未提及但可能破坏逻辑链的新情节\n\n"
            f"### 细纲（outline_detail）\n{json.dumps(outline, ensure_ascii=False)[:2000]}\n\n"
            f"### 本章正文\n{content[:3000]}\n\n"
            "输出严格 JSON 格式（不要 markdown 包裹）：\n"
            "{\n"
            '  "has_deviation": true/false,\n'
            '  "deviation_type": "missing_node" | "contradiction" | "new_plot" | null,\n'
            '  "detail": "详细描述偏离情况",\n'
            '  "is_blocking": true/false\n'
            "}"
        )

        client = await self._ai_service._build_client(db)
        try:
            result = str(await client.chat(
                messages=[
                    {"role": "system", "content": "你是一位严格的大纲一致性审查员。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1500,
            ))
            data = self._parse_anti_hallucination_llm_output(result)
        finally:
            await client.close()

        return {
            "law": "outline_is_law",
            "label": LAWS["outline_is_law"],
            "passed": not data.get("has_deviation", False),
            "deviation": data.get("deviation_type"),
            "detail": data.get("detail", "未检测到偏离"),
            "blocking": data.get("is_blocking", False),
        }

    # ── 定律 2：设定即物理 ──────────────────────────────────────────────

    async def _check_setting_is_physics(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """
        设定即物理 — 比对正文 vs worldview + character 设定，检测违反。
        - 从 worldview 表读取世界观规则（rules）
        - 从 character 表读取角色设定
        - 检测正文中是否有违反世界观规则或角色设定的内容
        """
        # 1) 获取世界观设定
        wv_result = await db.execute(
            select(Worldview).where(Worldview.project_id == project.id)
        )
        worldviews = wv_result.scalars().all()

        # 2) 获取角色设定
        char_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        characters = char_result.scalars().all()

        if not worldviews and not characters:
            return {
                "law": "setting_is_physics",
                "label": LAWS["setting_is_physics"],
                "passed": True,
                "violations": [],
                "detail": "无世界观或角色设定，跳过检查",
                "blocking": False,
            }

        # 3) 格式化设定文本
        wv_text = "\n".join(
            f"### {w.name}\n描述：{w.description}\n规则：\n"
            + "\n".join(f"  - {r}" for r in (w.rules or []))
            for w in worldviews
        )
        char_text = "\n".join(
            f"- {c.name}（{c.role_type}）\n"
            f"  性格：{', '.join(c.personality if isinstance(c.personality, list) else [])}\n"
            f"  背景：{c.background or '无'}\n"
            f"  能力：{json.dumps(c.arc or {}, ensure_ascii=False)[:200]}"
            for c in characters
        )

        content = self._extract_chapter_text(chapter)
        prompt = (
            "你是一位小说设定一致性审查员。请检查本章正文是否违反世界观规则或角色设定。\n\n"
            f"### 世界观设定\n{wv_text[:2000]}\n\n"
            f"### 角色设定\n{char_text[:2000]}\n\n"
            f"### 本章正文\n{content[:3000]}\n\n"
            "请逐条检查以下方面并按格式输出：\n"
            "1. 世界观规则是否被违反（如魔法规则、物理法则、社会结构）\n"
            "2. 角色行为是否符合其性格和能力设定\n"
            "3. 角色关系是否与已有设定一致\n\n"
            "输出严格 JSON 格式（不要 markdown 包裹）：\n"
            "{\n"
            '  "has_violation": true/false,\n'
            '  "violations": [\n'
            "    {\n"
            '      "rule": "被违反的具体规则/设定",\n'
            '      "evidence": "原文证据片段",\n'
            '      "fix_hint": "修复建议",\n'
            '      "is_blocking": true/false\n'
            "    }\n"
            "  ],\n"
            '  "detail": "总结" \n'
            "}"
        )

        client = await self._ai_service._build_client(db)
        try:
            result = str(await client.chat(
                messages=[
                    {"role": "system", "content": "你是一位严格的设定一致性审查员。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            ))
            data = self._parse_anti_hallucination_llm_output(
                result, expect_list="violations"
            )
        finally:
            await client.close()

        violations = data.get("violations", [])
        return {
            "law": "setting_is_physics",
            "label": LAWS["setting_is_physics"],
            "passed": len(violations) == 0,
            "violations": violations,
            "detail": data.get("detail", f"发现 {len(violations)} 处设定违反"),
            "blocking": any(v.get("is_blocking", False) for v in violations),
        }

    # ── 定律 3：发明需识别 ──────────────────────────────────────────────

    async def _check_invention_must_be_flagged(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
    ) -> dict[str, Any]:
        """
        发明需识别 — AI 新增的设定/角色/事件必须标记为 "invented" 而不是 "existing"。
        已知世界观名词（来自 worldview / story_core / character）必须排除，不计为新发明。
        """
        content = self._extract_chapter_text(chapter)

        # 1) 已知角色信息（名字 + 背景 + 外貌，让 LLM 知道这些能力不算新发明）
        char_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        all_chars = char_result.scalars().all()
        known_chars = {c.name for c in all_chars if c.name}

        # 角色背景摘要（注入 LLM 以识别角色已定义的能力）
        char_backgrounds = []
        for c in all_chars:
            if not c.name:
                continue
            info = f"角色「{c.name}」"
            if c.background:
                info += f" 背景：{c.background}"
            if c.personality:
                info += f" 性格：{', '.join(c.personality) if isinstance(c.personality, list) else str(c.personality)}"
            if c.appearance:
                info += f" 外貌：{c.appearance}"
            char_backgrounds.append(info)

        # 2) 世界观设定 — 注入 LLM，让它排除世界观已有名词
        wv_result = await db.execute(
            select(Worldview).where(Worldview.project_id == project.id)
        )
        worldviews = wv_result.scalars().all()
        worldview_texts = []
        for wv in worldviews:
            if wv.description:
                worldview_texts.append(wv.description)
            for wv_desc in (wv.description, wv.rules, wv.timeline):
                if wv_desc and wv_desc not in worldview_texts:
                    worldview_texts.append(str(wv_desc) if isinstance(wv_desc, (dict, list)) else wv_desc)

        # 3) story_core 中的世界观描述
        story_core = project.story_core or {}
        story_core_text = json.dumps(
            {k: v for k, v in story_core.items() if not k.startswith("_")},
            ensure_ascii=False,
        )[:2000]

        # 4) 已知设定提示语（告诉 LLM 这些不算新发明）
        known_setting_section = ""
        if known_chars:
            known_setting_section += "【已有角色名】\n" + "\n".join(f"- {n}" for n in sorted(known_chars)) + "\n"
        if char_backgrounds:
            known_setting_section += "\n【角色设定】（以下角色的背景、能力、关系已定义，相关描述不算新发明）\n" + "\n\n".join(char_backgrounds) + "\n"
        if worldview_texts:
            known_setting_section += "\n【世界观设定】（这些词/概念已经存在于世界观中，不算新发明）\n" + "\n\n".join(worldview_texts[:3]) + "\n"
        if story_core_text:
            known_setting_section += "\n【故事核心 / 核心设定】\n" + story_core_text + "\n"

        # 5) 调用 LLM 检测
        prompt = (
            "你是一位小说内容审计员。请检查本章正文中，哪些元素是AI系统在本章\n"
            "中凭空创造的新设定（即：不属于项目既有世界观、故事核心、角色设定的全新内容），\n"
            "但可能没有被正确标记为 'invented'。\n\n"
            "===== 以下是在此项目已定义的内容（这些不算新发明） =====\n"
            f"{known_setting_section}\n"
            "==============================================\n\n"
            f"### 本章正文\n{content[:3000]}\n\n"
            "检查标准（重要）：\n"
            "1. 角色名：正文中出现但不在【已有角色名】中的角色，才算新发明\n"
            "2. 地名：正文中出现但未在【世界观设定】/【故事核心】中出现的新地点\n"
            "3. 物品/道具：正文中出现但未在任何已有设定中出现的全新物品\n"
            "4. 规则/设定：正文中引入的全新世界观规则\n\n"
            "⚠️ 以下情况算【已有设定】，不算新发明：\n"
            "   - 世界观描述、故事核心中已出现过的概念和名词\n"
            "   - 角色设定（背景、能力）中已描述的内容\n"
            "   - 前文已出现过的角色、物品\n\n"
            "输出严格 JSON 格式（不要 markdown 包裹）：\n"
            "{\n"
            '  "has_unflagged_invention": true/false,\n'
            '  "invented_items": [\n'
            "    {\n"
            '      "name": "元素名称",\n'
            '      "type": "character" | "location" | "item" | "event" | "rule",\n'
            '      "evidence": "原文证据片段",\n'
            '      "already_flagged": true/false,\n'
            '      "is_blocking": true/false\n'
            "    }\n"
            "  ],\n"
            '  "detail": "总结"\n'
            "}"
        )

        client = await self._ai_service._build_client(db)
        try:
            result = str(await client.chat(
                messages=[
                    {"role": "system", "content": "你是一位严格的内容审计员。请严格区分'已有世界观设定'和'AI新发明'，已有世界观名词绝不算新发明。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            ))
            data = self._parse_anti_hallucination_llm_output(
                result, expect_list="invented_items"
            )
        finally:
            await client.close()

        items = data.get("invented_items", [])
        unflagged = [i for i in items if not i.get("already_flagged", False)]
        return {
            "law": "invention_must_be_flagged",
            "label": LAWS["invention_must_be_flagged"],
            "passed": len(unflagged) == 0,
            "invented_items": [i.get("name") for i in items],
            "unflagged": [i.get("name") for i in unflagged],
            "detail": (
                f"所有 {len(items)} 个新增元素均已标记"
                if len(unflagged) == 0
                else f"{len(unflagged)} 个新增元素未标记："\
                      f"{', '.join(i.get('name', '') for i in unflagged)}"
            ),
            "blocking": len(unflagged) > 0,
        }

    def _parse_anti_hallucination_llm_output(
        self,
        text: str,
        expect_list: str | None = None,
    ) -> dict[str, Any]:
        """解析反幻觉检查的 LLM JSON 输出。"""
        text = re.sub(r"```(?:json)?\s*", "", text)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {
                "has_deviation": True,
                "detail": "LLM 输出解析失败",
                "is_blocking": True,
                expect_list or "violations": [],
            }
        try:
            data = json.loads(match.group())
            return data
        except json.JSONDecodeError:
            return {
                "has_deviation": True,
                "detail": "JSON 解析失败",
                "is_blocking": True,
                expect_list or "violations": [],
            }
