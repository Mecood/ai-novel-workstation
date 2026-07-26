"""
朱雀检测本地替代器——基于 yuchuantian/AIGC_detector_zhv2 (ICLR 2024 Spotlight)

模型位置: /Users/products/code/ai-novel-workstation/backend/models/zhv2_local

检测逻辑：困惑度/突发性/语义连贯性的统计指纹，与朱雀检测同源（困惑度+突发性+语义连贯性+词汇分布+句法结构）

调用方式：
    detector = ZhuqueDetector()
    result = await detector.detect(text)
    # result = {"ai_probability": 0.12, "verdict": "人工", "level": "safe"}
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


# 模型路径——从 HF 下载好的本地缓存
_MODEL_ROOT = Path(__file__).parent.parent.parent / "models" / "zhv2"


class ZhuqueDetector:
    """
    朱雀 AIGC 检测本地替代器。

    检测维度（与朱雀检测同源）：
    - 困惑度（perplexity）—— 字词序列的可预测性
    - 突发性（burstiness）—— 句长分布的波动幅度
    - 语义连贯性—— 段落过渡是否"太完美"
    - 词汇分布—— 高频词集中度
    - 句法结构—— 主谓宾搭配的规整度

    阈值参考朱雀小说版：
    - safe: ai_probability < 0.30  (基本人工)
    - suspect: 0.30 <= ai_probability < 0.50  (可疑)
    - likely_ai: 0.50 <= ai_probability < 0.80  (很可能 AI)
    - confirmed_ai: ai_probability >= 0.80  (AI 生成)
    """

    def __init__(self, model_dir: Optional[Path] = None):
        self._tokenizer: Optional[AutoTokenizer] = None
        self._model: Optional[AutoModelForSequenceClassification] = None
        self._model_path = model_dir or self._find_model()
        self._device = "cpu"  # 无 GPU 环境

        # 分段检测阈值（朱雀小说版适配）
        self.thresholds = {
            "safe": 0.30,       # 人工
            "suspect": 0.50,    # 可疑
            "likely_ai": 0.80,  # 很可能 AI
            "confirmed_ai": 1.00,  # AI 生成
        }

    @staticmethod
    def _find_model() -> Path:
        """找本地缓存的模型目录。"""
        root = _MODEL_ROOT
        if root.exists():
            # 找 snapshots 下的模型目录
            for p in root.glob("models--*/snapshots/*/"):
                if (p / "config.json").exists() and (p / "pytorch_model.bin").exists():
                    return p
        raise RuntimeError(
            f"zhv2 模型未找到。请先运行: python3 -m huggingface_hub "
            f"download yuchuantian/AIGC_detector_zhv2 --cache-dir {_MODEL_ROOT}"
        )

    def _ensure_loaded(self):
        """懒加载模型和 tokenizer。"""
        if self._model is not None and self._tokenizer is not None:
            return
        if not self._model_path.exists():
            raise RuntimeError(f"模型目录不存在: {self._model_path}")

        self._tokenizer = AutoTokenizer.from_pretrained(self._model_path)
        self._model = AutoModelForSequenceClassification.from_pretrained(self._model_path)
        self._model.eval()
        # 确保 logits 在 CPU 上计算（无 GPU 环境）
        self._model.to("cpu")

    async def detect(self, text: str) -> dict[str, Any]:
        """
        检测文本的 AI 概率。

        Args:
            text: 待检测文本（建议 300-5000 字，与朱雀网页版一致）

        Returns:
            {"ai_probability": float, "verdict": str, "level": str}
        """
        if not text or len(text) < 50:
            return {"ai_probability": 0.0, "verdict": "人工", "level": "safe"}

        # 超过 512 token 的文本分段检测（模型最大窗口 512）
        segments = self._split_text(text, max_segment=400)
        segment_probs = []

        self._ensure_loaded()

        for seg in segments:
            prob = self._classify_segment(seg)
            segment_probs.append(prob)

        # 分段结果取最高值（朱雀检测策略——任意段可疑即整体可疑）
        max_prob = max(segment_probs)

        # 取均值（作为整体评估）
        avg_prob = sum(segment_probs) / len(segment_probs)

        level = self._classify_level(max_prob)
        verdict = self._classify_verdict(max_prob)

        return {
            "ai_probability": round(max_prob, 4),
            "average_probability": round(avg_prob, 4),
            "verdict": verdict,
            "level": level,
            "segments_checked": len(segment_probs),
            "segment_probs": segment_probs,
        }

    def _classify_segment(self, text: str) -> float:
        """对单个文本段分类，返回 AI 概率。"""
        inputs = self._tokenizer(
            text,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)[0]
        return float(probs[1].item())  # class 1 = AI-generated

    def _split_text(self, text: str, max_segment: int = 400) -> list[str]:
        """
        按段落/句子拆分文本。朱雀检测是按段落的，我们也按段落来。
        """
        # 按段落拆分
        paragraphs = re.split(r"\n\s*\n", text)

        segments: list[str] = []
        buffer = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果单段就够长，直接作为一段
            if len(para) >= max_segment * 0.8:
                if buffer:
                    segments.append(buffer)
                    buffer = ""
                segments.append(para)
            else:
                # 累积到 max_segment
                buffer += para + "\n"
                if len(buffer) >= max_segment:
                    segments.append(buffer)
                    buffer = ""

        if buffer:
            segments.append(buffer)

        return segments if segments else [text[:max_segment]]

    def _classify_level(self, prob: float) -> str:
        """根据概率分级。"""
        if prob < self.thresholds["safe"]:
            return "safe"
        elif prob < self.thresholds["suspect"]:
            return "suspect"
        elif prob < self.thresholds["likely_ai"]:
            return "likely_ai"
        else:
            return "confirmed_ai"

    def _classify_verdict(self, prob: float) -> str:
        """返回人类可读判定。"""
        if prob < 0.30:
            return "人工"
        elif prob < 0.50:
            return "可疑"
        elif prob < 0.80:
            return "很可能 AI"
        else:
            return "AI 生成"


# 全局单例（pipeline 共享）
_detector_instance: Optional[ZhuqueDetector] = None


def get_zhuque_detector() -> ZhuqueDetector:
    """获取全局共享的 zhuque 检测器实例。"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ZhuqueDetector()
    return _detector_instance


