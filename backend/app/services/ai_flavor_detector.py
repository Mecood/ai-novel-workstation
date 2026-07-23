"""AI味检测器 — 基于正则匹配+评分机制检测文本的AI痕迹。

返回结构：
{
    "score": 0-100,  # AI味分数，越高越像AI写的
    "level": "low" | "medium" | "high" | "severe",
    "issues": [
        {"type": "cliche_phrase", "text": "不禁", "line": 5, "suggestion": "替换为具体动作"},
        ...
    ],
    "stats": {
        "total_chars": 1234,
        "cliche_count": 8,
        "adverb_count": 15,
        "sentence_avg_len": 42,
        "paragraph_count": 12,
    }
}
"""
import re
from typing import Any


# AI八股词汇库 — 按严重程度分级
CLICHE_PHRASES = {
    # 严重（必扣分）
    "severe": [
        "一股暖流涌上心头", "心中暗想", "暗自思忖", "不自觉地",
        "嘴角微微上扬", "眼中闪过一丝", "微微一愣", "淡淡一笑",
        "缓缓说道", "轻声说道", "沉声说道", "冷冷说道",
        "若有所思", "意味深长", "不禁莞尔", "哑然失笑",
        "心如刀割", "心乱如麻", "百感交集", "五味杂陈",
        "他感到无比", "她感到一阵", "感到一股",
    ],
    # 中等（频繁出现才扣分）
    "medium": [
        "不禁", "仿佛", "宛如", "犹如", "似乎",
        "竟然", "居然", "顿时", "霎时", "蓦然",
        "微微", "轻轻", "淡淡", "缓缓", "徐徐",
        "深邃", "锐利", "犀利", "冰冷",
        "心中", "暗自", "不由得",
    ],
    # 轻微（大量出现才扣分）
    "low": [
        "说道", "笑道", "问道", "答道",
        "目光", "眼神", "神情",
        "转身", "回头", "点头", "摇头",
    ],
}

# AI典型句式模式
AI_SENTENCE_PATTERNS = [
    # "他/她感到 + 形容词 + 名词"
    (r"[他她]感到[一]?[股阵种][^\u3002\uff01\uff1b]+[。！]", "用具体反应代替'感到'句式"),
    # "不禁 + 动词"
    (r"不禁[微微轻轻淡淡缓缓]?\w{1,4}[，。]", "'不禁'是AI高频词，替换为具体动作"),
    # "心中 + 想法"
    (r"心中[暗]?[想道思忖觉][^\u3002\uff01\uff1b]+[。！]", "用动作/对话暗示心理，不直接写'心中想'"),
    # "一股/一阵 + 感受"
    (r"[一][股阵种][^\u3002\uff01\uff1b]*(涌上|袭来|传来|划过)", "避免'一股XX涌上'的AI八股"),
    # 连续形容词堆砌
    (r"[，、][\u4e00-\u9fa5]{2,4}的[\u4e00-\u9fa5]{2,4}的[\u4e00-\u9fa5]{2,4}的", "形容词堆砌，精简"),
]


