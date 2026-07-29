"""Topic research service — AI 选题调研。

提供给新建项目向导的步骤 1.5，用于分析题材在当前市场的热度、
竞争格局、切入角度推荐。

Output format: {
  genre: str,
  market_summary: str,
  hot_trends: list[str],
  recommendations: [{
    angle: str, score: float, reasoning: str, entry_point: str
  }]
}
"""

import json
import re

from app.services.ai_service import AIService
from app.models.app_config import AppConfig
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException


SYSTEM_PROMPT = """你是一位资深网文编辑和市场分析师，精通各大小说平台的选题策略。

根据用户选择的题材，你需要在以下维度提供洞察：

1. 当前市场趋势：该题材近期的阅读热度、读者偏好变化、平台审稿风向
2. 切入点分析：不同角度的市场空白和竞争优势，避免同质化
3. 推荐的切入点：3个差异化方案，各有不同的商业价值

每项推荐必须具体、可执行、基于真实市场分析。

请用 JSON 格式输出，结构为：
{
  "market_summary": "该题材当前市场状况的整体描述（200-300字）",
  "hot_trends": ["趋势1", "趋势2", "趋势3"],
  "recommendations": [
    {
      "angle": "切入角度",
      "score": 0.85,
      "description": "为什么这个角度可行",
      "entry_point": "具体的开篇建议（50字内）"
    }
  ]
}"""


MARKET_CONTEXT = """以 {
的市场环境分析背景：2025-2026年的主流在线小说平台（起点、
纵横、今日头条等）的流量结构；各类题材的竞争强度；受众画像和
阅读习惯数据。"""

def _parse_json(text: str) -> dict:
    """多层兜底解析JSON"""
    import json, re

    try: return json.loads(text.strip())
    except: pass

    try:
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            return json.loads(text[brace_start:brace_end+1])
    except: pass

    try:
        cleaned = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', text, flags=re.DOTALL)
        return json.loads(cleaned)
    except:
        return {"raw": text}


async def research_topic(
    db: AsyncSession,
    genre: str,
    project_name: str = "",
) -> dict:
    """Analyze a genre for the selected project.

    Returns a dict with market_summary, hot_trends, recommendations.
    Each recommendation has angle, score, description, entry_point.
    """
    if not genre:
        raise HTTPException(400, "必须提供题材")

    # Check AI config
    result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config or not config.config:
        raise HTTPException(400, "AI 未配置，请先在设置中添加模型供应商")
    active = config.config.get("active_provider")
    providers = config.config.get("providers", [])
    active_provider_idx = config.config.get("active_provider")
    active_provider = None
    if isinstance(active_provider_idx, int) and 0 <= active_provider_idx < len(providers):
        active_provider = providers[active_provider_idx]
    elif isinstance(active_provider_idx, str):
        active_provider = next((p for p in providers if p.get("name") == active_provider_idx), None)
    if not active_provider or not active_provider.get("api_key"):
        raise HTTPException(400, "AI 未配置")

    ai = AIService()
    client = await ai._build_client(db)

    user_prompt = f"""题材：{genre}
作品名参考：{project_name or '未指定'}

请分析这个题材在当前网文市场的状况，然后提供3个差异化的切入点建议。
每个切入点要瞄准不同的商业路径（如：深耕核心读者、大众轻向、实验创新）。
"""

    try:
        response = await client.chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ], temperature=0.8)
    finally:
        await client.close()

    parsed = _parse_json(response)
    if not isinstance(parsed, dict):
        import json
        parsed = {"raw": response}

    return {
        "genre": genre,
        "market_summary": parsed.get("market_summary", ""),
        "hot_trends": parsed.get("hot_trends", []),
        "recommendations": parsed.get("recommendations", []),
    }