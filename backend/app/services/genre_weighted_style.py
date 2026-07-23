"""
Style Adapter 深度版 — GenreStyleWeighter + StyleVariantGenerator

GenreStyleWeighter: 37种题材的加权风格参数 + build_style_prompt_section
StyleVariantGenerator: 同一情节的不同风格变体生成
"""

import json
import asyncio
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession


# ─────────────────────────────────────────────────────────────────────────────
# 37题材风格参数（词汇密度/节奏/句式/修辞/情感温度/对话占比）
# ─────────────────────────────────────────────────────────────────────────────

GENRE_STYLE_PARAMS: dict[str, dict[str, float]] = {
    "修仙": {"vocabulary_density": 0.7, "rhythm": 0.6, "sentence_style": 0.5, "rhetoric_level": 0.6, "emotional_temperature": 0.4, "dialogue_ratio": 0.45},
    "都市异能": {"vocabulary_density": 0.4, "rhythm": 0.7, "sentence_style": 0.6, "rhetoric_level": 0.3, "emotional_temperature": 0.5, "dialogue_ratio": 0.55},
    "都市脑洞": {"vocabulary_density": 0.3, "rhythm": 0.8, "sentence_style": 0.7, "rhetoric_level": 0.2, "emotional_temperature": 0.5, "dialogue_ratio": 0.6},
    "都市日常": {"vocabulary_density": 0.3, "rhythm": 0.5, "sentence_style": 0.8, "rhetoric_level": 0.2, "emotional_temperature": 0.8, "dialogue_ratio": 0.65},
    "青春甜宠": {"vocabulary_density": 0.2, "rhythm": 0.6, "sentence_style": 0.7, "rhetoric_level": 0.25, "emotional_temperature": 0.9, "dialogue_ratio": 0.7},
    "豪门总裁": {"vocabulary_density": 0.3, "rhythm": 0.6, "sentence_style": 0.6, "rhetoric_level": 0.4, "emotional_temperature": 0.8, "dialogue_ratio": 0.6},
    "职场婚恋": {"vocabulary_density": 0.3, "rhythm": 0.5, "sentence_style": 0.8, "rhetoric_level": 0.2, "emotional_temperature": 0.7, "dialogue_ratio": 0.65},
    "狗血言情": {"vocabulary_density": 0.2, "rhythm": 0.7, "sentence_style": 0.6, "rhetoric_level": 0.3, "emotional_temperature": 0.95, "dialogue_ratio": 0.6},
    "现言脑洞": {"vocabulary_density": 0.3, "rhythm": 0.75, "sentence_style": 0.65, "rhetoric_level": 0.3, "emotional_temperature": 0.6, "dialogue_ratio": 0.6},
    "幻想言情": {"vocabulary_density": 0.5, "rhythm": 0.6, "sentence_style": 0.5, "rhetoric_level": 0.6, "emotional_temperature": 0.7, "dialogue_ratio": 0.5},
    "女频悬疑": {"vocabulary_density": 0.4, "rhythm": 0.6, "sentence_style": 0.5, "rhetoric_level": 0.4, "emotional_temperature": 0.5, "dialogue_ratio": 0.5},
    "古言": {"vocabulary_density": 0.7, "rhythm": 0.4, "sentence_style": 0.35, "rhetoric_level": 0.7, "emotional_temperature": 0.4, "dialogue_ratio": 0.4},
    "民国言情": {"vocabulary_density": 0.6, "rhythm": 0.45, "sentence_style": 0.4, "rhetoric_level": 0.65, "emotional_temperature": 0.5, "dialogue_ratio": 0.45},
    "宫斗宅斗": {"vocabulary_density": 0.5, "rhythm": 0.35, "sentence_style": 0.3, "rhetoric_level": 0.6, "emotional_temperature": 0.4, "dialogue_ratio": 0.55},
    "种田": {"vocabulary_density": 0.3, "rhythm": 0.3, "sentence_style": 0.7, "rhetoric_level": 0.2, "emotional_temperature": 0.7, "dialogue_ratio": 0.5},
    "年代": {"vocabulary_density": 0.4, "rhythm": 0.35, "sentence_style": 0.6, "rhetoric_level": 0.3, "emotional_temperature": 0.6, "dialogue_ratio": 0.55},
    "多子多福": {"vocabulary_density": 0.3, "rhythm": 0.4, "sentence_style": 0.7, "rhetoric_level": 0.2, "emotional_temperature": 0.7, "dialogue_ratio": 0.6},
    "替身文": {"vocabulary_density": 0.3, "rhythm": 0.6, "sentence_style": 0.6, "rhetoric_level": 0.3, "emotional_temperature": 0.85, "dialogue_ratio": 0.6},
    "西幻": {"vocabulary_density": 0.65, "rhythm": 0.5, "sentence_style": 0.4, "rhetoric_level": 0.7, "emotional_temperature": 0.45, "dialogue_ratio": 0.45},
    "高武": {"vocabulary_density": 0.6, "rhythm": 0.7, "sentence_style": 0.45, "rhetoric_level": 0.5, "emotional_temperature": 0.4, "dialogue_ratio": 0.35},
    "科幻": {"vocabulary_density": 0.55, "rhythm": 0.65, "sentence_style": 0.5, "rhetoric_level": 0.5, "emotional_temperature": 0.3, "dialogue_ratio": 0.4},
    "无限流": {"vocabulary_density": 0.5, "rhythm": 0.8, "sentence_style": 0.6, "rhetoric_level": 0.4, "emotional_temperature": 0.4, "dialogue_ratio": 0.45},
    "末世": {"vocabulary_density": 0.45, "rhythm": 0.7, "sentence_style": 0.5, "rhetoric_level": 0.35, "emotional_temperature": 0.3, "dialogue_ratio": 0.4},
    "系统流": {"vocabulary_density": 0.35, "rhythm": 0.75, "sentence_style": 0.65, "rhetoric_level": 0.2, "emotional_temperature": 0.4, "dialogue_ratio": 0.5},
    "游戏体育": {"vocabulary_density": 0.3, "rhythm": 0.9, "sentence_style": 0.7, "rhetoric_level": 0.15, "emotional_temperature": 0.6, "dialogue_ratio": 0.45},
    "电竞": {"vocabulary_density": 0.25, "rhythm": 0.9, "sentence_style": 0.75, "rhetoric_level": 0.1, "emotional_temperature": 0.5, "dialogue_ratio": 0.5},
    "直播文": {"vocabulary_density": 0.2, "rhythm": 0.85, "sentence_style": 0.85, "rhetoric_level": 0.1, "emotional_temperature": 0.65, "dialogue_ratio": 0.7},
    "知乎短篇": {"vocabulary_density": 0.5, "rhythm": 0.7, "sentence_style": 0.5, "rhetoric_level": 0.5, "emotional_temperature": 0.5, "dialogue_ratio": 0.45},
    "规则怪谈": {"vocabulary_density": 0.4, "rhythm": 0.6, "sentence_style": 0.4, "rhetoric_level": 0.4, "emotional_temperature": 0.2, "dialogue_ratio": 0.4},
    "悬疑脑洞": {"vocabulary_density": 0.4, "rhythm": 0.65, "sentence_style": 0.45, "rhetoric_level": 0.4, "emotional_temperature": 0.3, "dialogue_ratio": 0.45},
    "悬疑灵异": {"vocabulary_density": 0.4, "rhythm": 0.5, "sentence_style": 0.4, "rhetoric_level": 0.45, "emotional_temperature": 0.25, "dialogue_ratio": 0.4},
    "历史脑洞": {"vocabulary_density": 0.55, "rhythm": 0.5, "sentence_style": 0.4, "rhetoric_level": 0.55, "emotional_temperature": 0.4, "dialogue_ratio": 0.45},
    "历史古代": {"vocabulary_density": 0.6, "rhythm": 0.4, "sentence_style": 0.35, "rhetoric_level": 0.6, "emotional_temperature": 0.4, "dialogue_ratio": 0.4},
    "抗战谍战": {"vocabulary_density": 0.45, "rhythm": 0.65, "sentence_style": 0.45, "rhetoric_level": 0.35, "emotional_temperature": 0.35, "dialogue_ratio": 0.45},
    "黑暗题材": {"vocabulary_density": 0.55, "rhythm": 0.4, "sentence_style": 0.35, "rhetoric_level": 0.6, "emotional_temperature": 0.15, "dialogue_ratio": 0.35},
    "克苏鲁": {"vocabulary_density": 0.65, "rhythm": 0.35, "sentence_style": 0.25, "rhetoric_level": 0.75, "emotional_temperature": 0.1, "dialogue_ratio": 0.3},
    "现实题材": {"vocabulary_density": 0.4, "rhythm": 0.45, "sentence_style": 0.7, "rhetoric_level": 0.25, "emotional_temperature": 0.6, "dialogue_ratio": 0.6},
}

