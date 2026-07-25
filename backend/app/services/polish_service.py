"""
Polish service — 审查后润色四步：定点修复 → 风格适配 → 排版 → AI味终检。

对应裂变创作 6 步流水线 Step 4（润色），填补工作站 auto_pipeline
"review → extraction → debt → commit" 中间缺的「审完改」环节。

输入：review_result（ReviewService 产出）+ 正文
输出：polished_content（润色后正文）+ polish_report（各步骤变更摘要）

四步流程：
  1) _fix_issues — 根据 review 的 blocking/high issues 做定点修复
  2) _apply_style  — 注入风格适配（从 genre_weighted_style / style_guidance）
  3) _typeset      — 排版优化：段落拆分、标点、对话格式
  4) _anti_ai_final — de_ai_rewrite 终检
"""
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import AIService
from app.models.chapter import Chapter


@dataclass
class PolishResult:
    """单次润色的完整产出。"""
    polished_content: str
    report: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "polished_content": self.polished_content,
            "report": self.report,
        }


class PolishError(Exception):
    pass


# ── Step 1: 定点修复 prompt ──────────────────────────────────────
FIX_ISSUES_SYSTEM = """\
你是一位专业的小说编辑。下面是一份章节内容，以及审查员指出的问题列表。
你的任务是只修改有问题的地方，不改动没问题的内容。

原则：
1. 只针对 issue 中列出的问题做定点修改
2. 保持角色语气、世界观设定、情节走向完全不变
3. 每个修改处用具体的文字替换，不要用占位符
4. 如果某条 issue 的修复会破坏上下文，跳过该条并在 report 中标记 skipped
5. 输出纯文本正文，不要 JSON，不要解释，不要 markdown 包裹
"""

FIX_ISSUES_USER_TEMPLATE = """\
### 章节内容
{chapter_content}

### 需要修复的问题
{issues_text}

请只修改上述问题涉及的文字，其余内容保持原样。直接输出修改后的完整正文。
"""


# ── Step 2: 风格适配 prompt ──────────────────────────────────────
STYLE_ADAPT_SYSTEM = """\
你是一位资深小说编辑。请将以下章节内容做风格适配，让文风更自然、更像真人写作。

适配规则：
1. 删除 AI 高频八股词（不禁/仿佛/嘴角微微上扬/眼中闪过/一股暖流等）
2. 减少副词（微微/轻轻/淡淡/缓缓/徐徐），换具体动作
3. 打破三段式循环：混入短句、碎句、省略句
4. 对话不要每句都带"说道"，混用动作+语气词
5. 段落长短要有变化
6. 保留所有剧情、对话、角色行为、伏笔、悬念不变
7. 字数与原文相差不超过 10%
8. 直接输出润色后正文，不要 JSON 不要解释
"""

STYLE_ADAPT_USER_TEMPLATE = """\
以下是需要风格适配的章节：

{chapter_content}

请进行风格适配。直接输出润色后的正文。
"""


# ── Step 3: 排版规则（纯规则，零 LLM） ──────────────────────────
# 对话行单独成段；连续超过 120 字的段落尝试按句号/换行拆分


def _typeset(content: str) -> str:
    """纯规则排版：段落格式 + 对话独立成段 + 标点清理。"""
    lines = content.split("\n")
    result_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result_lines.append("")
            continue

        # 对话行（被双引号包裹或对话引导词结尾）独立成段
        # 典型格式："xxx" / "xxx"，他 / "xxx"。他
        if stripped.startswith('"') and stripped.count('"') >= 2:
            result_lines.append(stripped)
            continue
        if stripped.endswith('"') and stripped.count('"') >= 2:
            result_lines.append(stripped)
            continue

        # 对话前缀：前导词 + 冒号 + 引号（如 他说："xxx"）
        # 保持原样，不拆分

        # 过长的段落（>120 字且含句号/感叹号/问号）尝试按句子拆段
        if len(stripped) > 120:
            # 优先按已有换行拆分
            if "\n" in stripped:
                for sub in stripped.split("\n"):
                    sub = sub.strip()
                    if sub:
                        result_lines.append(sub)
                continue

            # 无换行的长段落：按句号/感叹号/问号分段，但最多分 3 段
            sentences = re.split(r'(?<=[。！？])', stripped)
            sentences = [s.strip() for s in sentences if s.strip()]
            if len(sentences) > 1:
                # 把句子分组合并为段，每段不超过 80 字
                current: list[str] = []
                current_len = 0
                for s in sentences:
                    if current_len + len(s) > 80 and current:
                        result_lines.append("".join(current))
                        current = []
                        current_len = 0
                    current.append(s)
                    current_len += len(s)
                if current:
                    result_lines.append("".join(current))
            else:
                result_lines.append(stripped)
        else:
            result_lines.append(stripped)

    # 清理多余空行（连续空行合并为 1）
    cleaned: list[str] = []
    prev_blank = False
    for line in result_lines:
        is_blank = (line == "")
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank

    return "\n".join(cleaned)


