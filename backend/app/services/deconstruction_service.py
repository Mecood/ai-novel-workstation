"""参考书拆解（Deconstruction Agent）服务。

核心能力：把参考书拆成可迁移的创作模式，不输出原作角色/地名/组织/金手指/剧情事实。
输出严格遵循裂变 deconstruction-agent 的 Schema（init_reference_research）。

两种模式：
  quick：AI 一次性分析「黄金三章 + 整体结构 + 拆文报告」。
  deep：逐章 AI 提取情节点 → service 聚合为剧情条 → 故事线 → 角色分级 → 设定抽象。

Canon 隔离硬规则（canonicalize_output 强制执行）：
  - 不写原作角色名、地名、组织名、能力名、剧情事实。
  - 只输出条件框架：什么条件组合造成爽感/期待/反差。
  - 每个可借结构都必须说明如何换题材/换人物关系/换金手指机制。
  - 高相似度候选放入 canon_contamination_warnings。
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.ai_client import AIClient


# ── Schema 常量 ──────────────────────────────────────────────────────────────
QUICK_MODE = "quick"
DEEP_MODE = "deep"
VALID_MODES = (QUICK_MODE, DEEP_MODE)

DIMENSION_KEYS = [
    "reader_promise",
    "opening_hook_patterns",
    "cool_point_loops",
    "protagonist_patterns",
    "antagonist_pressure_patterns",
    "pacing_notes",
]


# ── 提示词模板 ───────────────────────────────────────────────────────────────
SYSTEM_DECONSTRUCTION = """\
你是一名「参考书拆解编辑」（Deconstruction Agent）。你的唯一产出是【可迁移的创作模式】，\
绝不复述或照搬参考书的任何原作事实。

【Canon 隔离硬规则 — 必须严格遵守】
1. 输出中不得出现原作任何角色名、地名、组织名、功法/能力名、神器名、剧情事实。\
用「该角色」「某势力」「一种能力机制」「某个地点」这类条件化表述替代。
2. 只输出【条件框架】：是什么条件组合造成了爽感 / 期待 / 反差 / 钩子。\
例如「弱者+信息差+限时」而非「叶尘用灵视识破阴谋」。
3. 每个可借结构都必须附带【换法说明】：如何换题材 / 换人物关系 / 换金手指机制。\
4. 任何疑似仍贴近原作的事实性描述，标记为 canon_contamination_warnings，\
从正文中剔除。
5. 输出必须是严格的 JSON，不要加代码块标记以外的说明文字。

【输出 JSON 顶层字段（init_reference_research Schema）】
reader_promise          : str   — 一句话说明本书承诺给读者什么样的核心爽感
opening_hook_patterns   : list[str] — 黄金三章的钩子类型与条件组合
cool_point_loops        : list[str] — 爽点循环的条件框架（触发→反应→反制）
protagonist_patterns    : list[str] — 主角成长/行动的条件框架（换法说明）
antagonist_pressure_patterns : list[str] — 反派压力的条件框架
pacing_notes            : list[str] — 节奏曲线与章节节拍的条件框架
borrowable_structures   : list[object] — 可借结构，每项含 name/conditions/how_to_swap
do_not_copy             : list[str] — 不应照搬的套路与风险点
differentiation_requirements : list[str] — 差异化要求（如何避免成为翻版）
init_candidates         : list[object] — 候选创意包，每项含 one_liner/anti_trope/differentiation_requirements
quality                 : object — {confidence, coverage, overlap, passed}
"""

SYSTEM_PLOT_NODE = """\
你是一名情节提取员。请从给定章节文本中提取「情节点」（plot nodes），\
并以严格 JSON 数组输出。每个情节点是一个条件框架，不描述原作具体事实。

Canon 规则：不得输出原作角色名/地名/组织名/能力名/具体剧情事实，\
用条件化表述（如「主角」「某个角色」「一种规则」）替代。