# 风格变体类型
STYLE_VARIANT_TYPES = [
    {
        "id": "serious",
        "label": "严肃正剧",
        "prompt_addition": "使用典雅、克制的语言。情感表达内敛，通过行为而非直白表露展现内心。句式平衡，节奏从容。适合史诗、历史、现实题材。",
    },
    {
        "id": "light",
        "label": "轻松幽默",
        "prompt_addition": "加入口语化表达和幽默感。允许俏皮话、吐槽、内心腹诽。节奏轻快，段落较短。适合都市、青春、甜宠。",
    },
    {
        "id": "poetic",
        "label": "诗意文学",
        "prompt_addition": "使用意象化语言，善用比喻和通感。留白多，让读者自行体会。句式有韵律感，段落疏密对比明显。适合古言、幻想、文学向。",
    },
    {
        "id": "action",
        "label": "快节奏动作",
        "prompt_addition": "短句为主，省略修饰词。动作描写精准利落，一句一动作。对话简洁，不做过多心理描写。适合战斗、追逐、高潮场景。",
    },
    {
        "id": "psychology",
        "label": "心理描写",
        "prompt_addition": "深入角色内心，展示意识流和潜意识层。用生理反应+微动作暗示情感，而非直接贴标签。内心独白和回忆穿插。适合情感冲突、角色转变。",
    },
]