# ── Step 4: AI 味终检（非流式，返回检测分） ──────────────────────
# 复用 ai_service 的 de_ai 逻辑；这里只做评分+决策
# 如果评分高 → 调 de_ai_rewrite_stream


class PolishService:
    """章节润色服务。"""

    def __init__(self, ai_service: AIService):
        self._ai_service = ai_service

    async def polish_chapter(
        self,
        db: AsyncSession,
        chapter: Chapter,
        review_result: dict | None = None,
        style_guidance: list[str] | None = None,
        *,
        apply_de_ai: bool = True,
    ) -> PolishResult:
        """
        四步润色主入口。

        Args:
            db: 数据库 session
            chapter: 待润色章节
            review_result: ReviewService 返回的审查结果（含 issues）
            style_guidance: 风格指导列表
            apply_de_ai: 是否执行去 AI 味终检
        """
        # 提取正文
        content = self._extract_chapter_text(chapter)
        if not content or len(content.strip()) < 50:
            return PolishResult(
                polished_content=content or "",
                report={
                    "status": "skipped",
                    "reason": "章节内容过短，跳过润色",
                    "steps": {},
                },
            )

        steps: dict[str, dict] = {}
        current_text = content

        # Step 1: 定点修复
        fix_result = await self._fix_issues(db, current_text, review_result)
        steps["fix_issues"] = fix_result
        current_text = fix_result.get("content", current_text)

        # Step 2: 风格适配
        style_result = await self._apply_style(db, current_text, style_guidance)
        steps["style_adapt"] = style_result
        current_text = style_result.get("content", current_text)

        # Step 3: 排版
        current_text = _typeset(current_text)
        steps["typeset"] = {"status": "ok", "changes": "段落格式优化"}

        # Step 4: AI 味终检
        if apply_de_ai:
            anti_ai_result = await self._anti_ai_final(db, current_text)
            steps["anti_ai_final"] = anti_ai_result
            if anti_ai_result.get("should_rewrite"):
                current_text = anti_ai_result.get("content", current_text)

        total_changes = sum(
            1 for s in steps.values() if s.get("changes") and s.get("changes") != "无"
        )

        report = {
            "status": "completed",
            "steps": steps,
            "total_changes": total_changes,
            "original_word_count": len(content),
            "polished_word_count": len(current_text),
        }

        return PolishResult(polished_content=current_text, report=report)

    # ── Step 1: 定点修复 ─────────────────────────────────────────
    async def _fix_issues(
        self,
        db: AsyncSession,
        content: str,
        review_result: dict | None,
    ) -> dict:
        """根据 review issues 做定点修复。只处理 blocking/high severity。"""
        if not review_result:
            return {"status": "skipped", "reason": "无审查结果", "content": content}

        issues = review_result.get("issues", [])
        # 只处理 blocking 或 high/critical 的 issue
        critical_issues = [
            i for i in issues
            if i.get("severity") in ("critical", "high")
            or i.get("blocking") is True
        ]

        if not critical_issues:
            return {"status": "ok", "changes": "无关键问题需修复", "content": content}

        # 构建 issues 文本
        issues_text = "\n".join(
            f"- [{i.get('severity', '?')}] {i.get('description', '')}\n  "
            f"位置：{i.get('location', '?')}\n  "
            f"修复建议：{i.get('fix_hint', '')}"
            for i in critical_issues
        )

        # 调 LLM 做定点修复
        client = await self._ai_service._build_client(db)
        try:
            messages = [
                {"role": "system", "content": FIX_ISSUES_SYSTEM},
                {"role": "user", "content": FIX_ISSUES_USER_TEMPLATE.format(
                    chapter_content=content[:5000],
                    issues_text=issues_text,
                )},
            ]
            result = await client.chat(messages, temperature=0.3, max_tokens=8192)
            fixed_content = str(result)
        finally:
            await client.close()

        return {
            "status": "ok",
            "changes": f"修复 {len(critical_issues)} 个关键问题",
            "content": fixed_content,
        }

    # ── Step 2: 风格适配 ────────────────────────────────────────
    async def _apply_style(
        self,
        db: AsyncSession,
        content: str,
        style_guidance: list[str] | None,
    ) -> dict:
        """风格适配：注入风格指导 + 通用风格规则。"""
        user_prompt = STYLE_ADAPT_USER_TEMPLATE.format(chapter_content=content[:5000])

        if style_guidance:
            # 把风格指导拼入系统提示
            system_prompt = STYLE_ADAPT_SYSTEM + "\n\n### 额外风格要求\n" + "\n".join(
                f"- {s}" for s in style_guidance
            )
        else:
            system_prompt = STYLE_ADAPT_SYSTEM

        client = await self._ai_service._build_client(db)
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            result = await client.chat(messages, temperature=0.7, max_tokens=8192)
            styled_content = str(result)
        finally:
            await client.close()

        return {
            "status": "ok",
            "changes": f"风格适配完成" + (f"（{len(style_guidance)} 条风格指导）" if style_guidance else ""),
            "content": styled_content,
        }

    # ── Step 4: AI 味终检 ────────────────────────────────────────
    async def _anti_ai_final(self, db: AsyncSession, content: str) -> dict:
        """AI 味终检：评分，超过阈值则调用去 AI 味重写。"""
        # 简单启发式评分（不占 LLM 额度）
        score = self._heuristic_anti_ai_score(content)
        should_rewrite = score >= 70

        if not should_rewrite:
            return {"status": "passed", "score": score, "should_rewrite": False,
                    "content": content}

        # 超过阈值 → 调 de_ai rewrite
        try:
            # 用 _build_client + de_ai prompt 非流式重写
            client = await self._ai_service._build_client(db)
            try:
                # 复用 AIService 的 de_ai prompt
                from pathlib import Path
                prompt_dir = Path(__file__).parent.parent.parent / "prompts"
                import yaml as _yaml
                with open(prompt_dir / "de_ai.yaml", encoding="utf-8") as f:
                    prompt = _yaml.safe_load(f)
                messages = [
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"].format(original_content=content[:5000])},
                ]
                result = await client.chat(messages, temperature=0.9, max_tokens=8192)
                rewritten = str(result)
            finally:
                await client.close()
            return {"status": "rewritten", "score": score, "should_rewrite": True,
                    "content": rewritten}
        except Exception:
            # fallback：调 _apply_style 做一次风格适配
            result = await self._apply_style(db, content, style_guidance=None)
            return {"status": "styled_fallback", "score": score, "should_rewrite": True,
                    "content": result["content"]}

    def _heuristic_anti_ai_score(self, text: str) -> int:
        """
        启发式 AI 味评分（零 LLM）。
        基于八股词密度 + 句式均匀度 + 副词密度。
        返回 0-100。
        """
        if len(text) < 50:
            return 30

        # 八股词列表
        cliches = [
            "不禁", "仿佛", "宛如", "嘴角微微", "眼中闪过", "一股暖流",
            "心中暗想", "暗自思忖", "不自觉地", "顿时", "霎时",
            "若有所思", "意味深长", "深邃", "锐利", "犀利",
            "微微一笑", "轻轻", "淡淡", "微微", "缓缓", "徐徐",
            "感受到", "感受到一种", "内心", "心头",
        ]
        cliche_count = sum(text.count(w) for w in cliches)
        cliche_score = min(40, cliche_count * 4)

        # 段落长度均匀度（AI 倾向每段都差不多长）
        paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
        if len(paragraphs) >= 3:
            lengths = [len(p) for p in paragraphs]
            avg = sum(lengths) / len(lengths)
            variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
            std = variance ** 0.5
            cv = std / avg if avg > 0 else 1
            # CV 小（段落均匀）→ AI 嫌疑大
            uniformity_score = max(0, int(30 * (1 - cv)))
        else:
            uniformity_score = 0

        # 副词密度
        adverbs = ["微微", "轻轻", "淡淡", "缓缓", "徐徐", "悄悄地", "慢慢地"]
        adverb_count = sum(text.count(w) for w in adverbs)
        adverb_score = min(30, adverb_count * 3)

        total = min(100, cliche_score + uniformity_score + adverb_score)
        return total

    # ── 工具方法 ────────────────────────────────────────────────
    def _extract_chapter_text(self, chapter: Chapter) -> str:
        """从 Chapter 提取纯文本正文。"""
        c = chapter.content
        if c is None:
            return ""
        if isinstance(c, dict) and "text" in c and isinstance(c["text"], str):
            return c["text"]
        if isinstance(c, str):
            return c
        return str(c or "")
