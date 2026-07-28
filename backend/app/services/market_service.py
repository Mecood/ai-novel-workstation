"""
P5D: 读者反馈模拟
P5E: 竞品拆解反哺

两个轻量级能力：
- simulate_readers: AI 模拟不同类型的读者对章节的评论/弹幕
- deconstruct_competitor: 输入一篇爆款小说，AI 拆解结构反哺
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.services.ai_service import AIService


@dataclass
class SimulatedComment:
    reader_type: str     # "爽文爱好者" / "考据党" / "感情线敏感"
    sentiment: str       # "喜欢" / "不满" / "困惑" / "期待"
    comment: str         # 评论内容
    highlight: str       # 你觉得最精彩/最不喜欢的段落


class ReaderFeedbackService:
    """读者反馈模拟"""
    def __init__(self, ai_service=None):
        self.ai = ai_service

    READER_TYPES = [
        {"type": "爽文爱好者", "preference": "节奏快、爽点多、打脸不过夜"},
        {"type": "考据党", "preference": "逻辑严谨、世界观自洽、设定不崩"},
        {"type": "感情线读者", "preference": "男女主互动自然、情感推进合理"},
        {"type": "重度书虫", "preference": "网文阅历丰富、对比同类作品"},
        {"type": "编辑视角", "preference": "签约标准、商业潜力、市场竞争力"},
    ]

    async def feedback(self, project_name: str, chapter_number: int, chapter_text: str) -> list[dict]:
        """AI 模拟4种读者对本章的评论"""
        if not self.ai:
            return []

        prompt = f"""你是小说读者模拟器。对小说《{project_name}》第{chapter_number}章给出读者反馈。

分别模拟以下4种读者视角，每人写一条评论（20-50字）和1个关注段落：

1. 爽文爱好者 —— 关注节奏、冲突、爽点
2. 考据党 —— 关注逻辑、设定一致性
3. 感情线读者 —— 关注角色互动、情感表达
4. 吐槽视角 —— 关注烂尾概率、套路质疑

章节正文：
{chapter_text[:3000]}

严格按JSON输出：
```json
[
  {{"reader_type":"爽文爱好者","sentiment":"喜欢|不满|期待|疑惑","comment":"20-50字评论","highlight":"关注的段落片段"}},
  ...
]
```
只输出纯 JSON。"""

        try:
            result = await self.ai.chat(
                messages=[{"role":"user","content":prompt}],
                temperature=0.9,
            )
            return self._parse_json(result)
        except Exception:
            return []

    def _parse_json(self, text):
        text = text.strip()
        for p in ["```json","```"]: text = text.removeprefix(p)
        text = text.removesuffix("```").strip()
        return json.loads(text)


class DeconstructionService:
    """竞品拆解服务"""
    def __init__(self, ai_service=None):
        self.ai = ai_service

    async def deconstruct(self, novel_text: str, novel_title: str = "目标作品") -> dict:
        """拆解一篇小说的结构、爆点、卖点"""
        if not self.ai:
            return {"error":"AI服务未配置"}

        prompt = f"""你是专业网文结构分析师。分析以下爆款小说的核心卖点和成功要素。

作品：《{novel_title}》

正文（前3章或关键段落）：
{novel_text[:6000]}

从以下维度分析，严格按JSON输出：

- 结构：开篇/承转/高潮/结局的四幕拆解
- 卖点：3个独特的吸引读者的点
- 节奏：3段关键节奏分析
- 教训：你可以从这篇学到的2条创作技巧
- 适配：如果我要写一篇同类作品，应该怎么切入（50字建议）

```json
{{
  "title": "{novel_title}",
  "structure": {{
    "act1_opening": "开篇手法分析（20字）",
    "act2_development": "发展手法分析（20字）",
    "act3_climax": "高潮手法分析（20字）",
    "act4_resolution": "收尾手法分析（20字）"
  }},
  "selling_points": ["卖点1","卖点2","卖点3"],
  "rhythm_analysis": ["节奏点1","节奏点2","节奏点3"],
  "lessons": ["创作经验1","创作经验2"],
  "angle": "同类切入角度建议"
}}
```

只输出纯JSON。"""

        try:
            result = await self.ai.chat(
                messages=[{"role":"user","content":prompt}],
                temperature=0.7,
            )
            return self._parse_json(result)
        except Exception:
            return {}

    def _parse_json(self, text):
        text = text.strip()
        for p in ["```json","```"]: text = text.removeprefix(p)
        text = text.removes("```").strip()
        return json.loads(text)