def detect_ai_flavor(text: str) -> dict[str, Any]:
    """检测文本的AI味程度。

    Args:
        text: 小说章节正文

    Returns:
        检测结果字典，包含score、level、issues、stats
    """
    issues: list[dict] = []
    lines = text.split("\n")

    # --- 统计基础数据 ---
    total_chars = len(text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sentences = re.split(r"[。！？]", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

    # --- 检测八股词汇 ---
    cliche_count = 0
    for severity, phrases in CLICHE_PHRASES.items():
        for phrase in phrases:
            for i, line in enumerate(lines, 1):
                matches = re.findall(re.escape(phrase), line)
                for _ in matches:
                    cliche_count += 1
                    issues.append({
                        "type": "cliche_phrase",
                        "severity": severity,
                        "text": phrase,
                        "line": i,
                        "suggestion": _get_suggestion(phrase, severity),
                    })

    # --- 检测AI句式 ---
    for pattern, suggestion in AI_SENTENCE_PATTERNS:
        for i, line in enumerate(lines, 1):
            matches = re.finditer(pattern, line)
            for m in matches:
                issues.append({
                    "type": "ai_pattern",
                    "severity": "medium",
                    "text": m.group()[:20],
                    "line": i,
                    "suggestion": suggestion,
                })

    # --- 检测段落长度均匀度（AI写作特征：段落长度高度一致）---
    if len(paragraphs) >= 3:
        para_lens = [len(p) for p in paragraphs]
        avg_para_len = sum(para_lens) / len(para_lens)
        variance = sum((l - avg_para_len) ** 2 for l in para_lens) / len(para_lens)
        cv = (variance ** 0.5) / max(avg_para_len, 1)  # 变异系数
        if cv < 0.3:  # 段落长度过于均匀
            issues.append({
                "type": "uniform_paragraphs",
                "severity": "low",
                "text": f"段落长度变异系数={cv:.2f}",
                "line": 0,
                "suggestion": "段落长度过于均匀，增加长短变化",
            })

    # --- 检测对话模式（每句都带"说道"）---
    dialogue_markers = re.findall(r'[\uff0c,][\u201c"][^\u201d]+[\u201d"][\uff0c,]?\s*(\w{2,4}[道说问答喊叫嚷嘟囔])', text)
    if len(dialogue_markers) >= 3:
        ratio = len(dialogue_markers) / max(len(re.findall(r'[\u201c"]', text)), 1)
        if ratio > 0.5:
            issues.append({
                "type": "dialogue_monotony",
                "severity": "medium",
                "text": f"对话标记单调，{len(dialogue_markers)}处用'说道/问答'",
                "line": 0,
                "suggestion": "混用动作+语气词替代'说道'，如：他顿了顿、她叹了口气",
            })

    # --- 计算AI味分数 ---
    score = _calculate_score(issues, total_chars, avg_sentence_len, len(paragraphs))

    # --- 确定等级 ---
    if score >= 70:
        level = "severe"
    elif score >= 50:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    return {
        "score": round(score, 1),
        "level": level,
        "issues": issues[:50],  # 最多返回50条
        "stats": {
            "total_chars": total_chars,
            "cliche_count": cliche_count,
            "issue_count": len(issues),
            "sentence_avg_len": round(avg_sentence_len, 1),
            "paragraph_count": len(paragraphs),
        },
    }


def _get_suggestion(phrase: str, severity: str) -> str:
    """根据词汇给出替换建议。"""
    suggestions = {
        "一股暖流涌上心头": "换成具体身体反应，如'手指不自觉攥紧了衣角'",
        "心中暗想": "用动作暗示，如'他摸了摸下巴，没说话'",
        "暗自思忖": "用动作暗示，如'她咬着嘴唇，目光落在窗外'",
        "不自觉地": "删掉，直接写动作",
        "嘴角微微上扬": "换个更具体的笑法，如'咧嘴一笑'或'露出虎牙'",
        "眼中闪过一丝": "删掉，用动作代替",
        "缓缓说道": "删掉'缓缓'，或换成具体节奏，如'停了两秒才开口'",
        "若有所思": "用动作代替，如'手指在桌面上敲了两下'",
        "意味深长": "删掉，让读者自己体会",
        "不禁": "删掉或换成具体动作",
        "仿佛": "减少使用，或换成更具体的比喻",
        "微微": "删掉80%的'微微'",
        "轻轻": "删掉或换成更具体的动词",
        "淡淡": "删掉或换成具体描写",
        "缓缓": "换具体动词，如'挪''拖''蹭'",
    }
    if phrase in suggestions:
        return suggestions[phrase]
    if severity == "severe":
        return "这是AI高频词，建议替换或删除"
    if severity == "medium":
        return "频繁出现会暴露AI痕迹，建议减少使用"
    return "大量使用会显得不自然"


def _calculate_score(
    issues: list[dict],
    total_chars: int,
    avg_sentence_len: float,
    paragraph_count: int,
) -> float:
    """计算AI味综合分数 0-100。"""
    if total_chars == 0:
        return 0

    score = 0.0

    # 八股词汇按严重程度加权
    severe_count = sum(1 for i in issues if i.get("severity") == "severe")
    medium_count = sum(1 for i in issues if i.get("severity") == "medium")
    low_count = sum(1 for i in issues if i.get("severity") == "low")
    pattern_count = sum(1 for i in issues if i.get("type") == "ai_pattern")

    # 基础分 = 各类问题的加权总和（不乘密度系数，避免短文本爆分）
    score += severe_count * 12      # 每个严重问题 +12 分
    score += medium_count * 5       # 每个中等问题 +5 分
    score += low_count * 1          # 每个轻微问题 +1 分
    score += pattern_count * 8      # 每个AI句式 +8 分

    # 密度修正：问题数相对于文本量的密度
    issue_density = (severe_count + medium_count + low_count + pattern_count) / max(total_chars / 500, 1)
    density_bonus = min(issue_density * 5, 20)  # 最多加 20 分
    score += density_bonus

    # 段落均匀度扣分
    uniform_issues = sum(1 for i in issues if i.get("type") == "uniform_paragraphs")
    score += uniform_issues * 10

    # 对话单调扣分
    dialogue_issues = sum(1 for i in issues if i.get("type") == "dialogue_monotony")
    score += dialogue_issues * 10

    # 归一化到 0-100
    return min(score, 100)
