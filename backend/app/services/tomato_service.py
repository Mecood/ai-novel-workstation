"""
P5B: Tomato (番茄小说) Compliance Service

三个步骤：
1. zhuque_check — 调用朱雀检测器，返回 AI 概率
2. de_ai_for_tomato — 针对番茄统计指纹优化的去 AI 味改写
3. tomato_export — 导出番茄要求的格式（纯文本，章节分隔，每章标题格式）
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from app.services.ai_service import AIService


@dataclass
class ZhuqueResult:
    """朱雀检测结果"""
    chapter_number: int
    ai_probability: float      # 0.0-1.0
    verdict: str               # "safe" / "warning" / "danger"
    segments: list[float] = field(default_factory=list)  # 各段 AI 概率

@dataclass
class TomatoExportResult:
    """番茄导出结果"""
    project_name: str
    chapter_count: int
    total_chars: int
    text: str                  # 番茄纯文本格式

class TomatoExporter:
    """番茄小说导出器"""

    def __init__(self, zhuque_detector=None, ai_service=None):
        self.zhuque = zhuque_detector
        self.ai = ai_service

    def export_project(self, project_name: str, chapters: list[dict]) -> TomatoExportResult:
        """
        导出为番茄要求的纯文本格式：
        - 章节标题格式："第N章 标题"
        - 章节间用双空行分隔
        - 每段前空两格（番茄编辑器自动处理，这里用文本缩进指示）
        """
        lines: list[str] = []
        total_chars = 0

        for ch in sorted(chapters, key=lambda c: c.get("chapter_number", 0)):
            ch_num = ch.get("chapter_number", "?")
            title = ch.get("title", "")

            # 章节标题
            lines.append(f"第{ch_num}章 {title}")
            lines.append("")

            # 正文
            content = ch.get("content", "").strip()
            if content:
                total_chars += len(content)
                # 按段落分割
                paragraphs = content.split("\n\n")
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        lines.append(para)
                lines.append("")
            lines.append("")

        text = "\n".join(lines)
        return TomatoExportResult(
            project_name=project_name,
            chapter_count=len(chapters),
            total_chars=total_chars,
            text=text,
        )

    async def check_with_zhuque(self, chapter_text: str) -> dict:
        """调用朱雀检测器"""
        if not self.zhuque:
            return {"error": "朱雀检测器未加载"}

        try:
            result = self.zhuque.detect(chapter_text)
            return result
        except Exception as e:
            return {"error": str(e)}

    async def de_ai_for_tomato(
        self, chapter_text: str, previous_zhuque_score: float = 0,
    ) -> str:
        """
        针对番茄平台优化去 AI 味改写。
        目标：降低困惑度、增加突发性、增加词汇多样性，
        让朱雀检测的统计指纹更接近人类创作。
        """
        if not self.ai:
            return chapter_text

        prompt = f"""你是番茄小说平台的资深编辑，熟知朱雀 AIGC 检测系统的识别规则。

朱雀检测核心维度：
1. 困惑度（perplexity）— AI 文本因过度优化而困惑度异常低
2. 突发性（burstiness）— AI 文本句式过于整齐
3. 语义连贯性 — AI 文本过分连贯，缺乏人类思维的跳跃感
4. 词汇分布 — AI 文本高频词过于均衡
5. 修辞多样性 — AI 文本缺乏个性化的隐喻/比喻
6. 情感一致性 — AI 文本情感表达过于"安全"

请按以下原则改写以下小说文本，降低朱雀检测的 AI 概率评分：
- 合理增加句子间的不规则性（不要每句都整齐）
- 加入一些适当的口语化表达
- 保留网文特色的节奏感和爽点
- 不要为了改而改得难读——可读性第一

当前 AI 检测概率：{previous_zhuque_score:.0%}

待改写的文本：
{chapter_text[:4000]}

请输出改写后的完整文本（不要 JSON，直接输出文本）。"""

        try:
            result = await self.ai.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return result.strip()
        except Exception:
            return chapter_text