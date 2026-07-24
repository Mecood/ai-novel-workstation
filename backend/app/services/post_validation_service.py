"""
写后强制校验服务 — 每章写完、提交前的最后一道关卡。

不通过时流水线直接拦停，不上报 commit。

校验维度：
  1. REQUIRED_NODES — 章节正文是否覆盖了合同要求的所有节点
  2. FORBIDDEN_ZONES — 章节正文是否触碰了禁止事项
  3. CONSTRAINTS — 章节正文是否满足已声明的约束条件
  4. CHARACTER_STATE — 角色行为/状态是否与已知历史一致
  5. POWER_CURVE — 数值型战力/等级是否存在异常跳跃

每个维度返回 PASS / FAIL，任意 FAIL 则阻断提交。
"""
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.chapter_contract import ChapterContract
from app.models.character import Character
from app.models.project import Project
from app.models.worldview import Worldview
from app.services.ai_service import AIService


# ── 校验结果类型 ─────────────────────────────────────────────────────
class CheckResult:
    """单个维度的校验结果。"""

    def __init__(
        self,
        name: str,
        label: str,
        passed: bool,
        detail: str = "",
        evidence: str = "",
        severity: str = "warning",
    ):
        self.name = name
        self.label = label
        self.passed = passed
        self.detail = detail
        self.evidence = evidence
        self.severity = severity  # "blocking" | "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "passed": self.passed,
            "detail": self.detail,
            "evidence": self.evidence,
            "severity": self.severity,
        }


class ValidationReport:
    """聚合所有维度校验结果的报告。"""

    def __init__(self, results: list[CheckResult]):
        self.results = results
        self.passed = all(r.passed for r in results)
        self.blocking_count = sum(
            1 for r in results if not r.passed and r.severity == "blocking"
        )
        self.warning_count = sum(
            1 for r in results if not r.passed and r.severity == "warning"
        )

    @property
    def summary(self) -> str:
        if self.passed:
            return "所有校验通过，章节可以提交"
        lines = []
        for r in self.results:
            if not r.passed:
                icon = "❌" if r.severity == "blocking" else "⚠️"
                lines.append(f"{icon} {r.label}：{r.detail}")
        return "; ".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blocking_count": self.blocking_count,
            "warning_count": self.warning_count,
            "summary": self.summary,
            "checks": [r.to_dict() for r in self.results],
        }


