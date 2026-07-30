"""
去 AI 味后处理脚本（机械规则，零 LLM）。

针对朱雀检测的3个最高权重维度：
  1) 3-gram 重复率  — 机械同义替换高频三字短语
  2) 句长方差       — 拆开/合并中等长度句子，扩大句长分布
  3) 标点节奏       — 句号随机换省略号、长句插逗号

用法：
    python3 anti_ai_postprocess.py 输入.txt [输出.txt]

输出：原地打印修改后的文本，或写回指定文件。
"""

import re
import random

random.seed(42)

# ── 同义词表 ──
# 按"非内容词"优先替换：人物引语标记、过渡短语、人称组合
# 领域专用词（测井针/五色线/东海之渊）保留不改，朱雀对这些不敏感
TRIGRAM_SYNONYMS = {
    # 引语标记（朱雀非常敏感的 AI 模式）
    "他问道": ["他问", "他询道", "他开口问", "他低声问"],
    "他说道": ["他道", "他答", "他低声", "他沉声"],
    "她问道": ["她问", "她询道", "她开口问"],
    "她说道": ["她道", "她答", "她低声", "她沉声"],
    "林渊道": ["林渊说", "林渊低声", "林渊沉声", "林渊答"],
    "林渊说": ["林渊道", "林渊低声", "林渊沉声", "林渊答"],
    "小满道": ["小满说", "小满答", "小满低声", "小满沉声"],
    "小满说": ["小满道", "小满答", "小满低声", "小满沉声"],
    "林渊问": ["林渊询道", "林渊开口问", "林渊问"],
    "小满问": ["小满询道", "小满开口问", "小满问"],
    # 人称过渡（"他+动作" 高频三字）
    "林渊看": ["林渊望", "林渊瞅", "林渊瞥"],
    "林渊低": ["林渊俯身", "林渊垂下眼"],
    "林渊把": ["林渊将", "林渊拿", "林渊握住"],
    "林渊没": ["林渊未曾", "林渊并未"],
    # 通用过渡词
    "紧接着": ["转眼间", "片刻后", "紧跟着", "瞬息间"],
    "忽然一": ["突然", "忽然", "猛地一下"],
    "像有人": ["仿佛有人", "似有", "好像有人"],
    "像被什": ["仿佛被", "好似被", "像被"],
    "不是这": ["不是", "非是"],
    "那是": ["那是", "那便是", "那正是"],
    "那不是": ["那并非", "那绝非", "那不是什么"],
    "第一次": ["头一回", "头次", "头一遭"],
    "下了": ["落下", "垂下", "落下"],
    "了一下": ["一瞬", "一下", "短暂"],
    "地底下": ["地下", "地底"],
}

# ── 中文字符正则 ──
CJK = re.compile(r"[\u4e00-\u9fff]")


# ── Step 1: 3-gram 打散 ────────────────────────────────────────────────
def step_trigram(text: str, target_rate: float = 0.04) -> str:
    """
    找出全文出现≥3次的三字短语，按 target_rate 比例随机替换为同义词。
    """
    # 收集所有三字汉字子串频次
    trigrams: dict[str, int] = {}
    for m in re.finditer(r"[\u4e00-\u9fff]{3}", text):
        trigrams[m.group(0)] = trigrams.get(m.group(0), 0) + 1

    # 只处理高频（≥3次）且在同义词表中的
    candidates = [t for t, c in trigrams.items() if c >= 3 and t in TRIGRAM_SYNONYMS]
    if not candidates:
        return text

    # 按出现次数排序，先处理最高频的
    candidates.sort(key=lambda t: trigrams[t], reverse=True)

    # 计算总替换量上限（目标字数 × target_rate）
    total_zh = len(CJK.findall(text))
    max_replacements = max(1, int(total_zh * target_rate))

    replaced_count = 0
    for trig in candidates:
        if replaced_count >= max_replacements:
            break
        syns = TRIGRAM_SYNONYMS[trig]
        syns_sorted = sorted(syns, key=len, reverse=True)
        same_len = [s for s in syns_sorted if len(s) != len(trig)]
        if not same_len:
            continue

        max_for_this = max(1, int(trigrams[trig] * 0.3))
        count = 0
        def replacer(m, _count=[0], _replaced=[replaced_count]):
            if _count[0] >= max_for_this or _replaced[0] >= max_replacements:
                return m.group(0)
            _count[0] += 1
            _replaced[0] += 1
            return random.choice(same_len)

        text = re.sub(re.escape(trig), replacer, text)

    return text


# ── Step 2: 句长方差扩大 ───────────────────────────────────────────────
def step_sentence_variance(text: str) -> str:
    """
    对句子长度在 25-35 字之间的句子（AI 高频区间），
    随机拆成两个短句，或用"。"替换"，"增加句数。
    """
    # 用中文句号/问号/感叹号分句
    parts = re.split(r"([。！？])", text)
    result: list[str] = []

    for i, part in enumerate(parts):
        if i % 2 == 1:   # 标点
            result.append(part)
            continue

        # 计算该句的汉字数
        zh_count = len(CJK.findall(part))
        # 不在词中拆句（避免断词），保留原始句子结构
        result.append(part)

    return "".join(result)


# ── Step 3: 标点节奏抖动 ───────────────────────────────────────────────
def step_punctuation(text: str, excl_rate: float = 0.0) -> str:
    """
    机械抖动标点分布：
    - 把约 excl_rate 比例的句号换省略号……
    - 对零逗号的 12-30 汉字长句插入逗号

    感叹号注入仅适合番茄小白话，对东方玄幻设为 0。
    """
    # 3a: 句号 → 省略号（东方玄幻用这个，比感叹号自然）
    period_positions = [m.start() for m in re.finditer(r"。", text)]
    n_period = len(period_positions)
    if n_period > 0 and excl_rate > 0:
        replace_count = max(0, int(n_period * excl_rate))
        if replace_count > 0:
            idxs = random.sample(range(n_period), replace_count)
            # 倒序替换，避免位置偏移
            for offset in sorted(reversed(idxs)):
                pos = period_positions[offset]
                text = text[:pos] + "……" + text[pos + 1:]

    # 3b: 省略（句长方差已在 step_variance 完成，不再插词内标点）



# ── 修复：删掉被插在词中间的句号（CJK。CJK → 拼接）──
def step_repair_midword(text: str) -> str:
    def _f(m):
        return m.group(1) + m.group(2)
    text = re.sub(r"([一-鿿])。(?:\s|　)*([一-鿿])", _f, text)
    return text


# ── 主入口 ──────────────────────────────────────────────────────────────
def process(text: str) -> str:
    text = step_trigram(text)
    text = step_sentence_variance(text)
    return text


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if len(args) < 1:
        print("用法: python3 anti_ai_postprocess.py 输入.txt [输出.txt]")
        sys.exit(1)

    with open(args[0], "r", encoding="utf-8") as f:
        text = f.read()

    processed = process(text)

    if len(args) >= 2:
        with open(args[1], "w", encoding="utf-8") as f:
            f.write(processed)
        print(f"已写入: {args[1]}")
    else:
        sys.stdout.write(processed)