class GenreStyleWeighter:
    """题材加权风格参数器。"""

    NAME_TO_KEY: dict[str, str] = {}

    @classmethod
    def _resolve_genre(cls, genre: str) -> str:
        """模糊匹配题材名 → 参数表 key。"""
        if not cls.NAME_TO_KEY:
            cls.NAME_TO_KEY = {k: k for k in GENRE_STYLE_PARAMS}
            # 别名
            aliases = {
                "玄幻": "修仙", "言情": "青春甜宠", "都市": "都市日常",
                "悬疑": "悬疑脑洞", "灵异": "悬疑灵异", "恐怖": "黑暗题材",
                "史诗奇幻": "西幻", "武侠": "高武", "末日": "末世",
                "电竞小说": "电竞", "游戏": "游戏体育",
                "田园": "种田", "古代": "古言", "谍战": "抗战谍战",
                "爱情": "狗血言情", "系统": "系统流", "规则": "规则怪谈",
            }
            cls.NAME_TO_KEY.update(aliases)

        genre_lower = genre.lower().strip()
        for key in cls.NAME_TO_KEY:
            if key in genre_lower or genre_lower in key:
                return key
        # 模糊包含匹配
        for key in GENRE_STYLE_PARAMS:
            if any(word in genre_lower for word in key.split()):
                return key
        return "都市日常"  # 默认

    def get_style_params(self, genre: str) -> dict[str, float]:
        """返回题材风格参数。"""
        key = self._resolve_genre(genre)
        return dict(GENRE_STYLE_PARAMS.get(key, GENRE_STYLE_PARAMS["都市日常"]))

    def build_style_prompt_section(self, genre: str, chapter_type: str = "normal") -> str:
        """生成注入 prompt 的风格段落。"""
        params = self.get_style_params(genre)
        lines = [
            "## 风格参数指导（题材自适应）",
            "",
            f"题材风格：{self._resolve_genre(genre)}",
            "",
            "请在写作中注意以下参数倾向：",
        ]
        labels = {
            "vocabulary_density": "词汇密度",
            "rhythm": "节奏速度",
            "sentence_style": "句式复杂度",
            "rhetoric_level": "修辞程度",
            "emotional_temperature": "情感温度",
            "dialogue_ratio": "对话占比",
        }
        for key, label in labels.items():
            val = params.get(key, 0.5)
            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
            lines.append(f"- {label}: {bar} ({val:.1f})")

        # 章节类型微调
        if chapter_type in ("combat", "action"):
            lines.append("- ⚡ 战斗场景：节奏+0.2，修辞-0.1，对话占比-0.1")
        elif chapter_type in ("emotional", "romance"):
            lines.append("- 💕 情感场景：情感温度+0.15，对话占比+0.1，节奏-0.1")
        elif chapter_type == "dialogue":
            lines.append("- 💬 对话场景：对话占比+0.2，句式复杂度-0.1")

        return "\n".join(lines)


