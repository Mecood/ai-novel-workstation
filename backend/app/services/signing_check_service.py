"""
P5C: Contract-fit Self-Check Service

签约自测——用编辑视角自动审查前三章，输出评分报告。
维度：黄金三章要件 / 爆钩密度 / 断章节奏 / 人物记忆点 / 世界观吸引力
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.services.ai_service import AIService


@dataclass
class DimensionScore:
    name: str = ""            # 维度名称
    score: int = 0            # 0-100
    verdict: str = ""         # "优秀" / "良好" / "一般" / "不足"
    analysis: str = ""        # 分析文字
    id: str = ""              # 维度ID (可选)
    suggestions: list[str] = field(default_factory=list)

@dataclass
class SigningReport:
    total_score: int     # 0-100
    platform: str        # "tomato" / "qidian"
    pass_threshold: int  # 该平台签约合格线
    is_pass: bool
    dimensions: list[DimensionScore]
    summary: str
    top_strength: str    # 最大亮点
    top_weakness: str    # 最大短板


class SigningCheckService:
    """签约自测服务"""

    def __init__(self, ai_service=None):
        self.ai = ai_service

    DIMENSIONS = [
        {
            "id": "golden_three",
            "name": "黄金三章要件",
            "weight": 0.25,
            "check": "前三章是否有明确的冲突引入、主角动机建立、世界观钩子、第一爆点",
        },
        {
            "id": "hook_density",
            "name": "爆钩密度",
            "weight": 0.20,
            "check": "每章末是否有追读钩子、每3000字是否有小爆点/冲突升级",
        },
        {
            "id": "chapter_end",
            "name": "断章节奏",
            "weight": 0.20,
            "check": "章末是否在紧张/悬念处断章而非自然段落结束、章末钩子是否有效",
        },
        {
            "id": "character_appeal",
            "name": "人物代入感",
            "weight": 0.20,
            "check": "主角是否在三章内建立读者认同、配角是否立体、反派是否有魅力",
        },
        {
            "id": "world_appeal",
            "name": "世界观吸引力",
            "weight": 0.15,
            "check": "世界观设定是否新颖、是否能在一开始引起读者好奇",
        },
    ]

    async def analyze(
        self, project_name: str, chapters: list[dict],
        worldview: str = "", characters: str = "",
    ) -> SigningReport:
        """分析前三章，返回签约自测报告"""
        if not self.ai:
            return self._empty_report()

        # 构建章节文本
        chapter_texts = []
        for ch in sorted(chapters, key=lambda c: c.get("chapter_number", 0)):
            title = ch.get("title", "")
            content = ch.get("content", "")
            chapter_texts.append(f"第{ch['chapter_number']}章 {title}\n{content[:3000]}")

        all_text = "\n\n---\n\n".join(chapter_texts[:3])

        # AI 分析
        prompt = f"""你是番茄小说/起点中文网的资深签约编辑，有10年以上审稿经验。

请对以下小说《{project_name}》的前三章进行签约标准评审。

世界观信息：{worldview[:500]}
角色信息：{characters[:500]}

正文：
{all_text[:8000]}

请从以下5个维度逐个评分，严格按JSON输出：

```json
{{
  "total_score": 0-100,
  "dimensions": [
    {{
      "id": "golden_three",
      "score": 0-100,
      "verdict": "优秀|良好|需要改进|不足",
      "analysis": "50字以内的专业分析",
      "suggestions": ["一条建议", "另一条建议"]
    }},
    ...
  ],
  "summary": "100字以内的总结评审意见",
  "top_strength": "最大亮点（15字以内）",
  "top_weakness": "最大短板（15字以内）"
}}
```

只输出纯 JSON，不要任何解释。评分要客观中肯。"""

        try:
            result = await self.ai.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
            )
            data = self._parse_json(result)

            dims = []
            for d in data.get("dimensions", []):
                dims.append(DimensionScore(
                    id=d.get("id", "?"),
                    name=d.get("name", "?"),
                    score=d.get("score", 0),
                    verdict=d.get("verdict", "中等"),
                    analysis=d.get("analysis", ""),
                    suggestions=d.get("suggestions", []),
                ))

            total = data.get("total_score", 50)
            return SigningReport(
                total_score=total,
                platform="tomato",
                pass_threshold=60,
                is_pass=total >= 60,
                dimensions=dimensions,
                summary=data.get("summary", ""),
                top_strength=data.get("top_strength", ""),
                top_weakness=data.get("top_weakness", ""),
            )
        except Exception as e:
            return self._empty_report()

    def _empty_report(self) -> SigningReport:
        return SigningReport(
            total_score=0,
            platform="tomato",
            pass_threshold=60,
            is_pass=False,
            dimensions=[],
            summary="",
            top_strength="",
            top_weakness="",
        )

    def _parse_json(self, text: str):
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text)