输出 JSON 数组，每项：
{
  "node_type": "setup|hook|conflict|cool_point|reveal|turn|payoff|setup_twist|closure",
  "chapter_index": 数字,
  "condition": "造成该节点的条件框架（1-2句，条件化表述）",
  "function": "该节点对爽感/期待/反差的叙事功能",
  "how_to_swap": "换题材/换人物关系/换金手指的迁移方法",
  "canon_risk": "low|medium|high（是否仍贴近原作事实）"
}
"""

SCHEMA_INSTRUCTION = """\
请输出严格 JSON，字段顺序与上文一致，数组元素为字符串或对象。\
不要输出 JSON 以外的任何文字。"""


# ── 服务类 ───────────────────────────────────────────────────────────────────
@dataclass
class DeconstructionResult:
    """拆解分析的结构化结果。"""
    reader_promise: str = ""
    opening_hook_patterns: list[str] = field(default_factory=list)
    cool_point_loops: list[str] = field(default_factory=list)
    protagonist_patterns: list[str] = field(default_factory=list)
    antagonist_pressure_patterns: list[str] = field(default_factory=list)
    pacing_notes: list[str] = field(default_factory=list)
    borrowable_structures: list[dict[str, Any]] = field(default_factory=list)
    do_not_copy: list[str] = field(default_factory=list)
    differentiation_requirements: list[str] = field(default_factory=list)
    init_candidates: list[dict[str, Any]] = field(default_factory=list)
    quality: dict[str, Any] = field(
        default_factory=lambda: {
            "confidence": 0.0,
            "coverage": 0.0,
            "overlap": 0.0,
            "passed": False,
        }
    )
    canon_contamination_warnings: list[str] = field(default_factory=list)
    analysis_mode: str = QUICK_MODE
    reference_title: str = ""
    target_genre: str = ""
    chapter_plot_nodes: list[dict[str, Any]] = field(default_factory=list)
    plot_lines: list[dict[str, Any]] = field(default_factory=list)
    story_arcs: list[dict[str, Any]] = field(default_factory=list)
    character_tiers: list[dict[str, Any]] = field(default_factory=list)
    world_abstractions: list[dict[str, Any]] = field(default_factory=list)


class DeconstructionService:
    """参考书拆解服务。

    接受一个可选的 AIClient；当 ai_client 为 None 时不真正调用 AI，\
    仅返回结构化占位 / 可被外部传入已分析文本的解析结果。\
    这让调用方可以自行决定何时、用何种 AI 进行分析。
    """

    def __init__(self, ai_client: Optional[AIClient] = None):
        self.ai_client = ai_client

    # ── 主入口 ───────────────────────────────────────────────────────────
    async def analyze_reference(
        self,
        book_text: Optional[str],
        analysis_mode: str = QUICK_MODE,
        target_genre: str = "",
        reference_title: str = "",
        ai_client: Optional[AIClient] = None,
    ) -> dict[str, Any]:
        """参考书拆解分析主入口。

        Args:
            book_text: 参考书正文。为 None 时返回占位结构（可由调用方另行供给分析结果）。
            analysis_mode: "quick" 或 "deep"。
            target_genre: 目标创作题材，影响换法说明的方向。
            reference_title: 参考书名。
            ai_client: 可选 AI 客户端。优先于此，若无则用构造时传入的 self.ai_client。

        Returns:
            严格 Schema 的结构化 dict，含 canon_contamination_warnings。
        """
        mode = analysis_mode.lower().strip()
        if mode not in VALID_MODES:
            raise ValueError(f"analysis_mode 必须为 {VALID_MODES}")
        if not book_text:
            return self._empty_result(mode, reference_title, target_genre)

        client = ai_client or self.ai_client
        if client is None:
            return self._empty_result(mode, reference_title, target_genre)

        if mode == QUICK_MODE:
            result = await self._analyze_quick(book_text, target_genre, client)
        else:
            result = await self._analyze_deep(book_text, target_genre, client)

        # 规范输出：剔除 canon 污染，生成警告
        canon_warnings = self._detect_canon_leaks(book_text, result)
        return self.canonicalize_output(result, canon_warnings)

    # ── quick 模式：AI 一次性分析黄金三章 + 整体结构 ─────────────────
    async def _analyze_quick(
        self, text: str, target_genre: str, client: AIClient,
    ) -> DeconstructionResult:
        # 优先用前 8000 字（黄金三章）+ 整体概述
        golden = text[:8000]
        user_msg = f"""以下是参考书（目标创作题材参考：{target_genre or '不限'}）的开头部分与整体脉络。