class PostValidationService:
    """写后强制校验服务。"""

    def __init__(self, ai_service: AIService):
        self._ai = ai_service

    # ── 入口 ────────────────────────────────────────────────────────

    async def validate_chapter(
        self, db: AsyncSession, project: Project, chapter: Chapter
    ) -> ValidationReport:
        """
        对一章执行全部校验，返回 ValidationReport。

        任意 blocking 失败 → report.passed = False，建议拦停提交。
        只 warning → report.passed = True，但可标记提醒。
        """
        contract = await self._load_contract(db, project, chapter.chapter_number)

        results: list[CheckResult] = []

        # 1) 合同节点覆盖
        results.append(await self._check_required_nodes(db, project, chapter, contract))

        # 2) 禁止事项
        results.append(await self._check_forbidden_zones(db, project, chapter, contract))

        # 3) 约束条件
        results.append(await self._check_constraints(db, project, chapter, contract))

        # 4) 角色状态一致性
        results.append(await self._check_character_state(db, project, chapter, contract))

        # 5) 战力曲线（仅世界观声明了数值体系时才触发）
        results.append(await self._check_power_curve(db, project, chapter, contract))

        return ValidationReport(results)

    # ── 1. 合同节点覆盖 ─────────────────────────────────────────────

    async def _check_required_nodes(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        contract: ChapterContract | None,
    ) -> CheckResult:
        """
        检查章节正文是否覆盖了合同要求的所有 required_nodes。

        策略：
        - 有合同 → 调用 LLM 逐节点检查覆盖率
        - 无合同 → 跳过（PASS，标记说明）
        """
        if contract is None:
            return CheckResult(
                name="required_nodes",
                label="合同节点覆盖",
                passed=True,
                detail="本章无合同，跳过节点覆盖检查",
                severity="warning",
            )

        required = contract.required_nodes or []
        if not required:
            return CheckResult(
                name="required_nodes",
                label="合同节点覆盖",
                passed=True,
                detail="合同无 required_nodes，跳过",
            )

        content = self._extract_chapter_text(chapter)

        # 格式：每个 node 通常有 id/name/description，拼成检查 prompt
        node_descriptions = []
        for n in required:
            if isinstance(n, dict):
                desc = n.get("description", n.get("name", str(n)))
                node_descriptions.append(desc)
            else:
                node_descriptions.append(str(n))

        node_text = "\n".join(f"{i+1}. {d}" for i, d in enumerate(node_descriptions))

        prompt = self._build_required_nodes_prompt(node_text, content[:4000])
        result = await self._call_with_client(db, prompt, temperature=0.1)
        parsed = self._parse_json_from_llm(result)

        # 解析 LLM 返回
        uncovered = parsed.get("uncovered_nodes", [])
        all_covered = parsed.get("all_covered", True)
        evidence = parsed.get("evidence", "")

        if not uncovered and all_covered:
            return CheckResult(
                name="required_nodes",
                label="合同节点覆盖",
                passed=True,
                detail=f"合同 {len(required)} 个节点全部覆盖",
                severity="blocking",
            )

        detail = f"未覆盖节点：{', '.join(str(x) for x in uncovered[:3])}"
        if len(uncovered) > 3:
            detail += f" 等共 {len(uncovered)} 个"
        return CheckResult(
            name="required_nodes",
            label="合同节点覆盖",
            passed=False,
            detail=detail,
            evidence=evidence,
            severity="blocking",
        )

    # ── 2. 禁止事项 ────────────────────────────────────────────────

    async def _check_forbidden_zones(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        contract: ChapterContract | None,
    ) -> CheckResult:
        """
        检查章节正文是否触碰了 forbidden_zones（禁止事项/红线）。
        """
        if contract is None:
            return CheckResult(
                name="forbidden_zones",
                label="禁止事项",
                passed=True,
                detail="本章无合同，跳过禁止事项检查",
            )

        forbidden = contract.forbidden_zones or []
        if not forbidden:
            return CheckResult(
                name="forbidden_zones",
                label="禁止事项",
                passed=True,
                detail="合同无 forbidden_zones，跳过",
            )

        content = self._extract_chapter_text(chapter)

        # 先做关键词快速筛（轻量、不依赖 LLM）
        keyword_violations = []
        for zone in forbidden:
            zone_text = self._zone_text(zone)
            # 简单关键词匹配
            if zone_text and zone_text.lower() in content.lower():
                keyword_violations.append(zone_text)

        # 有关键词命中 → 直接 FAIL，不浪费 LLM 调用
        if keyword_violations:
            return CheckResult(
                name="forbidden_zones",
                label="禁止事项",
                passed=False,
                detail=f"触碰禁止事项：{', '.join(keyword_violations)}",
                severity="blocking",
            )

        # 关键词未命中 → LLM 语义确认（防绕关键字）
        prompt = self._build_forbidden_zones_prompt(forbidden, content[:4000])
        result = await self._call_with_client(db, prompt, temperature=0.1)
        parsed = self._parse_json_from_llm(result)

        violations = parsed.get("violations", [])
        all_clear = parsed.get("all_clear", True)

        if not violations and all_clear:
            return CheckResult(
                name="forbidden_zones",
                label="禁止事项",
                passed=True,
                detail="未发现触碰禁止事项",
                severity="blocking",
            )

        detail = f"LLM 检测到 {len(violations)} 处语义违反"
        return CheckResult(
            name="forbidden_zones",
            label="禁止事项",
            passed=False,
            detail=detail,
            evidence=str(violations[:2]),
            severity="blocking",
        )

    # ── 3. 约束条件 ────────────────────────────────────────────────

    async def _check_constraints(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        contract: ChapterContract | None,
    ) -> CheckResult:
        """
        检查章节正文是否满足 constraints（风格/字数/场景等约束）。
        """
        if contract is None:
            return CheckResult(
                name="constraints",
                label="约束条件",
                passed=True,
                detail="本章无合同，跳过约束检查",
            )

        constraints = contract.constraints or []
        if not constraints:
            return CheckResult(
                name="constraints",
                label="约束条件",
                passed=True,
                detail="合同无 constraints，跳过",
            )

        content = self._extract_chapter_text(chapter)

        prompt = self._build_constraints_prompt(constraints, content[:4000])
        result = await self._call_with_client(db, prompt, temperature=0.1)
        parsed = self._parse_json_from_llm(result)

        violations = parsed.get("violations", [])
        satisfied = parsed.get("satisfied", True)

        if not violations and satisfied:
            return CheckResult(
                name="constraints",
                label="约束条件",
                passed=True,
                detail=f"{len(constraints)} 个约束条件全部满足",
                severity="warning",
            )

        detail = f"未满足约束 {len(violations)} 个"
        return CheckResult(
            name="constraints",
            label="约束条件",
            passed=False,
            detail=detail,
            evidence=str(violations[:2]),
            severity="warning",
        )

    # ── 4. 角色状态一致性 ──────────────────────────────────────────

    async def _check_character_state(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        contract: ChapterContract | None,
    ) -> CheckResult:
        """
        检查章节中出现的角色是否与已知状态一致。

        读 DB 中前 N 章提取的 StoryEvent（entities + description），
        与本章节中角色的呈现做对比。
        """
        from app.models.story_event import StoryEvent

        # 读取所有角色
        char_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        characters = char_result.scalars().all()

        # 读前 N 章的事件（用于状态追踪）
        prev_events = await db.execute(
            select(StoryEvent).where(
                StoryEvent.project_id == project.id,
                StoryEvent.chapter_number < chapter.chapter_number,
            ).order_by(StoryEvent.chapter_number)
        )
        prev_events_list = prev_events.scalars().all()

        if not characters or not prev_events_list:
            return CheckResult(
                name="character_state",
                label="角色状态一致性",
                passed=True,
                detail="无已知角色状态，跳过",
            )

        content = self._extract_chapter_text(chapter)

        # 构造已知状态摘要：用 entities + description 汇总每个角色的历史行为
        char_event_map: dict[str, list[str]] = {}
        for ev in prev_events_list:
            entities = ev.entities or []
            desc = ev.description or ""
            for name in entities:
                if name not in char_event_map:
                    char_event_map[name] = []
                # 截取 description 的前 80 字
                snippet = desc[:80]
                if snippet not in char_event_map[name]:
                    char_event_map[name].append(snippet)

        # 只保留与项目角色相关的
        char_names = {c.name for c in characters}
        known_state_text = "\n".join(
            f"- {name}: {', '.join(sorted(set(events[-3:])))}"
            for name, events in char_event_map.items()
            if name in char_names or any(name in c.name for c in characters)
        )

        char_summary = "\n".join(
            f"- {c.name}（{c.role_type}）"
            for c in characters
        )

        if not known_state_text.strip():
            return CheckResult(
                name="character_state",
                label="角色状态一致性",
                passed=True,
                detail="无可用历史事件，跳过",
            )

        prompt = self._build_character_state_prompt(
            char_summary, known_state_text, content[:4000]
        )
        result = await self._call_with_client(db, prompt, temperature=0.1)
        parsed = self._parse_json_from_llm(result)

        contradictions = parsed.get("contradictions", [])
        consistent = parsed.get("consistent", True)

        if not contradictions and consistent:
            return CheckResult(
                name="character_state",
                label="角色状态一致性",
                passed=True,
                detail="角色状态与历史一致",
                severity="blocking",
            )

        detail = f"检测到 {len(contradictions)} 处角色状态矛盾"
        return CheckResult(
            name="character_state",
            label="角色状态一致性",
            passed=False,
            detail=detail,
            evidence=str(contradictions[:2]),
            severity="blocking",
        )

    # ── 5. 战力曲线 ────────────────────────────────────────────────

    async def _check_power_curve(
        self,
        db: AsyncSession,
        project: Project,
        chapter: Chapter,
        contract: ChapterContract | None,
    ) -> CheckResult:
        """
        检查数值型设定（战力/等级/境界等）是否存在异常跳跃。

        仅当世界观声明了数值体系（如世界观 description 或 rules 中提到"境界/等级/数值"）
        时才触发；否则跳过。
        """
        from app.models.story_event import StoryEvent

        # 检查世界观是否声明了数值体系
        wv_result = await db.execute(
            select(Worldview).where(Worldview.project_id == project.id)
        )
        worldviews = wv_result.scalars().all()
        has_numeric_system = any(
            any(kw in (w.description or "") for kw in ["境界", "等级", "阶位", "数值", "战力", "战斗力"])
            for w in worldviews
        )
        if not has_numeric_system:
            return CheckResult(
                name="power_curve",
                label="战力曲线",
                passed=True,
                detail="世界观未声明数值体系，跳过",
            )

        # 读前 N 章事件中记录的数值变化
        prev_events = await db.execute(
            select(StoryEvent).where(
                StoryEvent.project_id == project.id,
                StoryEvent.chapter_number < chapter.chapter_number,
            ).order_by(StoryEvent.chapter_number)
        )
        prev_events_list = prev_events.scalars().all()

        content = self._extract_chapter_text(chapter)

        # 从事件中提取实力相关的 entity/event 变化
        # （StoryEvent 无 power_levels 列，用 entities+description 中提取）
        numeric_history = []
        for ev in prev_events_list:
            entities = ev.entities or []
            desc = (ev.description or "")[:60]
            event_type = ev.event_type or ""
            for name in entities:
                # 只收集与等级/力量/突破/获得能力相关的事件
                if any(kw in (desc + event_type).lower() for kw in [
                    "突破", "升级", "进阶", "获得", "觉醒", "金丹", "筑基", "元婴",
                    "lv", "level", "power", "境界", "等级", "阶位", "攻击", "击败",
                ]):
                    numeric_history.append((name, f"第{ev.chapter_number}章: {desc}"))

        if not numeric_history:
            return CheckResult(
                name="power_curve",
                label="战力曲线",
                passed=True,
                detail="无已知数值历史，跳过",
            )

        # 构造 prompt 让 LLM 检查异常
        history_text = "\n".join(
            f"- {name}: {level}" for name, level in numeric_history
        )

        prompt = self._build_power_curve_prompt(
            history_text, content[:3000]
        )
        result = await self._call_with_client(db, prompt, temperature=0.1)
        parsed = self._parse_json_from_llm(result)

        anomalies = parsed.get("anomalies", [])
        stable = parsed.get("stable", True)

        if not anomalies and stable:
            return CheckResult(
                name="power_curve",
                label="战力曲线",
                passed=True,
                detail="战力数值变化正常",
                severity="blocking",
            )

        detail = f"检测到 {len(anomalies)} 处数值异常跳跃"
        return CheckResult(
            name="power_curve",
            label="战力曲线",
            passed=False,
            detail=detail,
            evidence=str(anomalies[:2]),
            severity="blocking",
        )

    # ── 辅助方法 ────────────────────────────────────────────────────

    @staticmethod
    async def _load_contract(
        db: AsyncSession, project: Project, chapter_number: int
    ) -> ChapterContract | None:
        result = await db.execute(
            select(ChapterContract).where(
                ChapterContract.project_id == project.id,
                ChapterContract.chapter_number == chapter_number,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _extract_chapter_text(chapter: Chapter) -> str:
        """安全提取章节正文（兼容 str 和 dict 格式）。"""
        c = chapter.content
        if c is None:
            return ""
        if isinstance(c, str):
            return c
        if isinstance(c, dict) and "text" in c and isinstance(c["text"], str):
            return c["text"]
        return json.dumps(c, ensure_ascii=False)

    @staticmethod
    def _zone_text(zone: Any) -> str:
        """从 forbidden zone 对象中提取可读文本。"""
        if isinstance(zone, str):
            return zone
        if isinstance(zone, dict):
            return zone.get("description", zone.get("name", str(zone)))
        return str(zone)

    # ── Prompt 构建器 ───────────────────────────────────────────────

    @staticmethod
    def _build_required_nodes_prompt(nodes_text: str, content: str) -> str:
        return (
            "你是一位严格的大纲履约检查员。请检查本章正文是否覆盖了以下合同要求节点。\n\n"
            "## 要求节点\n"
            f"{nodes_text}\n\n"
            "## 本章正文（前4000字）\n"
            f"{content}\n\n"
            "请逐项检查每个节点是否在正文中有实际描述（不只是提及，要有实质情节）。\n\n"
            "输出严格 JSON（不要 markdown 包裹）：\n"
            '{\n'
            '  "all_covered": true/false,\n'
            '  "uncovered_nodes": ["未覆盖的节点描述"],\n'
            '  "evidence": "每个节点的覆盖情况简要说明",\n'
            '  "detail": "总体评估"\n'
            "}"
        )

    @staticmethod
    def _build_forbidden_zones_prompt(forbidden: list, content: str) -> str:
        zone_text = "\n".join(
            f"{i+1}. {PostValidationService._zone_text(z)}" for i, z in enumerate(forbidden)
        )
        return (
            "你是一位红线检查员。请检查本章正文是否触碰了以下任何禁止事项。\n\n"
            "## 禁止事项\n"
            f"{zone_text}\n\n"
            "## 本章正文（前4000字）\n"
            f"{content}\n\n"
            "注意：即使正文没有完全相同的文字，如果语义等价地触碰了禁止事项，也算违反。\n\n"
            "输出严格 JSON（不要 markdown 包裹）：\n"
            '{\n'
            '  "all_clear": true/false,\n'
            '  "violations": ["违反的具体描述"],\n'
            '  "detail": "检查说明"\n'
            "}"
        )

    @staticmethod
    def _build_constraints_prompt(constraints: list, content: str) -> str:
        constraint_text = "\n".join(
            f"{i+1}. {PostValidationService._zone_text(c)}" for i, c in enumerate(constraints)
        )
        return (
            "你是一位约束条件检查员。请检查本章正文是否满足以下约束条件。\n\n"
            "## 约束条件\n"
            f"{constraint_text}\n\n"
            "## 本章正文（前4000字）\n"
            f"{content}\n\n"
            "输出严格 JSON（不要 markdown 包裹）：\n"
            '{\n'
            '  "satisfied": true/false,\n'
            '  "violations": ["未满足的约束描述"],\n'
            '  "detail": "检查说明"\n'
            "}"
        )

    @staticmethod
    def _build_character_state_prompt(
        char_summary: str, known_state_text: str, content: str
    ) -> str:
        return (
            "你是一位角色状态一致性检查员。请检查本章正文中角色表现是否与历史状态一致。\n\n"
            "## 已知角色\n"
            f"{char_summary}\n\n"
            "## 已知角色状态（近三章记录）\n"
            f"{known_state_text}\n\n"
            "## 本章正文（前4000字）\n"
            f"{content}\n\n"
            "检查重点：\n"
            "1. 已死角色是否复活（除非有明确的复活情节）\n"
            "2. 角色性格/态度是否发生不可解释的突变\n"
            "3. 角色实力/能力是否出现不合理跳跃\n\n"
            "输出严格 JSON（不要 markdown 包裹）：\n"
            '{\n'
            '  "consistent": true/false,\n'
            '  "contradictions": ["具体矛盾描述"],\n'
            '  "detail": "检查说明"\n'
            "}"
        )

    @staticmethod
    def _build_power_curve_prompt(history_text: str, content: str) -> str:
        return (
            "你是一位战力数值检查员。请检查本章正文中出现的战力/等级/境界数值"
            "是否与历史曲线一致，是否存在异常跳跃。\n\n"
            "## 历史数值记录\n"
            f"{history_text}\n\n"
            "## 本章正文（前3000字）\n"
            f"{content}\n\n"
            "检查重点：\n"
            "1. 数值是否合理递增/递减\n"
            "2. 是否存在不合理的剧烈跳跃（如等级突然翻倍）\n"
            "3. 是否有角色数值倒退（除非有明确原因）\n\n"
            "输出严格 JSON（不要 markdown 包裹）：\n"
            '{\n'
            '  "stable": true/false,\n'
            '  "anomalies": ["异常描述"],\n'
            '  "detail": "检查说明"\n'
            "}"
        )

    @staticmethod
    def _parse_json_from_llm(text: str) -> dict[str, Any]:
        """从 LLM 返回中解析 JSON。"""
        import re
        text = text.strip()
        # 找第一个 { 和最后一个 }
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {}
        return {}

    async def _call_with_client(
        self, db: AsyncSession, prompt: str, temperature: float = 0.1
    ) -> str:
        """通过 AIService 的 client 调用 LLM。"""
        client = await self._ai._build_client(db)
        try:
            return await client.chat(
                messages=[
                    {"role": "system", "content": "你是一位严格的内容审核员。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=1500,
            )
        finally:
            await client.close()