class StyleVariantGenerator:
    """风格变体生成器。"""

    def __init__(self, db: AsyncSession, project_id: str):
        self.db = db
        self.project_id = project_id

    def get_variant_options(self, genre: str) -> list[dict]:
        """根据题材返回可用的风格变体选项。"""
        weighter = GenreStyleWeighter()
        params = weighter.get_style_params(genre)

        # 按题材特征筛选合适的变体
        all_variants = list(STYLE_VARIANT_TYPES)
        selected = all_variants[:]  # 默认全给

        # 情感温度很高 → 移除过于冷淡的风格
        if params.get("emotional_temperature", 0.5) >= 0.8:
            selected = [v for v in selected if v["id"] not in ("action",)]
        # 修辞程度高 → 加诗意
        if params.get("rhetoric_level", 0.3) >= 0.6:
            # 诗意已在列表中，保留
            pass
        # 节奏高 → 优先快节奏
        if params.get("rhythm", 0.5) >= 0.7:
            selected = [v for v in selected if v["id"] != "psychology"]

        return selected

    def generate_variant_prompt(self, base_text: str, genre: str, variant_id: str) -> str:
        """生成风格变体改写 prompt。"""
        variant = next((v for v in STYLE_VARIANT_TYPES if v["id"] == variant_id), None)
        if not variant:
            variant = STYLE_VARIANT_TYPES[0]

        weighter = GenreStyleWeighter()
        params = weighter.get_style_params(genre)

        prompt = f"""你是小说风格改写专家。将以下段落改写为"{variant['label']}"风格。

原文：
---
{base_text[:3000]}
---

改写要求：
{variant['prompt_addition']}

题材背景：{weighter._resolve_genre(genre)}
参考参数：词汇密度{params['vocabulary_density']:.1f} 节奏{params['rhythm']:.1f} 情感温度{params['emotional_temperature']:.1f}

要求：
1. 保持原情节、事件顺序和关键对话内容不变
2. 只改变表达方式、句式节奏、情感渲染程度
3. 输出纯文本，不要加任何说明或JSON格式
4. 长度与原段落相当（±20%）
"""
        return prompt

    async def generate_variants_stream(
        self, base_text: str, genre: str, variant_ids: list[str],
    ) -> dict[str, str]:
        """流式生成多个风格变体（返回 {variant_id: text}）。"""
        from app.core.ai_client import AIClient  # 需要 await 上下文

        results = {}
        for vid in variant_ids:
            prompt_text = self.generate_variant_prompt(base_text, genre, vid)
            # 用同步方式生成（简化版，实际使用时由 AI service 调用）
            results[vid] = prompt_text  # 返回 prompt 供调用方使用 AI client
        return results