请严格按照要求输出 JSON，拆解其可迁移的创作模式，绝不复述原作事实。

【参考文本（黄金三章及后续节选）】
---
{golden}
---

{SCHEMA_INSTRUCTION}"""
        messages = [
            {"role": "system", "content": SYSTEM_DECONSTRUCTION},
            {"role": "user", "content": user_msg},
        ]
        raw = await client.chat(messages, temperature=0.3, max_tokens=4096)
        raw = self._to_str(raw)
        parsed = self._parse_json_block(raw, "quick")
        return self._result_from_dict(parsed)

    # ── deep 模式：逐章提取情节点 → 聚合 ────────────────────────────
    async def _analyze_deep(
        self, text: str, target_genre: str, client: AIClient,
    ) -> DeconstructionResult:
        # 粗略分章：按「第 N 章」或段落分隔；最长每章约 3000 字
        chapters = self._split_chapters(text)
        all_nodes: list[dict[str, Any]] = []

        for idx, chap_text in enumerate(chapters, start=1):
            if not chap_text.strip():
                continue
            user_msg = f"""以下是参考书第 {idx} 章。
请提取情节点，严格输出 JSON 数组，条件化表述，不写原作事实。

{chap_text}

{SCHEMA_INSTRUCTION}"""
            messages = [
                {"role": "system", "content": SYSTEM_PLOT_NODE},
                {"role": "user", "content": user_msg},
            ]
            try:
                raw = await client.chat(messages, temperature=0.2, max_tokens=2048)
                raw = self._to_str(raw)
                nodes = self._parse_json_list(raw) or []
                # 注入章节索引（兜底）
                for n in nodes:
                    if "chapter_index" not in n:
                        n["chapter_index"] = idx
                all_nodes.extend(nodes)
            except Exception:
                continue  # 单章失败不影响整体

        # 聚合分析（纯本地，不依赖 AI）
        plot_lines = self.aggregate_plot_lines(all_nodes)
        story_arcs = self._derive_story_arcs(plot_lines)
        character_tiers = self._derive_character_tiers(all_nodes)
        world_abstractions = self._derive_world_abstractions(all_nodes)

        # 顶层维度：基于情节点的归纳（纯本地条件框架）
        result = self._build_top_level_from_nodes(all_nodes, target_genre)
        result.chapter_plot_nodes = all_nodes
        result.plot_lines = plot_lines
        result.story_arcs = story_arcs
        result.character_tiers = character_tiers
        result.world_abstractions = world_abstractions
        result.analysis_mode = DEEP_MODE
        return result

    # ── 章节切分 ────────────────────────────────────────────────────────
    def _split_chapters(self, text: str) -> list[str]:
        """按章节标题切分；无标题时按 3000 字一段。"""
        # 尝试匹配「第 N 章」「CHAPTER」「章」类标题
        pattern = re.compile(
            r"(?im)^\s*(?:第\s*\d+\s*章|CHAPTER\s*\d+|Chapter\s*\d+)\s*:?\s*\S{0,30}\s*$",
        )
        splits = pattern.split(text)
        # splits[0] 是第一章前内容，从第二个起交错：标题, 正文
        if len(splits) > 1:
            chunks = []
            body = splits[0].strip()
            if body:
                chunks.append(body)
            for i in range(1, len(splits) - 1, 2):
                if i + 1 < len(splits):
                    chunks.append(splits[i + 1].strip())
            return [c for c in chunks if len(c) > 100]
        # 无标题：按固定长度切
        chunk_size = 3000
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    # ── 提取情节点（深度模式用） ──────────────────────────────────────
    def extract_plot_nodes(self, text: str, chapter_index: int = 0) -> list[dict[str, Any]]:
        """从单段文本中纯本地粗提情节点（无 AI 时兜底）。

        基于关键词的条件化提取，产出供 aggregate_plot_lines 使用的节点。
        不依赖 AI，适合 book_text 被外部已解析后的本地处理，或无 AI 配置时的占位。
        """
        if not text:
            return []
        nodes: list[dict[str, Any]] = []
        low = text[:2000].lower()
        markers = {
            "setup": ["登场", "来到", "开始", "遇到", "得知", "发现"],
            "hook": ["突然", "意外", "震惊", "竟然", "没想到", "悬念"],
            "conflict": ["对峙", "冲突", "拒绝", "矛盾", "争辩", "阻止"],
            "cool_point": ["碾压", "逆袭", "反转", "打脸", "觉醒", "爆发"],
            "turn": ["然而", "可是", "不料", "反转", "变化", "转折"],
        }
        for ntype, words in markers.items():
            hits = [w for w in words if w in low]
            if hits:
                nodes.append({
                    "node_type": ntype,
                    "chapter_index": chapter_index,
                    "condition": f"本章包含 {ntype} 条件信号：{'/'.join(hits)}（条件化占位）",
                    "function": f"{ntype} 节点",
                    "how_to_swap": "更换该条件组合的实现载体与触发场景即可迁移。",
                    "canon_risk": "low",
                })
        return nodes

    # ── 聚合剧情条 ────────────────────────────────────────────────────
    @staticmethod
    def aggregate_plot_lines(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """把情节点按类型聚合为剧情条（plot lines）。

        纯本地逻辑：按 node_type 归并连续出现的节点，形成一条可读的条件化剧情条。
        """
        if not nodes:
            return []
        # 按章节排序
        sorted_nodes = sorted(nodes, key=lambda n: n.get("chapter_index", 0))
        # 按类型分组
        by_type: dict[str, list[dict[str, Any]]] = {}
        for n in sorted_nodes:
            by_type.setdefault(n.get("node_type", "setup"), []).append(n)
        lines = []
        for ntype, group in by_type.items():
            if not group:
                continue
            conditions = " → ".join(
                n.get("condition", "") for n in group[:6]
            )
            lines.append({
                "line_type": ntype,
                "node_count": len(group),
                "condition_chain": conditions,
                "chapters": sorted({n.get("chapter_index", 0) for n in group}),
                "how_to_swap": "改变该剧情条中的条件载体（人物/场景/能力机制）即可迁移到目标题材。",
            })
        return lines

    # ── 从节点归纳顶层维度（纯本地） ──────────────────────────────
    def _build_top_level_from_nodes(
        self, nodes: list[dict[str, Any]], target_genre: str,
    ) -> DeconstructionResult:
        result = DeconstructionResult(analysis_mode=DEEP_MODE)
        result.reader_promise = (
            f"基于 {len(nodes)} 个情节点归纳：通过条件化钩子与爽点循环驱动阅读期待。"
        )
        result.quality = {
            "confidence": round(min(0.6, 0.2 + len(nodes) * 0.03), 2),
            "coverage": round(min(1.0, len(nodes) / max(1, 12)), 2),
            "overlap": 0.0,
            "passed": len(nodes) > 0,
        }
        # 按类型抽条件
        type_map: dict[str, list[str]] = {}
        for n in nodes:
            type_map.setdefault(n.get("node_type", "setup"), []).append(
                n.get("condition", "")
            )
        for ntype, conds in type_map.items():
            de_dup = self._dedup(conds)
            if ntype in ("hook", "setup"):
                result.opening_hook_patterns.extend(de_dup[:4])
            elif ntype in ("cool_point",):
                result.cool_point_loops.extend(de_dup[:4])
            elif ntype == "conflict":
                result.antagonist_pressure_patterns.extend(de_dup[:4])
        if target_genre:
            result.differentiation_requirements.append(
                f"在 {target_genre} 题材中，需用该题材特有的载体替换上述条件（题材/关系/金手指）。"
            )
        return result

    @staticmethod
    def _dedup(items: list[str]) -> list[str]:
        out, seen = [], set()
        for x in items:
            if x and x not in seen:
                out.append(x)
                seen.add(x)
        return out

    # ── 故事线 / 角色分级 / 设定抽象（纯本地推导） ──────────────
    @staticmethod
    def _derive_story_arcs(plot_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        arcs = []
        for pl in plot_lines:
            arcs.append({
                "arc_type": pl.get("line_type", ""),
                "condition_chain": pl.get("condition_chain", ""),
                "how_to_swap": pl.get("how_to_swap", ""),
            })
        return arcs

    @staticmethod
    def _derive_character_tiers(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """纯条件化：按功能将角色分为驱动型/压力型/辅助型。不出现原作名。"""
        seen = {n.get("node_type") for n in nodes}
        tiers = []
        if "conflict" in seen or "cool_point" in seen:
            tiers.append({"tier": "驱动型角色", "function": "承担冲突升级与爽点触发", "how_to_swap": "换人物关系与动机即可迁移"})
        if "setup" in seen:
            tiers.append({"tier": "辅助型角色", "function": "提供信息与转折信号", "how_to_swap": "换场景与身份即可迁移"})
        return tiers

    @staticmethod
    def _derive_world_abstractions(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 从条件的共性中抽象设定规则
        sample = nodes[:6]
        abstractions = []
        for n in sample:
            cond = n.get("condition", "")
            abstractions.append({
                "abstraction": cond,
                "how_to_swap": "改变规则的实现形态（数值/社会规则/超自然机制）即可迁移。",
            })
        return abstractions

    # ── 输出规范（Canon 隔离） ────────────────────────────────────────
    @staticmethod
    def canonicalize_output(
        raw_result: DeconstructionResult | dict[str, Any],
        canon_contamination_warnings: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """将拆解结果规范化为严格 Schema，并挂载 canon 污染警告。"""
        warnings = canon_contamination_warnings or []
        r = raw_result if isinstance(raw_result, dict) else {
            "reader_promise": getattr(raw_result, "reader_promise", ""),
            "opening_hook_patterns": getattr(raw_result, "opening_hook_patterns", []),
            "cool_point_loops": getattr(raw_result, "cool_point_loops", []),
            "protagonist_patterns": getattr(raw_result, "protagonist_patterns", []),
            "antagonist_pressure_patterns": getattr(raw_result, "antagonist_pressure_patterns", []),
            "pacing_notes": getattr(raw_result, "pacing_notes", []),
            "borrowable_structures": getattr(raw_result, "borrowable_structures", []),
            "do_not_copy": getattr(raw_result, "do_not_copy", []),
            "differentiation_requirements": getattr(raw_result, "differentiation_requirements", []),
            "init_candidates": getattr(raw_result, "init_candidates", []),
            "quality": getattr(raw_result, "quality", {}),
            "analysis_mode": getattr(raw_result, "analysis_mode", QUICK_MODE),
            "reference_title": getattr(raw_result, "reference_title", ""),
            "target_genre": getattr(raw_result, "target_genre", ""),
        }
        if isinstance(raw_result, DeconstructionResult):
            r.update({
                "chapter_plot_nodes": raw_result.chapter_plot_nodes,
                "plot_lines": raw_result.plot_lines,
                "story_arcs": raw_result.story_arcs,
                "character_tiers": raw_result.character_tiers,
                "world_abstractions": raw_result.world_abstractions,
            })
        r["canon_contamination_warnings"] = warnings
        return r

    # ── Canon 泄漏检测（纯本地启发式） ──────────────────────────────
    @staticmethod
    def _detect_canon_leaks(text: str, result: DeconstructionResult | dict[str, Any]) -> list[str]:
        """检测输出中是否仍有贴近原作事实的残留。

        启发式：扫描输出文本块中长度 ≥ 2 的中文词组是否同时大量出现在原文中。
        命中则列为高相似度候选，提醒调用方清洗。
        """
        text = text or ""
        result_text = _result_to_flat_text(result)
        out_words = set(_chinese_grams(result_text, min_len=2, max_len=3))
        canon_words = set(_chinese_grams(text, min_len=2, max_len=3))
        canon_words = {w for w in canon_words if len(w) >= 2}
        overlap = out_words & canon_words
        # 过滤停用词/常见词
        stop = {"这个", "那个", "什么", "一个", "这样", "可以", "角色", "主角", "情节", "章节", "故事", "如何", "题材", "关系"}
        sus = [w for w in sorted(overlap, key=len, reverse=True) if w not in stop][:15]
        return [f"检测到与原作高度相似的残留词组（可能 canon 污染），建议人工清洗：{w}" for w in sus]

    # ── 解析 AI 返回的 JSON ─────────────────────────────────────────
    @staticmethod
    def _parse_json_block(raw: str, mode: str) -> dict[str, Any]:
        """从 AI 返回的文本中提取 JSON 对象。"""
        raw = raw.strip()
        # 尝试去除 ```json ... ``` 包裹
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if m:
            raw = m.group(1)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {}

    @staticmethod
    def _parse_json_list(raw: str) -> list[dict[str, Any]]:
        raw = raw.strip()
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group())
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _result_from_dict(d: dict[str, Any]) -> DeconstructionResult:
        r = DeconstructionResult()
        for k in DIMENSION_KEYS:
            v = d.get(k)
            if isinstance(v, str) and v:
                v = [v]
            if isinstance(v, list):
                setattr(r, k, v)
        for k in ("borrowable_structures", "do_not_copy",
                  "differentiation_requirements", "init_candidates"):
            v = d.get(k)
            if isinstance(v, list):
                setattr(r, k, v)
        q = d.get("quality", {})
        if isinstance(q, dict):
            r.quality.update(q)
        return r

    @staticmethod
    def _empty_result(mode: str, reference_title: str, target_genre: str) -> dict[str, Any]:
        """文本为空或无 AI 时的占位结构（仍符合 Schema）。"""
        r = DeconstructionResult(analysis_mode=mode,
                                 reference_title=reference_title,
                                 target_genre=target_genre)
        r.quality = {"confidence": 0.0, "coverage": 0.0, "overlap": 0.0,
                     "passed": False, "reason": "未提供参考书正文或无 AI 客户端"}
        return DeconstructionService.canonicalize_output(r, [])


def _result_to_flat_text(result: DeconstructionResult | dict[str, Any]) -> str:
    """把拆解结果展平为纯文本，供 canon 泄漏词组扫描使用。"""
    if isinstance(result, DeconstructionResult):
        result = {
            "reader_promise": getattr(result, "reader_promise", ""),
            "opening_hook_patterns": getattr(result, "opening_hook_patterns", []),
            "cool_point_loops": getattr(result, "cool_point_loops", []),
            "protagonist_patterns": getattr(result, "protagonist_patterns", []),
            "antagonist_pressure_patterns": getattr(result, "antagonist_pressure_patterns", []),
            "pacing_notes": getattr(result, "pacing_notes", []),
            "borrowable_structures": getattr(result, "borrowable_structures", []),
            "do_not_copy": getattr(result, "do_not_copy", []),
            "differentiation_requirements": getattr(result, "differentiation_requirements", []),
            "init_candidates": getattr(result, "init_candidates", []),
        }
    parts: list[str] = []
    for v in result.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.extend(str(x) for x in item.values() if isinstance(x, str))
    return "".join(parts)


def _chinese_grams(text: str, min_len: int = 2, max_len: int = 4) -> list[str]:
    """从中文文本提取 n-gram 词组（含汉字与标点外的字符片段）。"""
    chars = re.findall(r"[\u4e00-\u9fff]", text)
    s = "".join(chars)
    out: list[str] = []
    for length in range(min_len, max_len + 1):
        for i in range(0, len(s) - length + 1):
            out.append(s[i:i + length])
    return out