async def detect_ai_generation(text: str) -> dict[str, Any]:
    """
    快速入口：检测文本是否 AI 生成。

    Returns:
        {"ai_probability": float, "verdict": str, "level": str}
    """
    detector = get_zhuque_detector()
    return await detector.detect(text)


# CLI 测试
if __name__ == "__main__":
    async def _test():
        detector = ZhuqueDetector()

        # 测试 1：管道 de_ai 产出
        text1 = (
            "诺亚穿过半塌的拱门，靴子踩碎石，摩擦声刺耳。"
            "阳光从穹顶裂缝斜射下来，灰尘在地面投下一道道光柱。"
            "他蹲下身，手指划过五芒星纹路，冰凉粗糙。"
            "戒指里的声音忽然开口：一千年前，我亲手刻的。"
            "用元素共鸣锁住波动，压制成普通铁环。"
            "诺亚指尖一顿——那现在失效了？是。"
            "伊格尼斯的声音带点嘲讽——因为你进来了。"
            "前方是个圆形大厅，地面刻着复杂纹路。"
            "但纹路黯淡，边缘被裂痕切割得支离破碎。"
            "压制法阵？曾经是。这里不是什么遗迹。"
            "伊格的声音变得很轻——是我的墓地。"
        )

        # 测试 2：八股 AI 味
        text2 = (
            "首先主角来到了遗迹之中，他环顾四周发现墙壁上刻着古老的纹路，"
            "那些纹路从地面蔓延到穹顶。其次他注意到这些纹路非常精美。"
            "此外他还发现了一枚古老的戒指，上面刻着复杂的符文。"
            "值得注意的是这枚戒指似乎蕴含着强大的力量。"
            "总而言之这里隐藏着大量的秘密等待他去探索。"
        )

        for name, text in [("de_ai管道", text1), ("八股AI", text2)]:
            result = await detector.detect(text)
            print(f"{name}: {result}")

    asyncio.run(_test())
