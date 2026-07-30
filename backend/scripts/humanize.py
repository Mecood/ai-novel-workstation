"""
Human Novel Polisher — 纯规则机械润色脚本（零 LLM）。
将 AI 生成的小说段落润色成更接近真人作者的风格。

实现 12 条规则中的机械化部分（5、6、7、8、9、10、11、12 可直接规则化；
2、3、4、7 部分规则化）。LLM 重写阶段处理上下文相关的规则（1、4、8）。

用法：
    python3 humanize.py 输入.txt [输出.txt]

用法（管道）：
    echo "文本" | python3 humanize.py

输出：stdin → stdout 或 文件→文件。
"""

import re
import random
import sys
import json

random.seed(42)

CJK = re.compile(r"[\u4e00-\u9fff]")

# ─────────────────────────────────────────────────────────────────────────────
# Rule 5：删除 AI 连接词
# ─────────────────────────────────────────────────────────────────────────────
AI_CONNECTORS = [
    # (pattern, replacement)
    (r"紧接着(?:，|,)?", ""),
    (r"下一瞬(?:，|,)?", ""),
    (r"此刻(?:，|,)?", ""),
    (r"更怪的是(?:，|,)?", ""),
    (r"按理说(?:，|,)?", ""),
    (r"与此同时(?:，|,)?", ""),
    (r"就在这时(?:，|,)?", ""),
    (r"毫无疑问(?:，|,)?", ""),
    (r"显然(?:，|,)?", ""),
    (r"随后(?:，|,)?", ""),
    (r"突然之间(?:，|,)?", ""),
    # 部分：仅在句首时删除"然而/但"作为连接词
    # （保留"然而"在句中作转折用法）
    (r"(^|[。！？\n])然而(?:，|,)?", ""),
    (r"(^|[。！？\n])就在这时(?:，|,)?", ""),
]

def remove_connectors(text: str) -> str:
    for pat, repl in AI_CONNECTORS:
        text = re.sub(pat, repl, text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 5 + 词汇降重：把高度 AI 化的心理描写短语 → 简化 / 删除
# ─────────────────────────────────────────────────────────────────────────────
PSYCH_VERBS = [
    (r"眼神一沉", ""),
    (r"眉峰一紧", ""),
    (r"神色微变", ""),
    (r"瞳孔微缩", ""),
    (r"呼吸一滞", ""),
    (r"神色一凝", ""),
    (r"心中一震", ""),
    (r"心头一跳", ""),
    (r"心中一凛", ""),
    (r"眸中闪过", "目光一"),
    (r"神色凝重", ""),
    (r"目光一沉", ""),
    (r"脸上闪过", "脸上"),
    (r"眼中闪过", "眼中"),
]

def simplify_psych_verbs(text: str) -> str:
    for pat, repl in PSYCH_VERBS:
        text = re.sub(pat, repl, text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 8：把心理判断句改为动作句（已知映射）
# ─────────────────────────────────────────────────────────────────────────────
PSYCH_TO_ACTION = {
    r"林渊十分警惕[。]?$": [
        "林渊把石锥往袖子里推了半寸。",
        "林渊的手慢慢缩了回去。",
    ],
    r"林渊心中一紧[。]?$": [
        "林渊手指一收。",
        "林渊把手收回来。",
    ],
    r"她感到害怕[。]?$": [
        "她把手伸进袖子里。",
        "她低头没说话。",
    ],
    r"他皱了皱眉[。]?$": [
        "他没说话。",
        "他把目光移开。",
    ],
    r"他心中暗想[，,]": [""],
    r"他心中默念[，,]": [""],
    r"他在心中想[，,]": [""],
    r"他心想[，,]": [""],
}

def psych_to_action(text: str) -> str:
    for pat, repls in PSYCH_TO_ACTION.items():
        if repls:
            repl = random.choice(repls)
        else:
            repl = ""
        text = re.sub(pat, repl, text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 9：生活感对白注入（在纯叙述段之后插入一句口语）
# ─────────────────────────────────────────────────────────────────────────────
CASUAL_LINES = [
    "算了。",
    "不知道。",
    "行吧。",
    "真的假的？",
    "不会吧。",
    "哦。",
    "嗯。",
    "骗人。",
    "……",
    "你问这个干嘛。",
    "不知道啊。",
    "随你。",
    "反正我也不懂。",
    "你说话真难听。",
    "关你什么事。",
    "……不知道。",
]

# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 + Rule 7：注入生活感停顿（小动作 + 无推进信息）
# ─────────────────────────────────────────────────────────────────────────────
PAUSE_PATTERNS = [
    "他没说话。",
    "风从侧面刮过来。",
    "走了几步，又停下。",
    "低头看了一会儿。",
    "天有点阴了。",
    "沉默了一会儿。",
    "鞋底沾了些泥。",
    "远处好像有动静。",
    # 生活动作（脏）
    "他抓了抓耳朵。",
    "揉了一下虎口。",
    "脚踢开一块石头。",
    "鞋里进了水，他甩了甩脚。",
    "把衣领往上提了提。",
    "吐了一口咸水。",
    "他甩了甩手。",
    "蹲久了，腿麻了，站起来晃了一下。",
    "揉了揉鼻子，鼻尖都是盐，越抹越脏。",
    "他忽然觉得冷。",
    # 发呆/走神
    "他忽然想起师父说过的话，没记住，也懒得想了。",
    "林渊忽然想到师父。停了两秒。什么都没说。",
    "他愣了一会儿。不知道在想什么。",
    "看着远处发了一会儿呆。",
    "他忽然觉得累。不知道为什么。",
    "他坐了一会儿。什么都不干。",
    "林渊盯着地上那滩水，看了很久。",
    "他没动。风也停了一会儿。",
]


# ─────────────────────────────────────────────────────────────────────────────
# Rule 10：句长波动（打散过于均匀的句长）
# ─────────────────────────────────────────────────────────────────────────────
def perturb_sentence_length(text: str, seed: int = 7) -> str:
    """
    对句子按句末标点切分，对连续中等长度（18-28字）句子做以下操作：
    - 拆一句（在逗号处断成两句）
    - 合并两句（去掉句号，用逗号连）
    让句长分布更不均匀。
    """
    rng = random.Random(seed)
    sentences = re.split(r"([。！？])", text)
    result: list[str] = []

    i = 0
    while i < len(sentences):
        s = sentences[i]
        if i % 2 == 1:
            result.append(s)
            i += 1
            continue

        # 汉字长度
        zc = len(CJK.findall(s))
        rest = sentences[i + 1:i + 3]  # next punct + next content

        # 拆句：18-28 字 → 如果后面有逗号，拆
        if 18 <= zc <= 28 and rest and len(rest) >= 2:
            comma_idx = s.find("，")
            if comma_idx > 0:
                if rng.random() < 0.25:
                    before = s[:comma_idx]
                    after = s[comma_idx + 1:]
                    punct = rest[0]
                    result.append(before + "。")
                    result.append(after + punct)
                    i += 3
                    continue

        # 合并：连续两个短句（8-15字）→ 用逗号连
        if 8 <= zc <= 15 and rest and len(rest) >= 2:
            nxt = rest[1]
            nxt_zc = len(CJK.findall(nxt)) if isinstance(nxt, str) else 0
            if 8 <= nxt_zc <= 15:
                if rng.random() < 0.20:
                    punct0 = rest[0]
                    punct1 = rest[2] if len(rest) >= 3 else "。"
                    result.append(s + "," + nxt + punct1)
                    i += 3
                    continue

        result.append(s)
        i += 1

    return "".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 11 + 12：注入不确定语气（模糊化处理精确表达）
# ─────────────────────────────────────────────────────────────────────────────
PRECISION_TO_VAGUE = [
    (r"的确就是", "好像"),
    (r"必然是", "大概是"),
    (r"毫无疑问", "可能"),
    (r"绝对不可能", "应该不会有"),
    (r"完全确定", "差不多"),
    (r"确切地", "大概"),
    (r"清清楚楚", "模模糊糊"),
    (r"明明白白", "模模糊糊"),
]

def inject_vagueness(text: str) -> str:
    for pat, repl in PRECISION_TO_VAGUE:
        text = re.sub(pat, repl, text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 6：信息分散——把连在一起的密集介绍拆开（启发式）
# ─────────────────────────────────────────────────────────────────────────────
# 识别"人物一出现就写外貌+身份+动作"的密集段，在中间插入一句停顿
DENSE_INTRO_PATTERNS = [
    # "衣服xx，头发xx，眼睛xx" 连写
    (r"([\u4e00-\u9fff]{2,6}(?:衣裳|衣服|衣衫|长衫|布衣|短打))，([\u4e00-\u9fff]{2,6}(?:头发|发丝|发尾|发梢))",
     r"\g<1>。她头发颜色很旧了，\g<2>"),
    # "眼神x，声音x，身份x" 密集
    (r"([\u4e00-\u9fff]{2,6}眼神(?:x{0,2}))，([\u4e00-\u9fff]{2,6}声音(?:x{0,2}))，([\u4e00-\u9fff]{4,12}身份)",
     r"\g<1>。她说不出话来。她的\g<2>。\n\n\g<3>"),
]

def disperse_info(text: str) -> str:
    for pat, repl in DENSE_INTRO_PATTERNS:
        text = re.sub(pat, repl, text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3：段落节奏打乱（把连续短段落合并，把长段落插入空行）
# ─────────────────────────────────────────────────────────────────────────────
def perturb_paragraph_rhythm(text: str, seed: int = 13) -> str:
    """
    - 3 个以上连续短段（<30字）→ 合并 2 个
    - 超段（>200 字且无空行）→ 中间插入一个空行拆成两段
    """
    rng = random.Random(seed)
    lines = text.split("\n")
    result: list[str] = []

    # 合并连续短段
    i = 0
    while i < len(lines):
        l = lines[i]
        zh_len = len(CJK.findall(l))
        # 短段（3-28 字）且下一段也是短段 → 30% 概率合并
        if 3 <= zh_len <= 20 and i + 1 < len(lines):
            next_l = lines[i + 1]
            next_zh = len(CJK.findall(next_l))
            # 仅合并极短+相邻+无对话引号
            if 3 <= next_zh <= 20 and '“' not in l and '“' not in next_l and '”' not in l:
                if rng.random() < 0.05:
                    result.append(l + next_l)
                    i += 2
                    continue
        result.append(l)
        i += 1

    # 拆分超段
    final: list[str] = []
    for l in result:
        zh_len = len(CJK.findall(l))
        if zh_len > 200:
            mid = zh_len // 2
            # 找到第 mid 个汉字的位置
            pos = 0
            cnt = 0
            for j, ch in enumerate(l):
                if CJK.match(ch):
                    cnt += 1
                if cnt == mid:
                    pos = j + 1
                    break
            # 在前面找一个句号位置
            cut = pos
            for k in range(pos - 5, max(0, pos - 30), -1):
                if l[k] == "。":
                    cut = k + 1
                    break
            if cut != pos and cut > 10:
                final.append(l[:cut])
                final.append("")
                final.append(l[cut:])
            else:
                final.append(l)
        else:
            final.append(l)

    return "\n".join(final)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2：在段落之间注入无推进信息
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Rule 10：无效对白注入（在已有对话段之间插入一句无关闲聊）
# ─────────────────────────────────────────────────────────────────────────────
_INVALID_DLG = [
    '“你发解。”',
    '“再这样吧。”',
    '“关你什么事。”',
    '“其实不懂。”',
    '“说真的啊。”',
    '“随你。”',
    '“谢。”',
]


def inject_invalid_dialogue(text: str, rate: float = 0.03, seed: int = 23) -> str:
    """
    在已有对白之后，按 rate 概率插入一句无效闲聊。
    """
    rng = random.Random(seed)
    paras = text.split("\n\n")
    result = []
    recent_dlg = []
    for idx, p in enumerate(paras[:-1]):
        result.append(p)
        if '\u201c' in p and rng.random() < rate:
            # 在两个对话段之间插一句闲聊
            pool = [
                "\u201c\u4f60\u95ee\u8fd9\u4e2a\u5e72\u5565\u3002\u201d",
                "\u201c\u518d\u8fd9\u6837\u5427\u3002\u201d",
                "\u201c\u5173\u4f60\u4ec0\u4e48\u4e8b\u3002\u201d",
                "\u201c\u5426\u8ba4\u4e5f\u4e0d\u61c2\u3002\u201d",
                "\u201c\u8bf4\u771f\u53d7\u7528\u3002\u201d",
            ]
            # 用字符串，避免解码问题
            choice = rng.choice(pool)
            # 直接加
            if choice not in recent_dlg[-3:]:
                result.append(choice)
                recent_dlg.append(choice)
        result.append("")
    if paras:
        result.append(paras[-1])
    return "\n\n".join(result)


def inject_pauses(text: str, rate: float = 0.06, seed: int = 19) -> str:
    """
    在段落之间，按 rate 比例插入一句生活感停顿。
    使用滑动窗口避免同一停顿短时间内重复。
    """
    rng = random.Random(seed)
    paras = text.split("\n\n")
    result = []
    recent: list[str] = []
    WINDOW = 3
    for idx, p in enumerate(paras[:-1]):
        result.append(p)
        if rng.random() < rate:
            pool = [x for x in PAUSE_PATTERNS if x not in recent[-WINDOW:]]
            if pool:
                choice = rng.choice(pool)
                result.append(choice)
                recent.append(choice)
        result.append("")
    if paras:
        result.append(paras[-1])
    return "\n\n".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────
def process(text: str,
            remove_connectors_flag: bool = True,
            simplify_psych: bool = True,
            psych_to_action_flag: bool = True,
            sentence_length: bool = True,
            paragraph_rhythm: bool = True,
            do_inject_vagueness: bool = True,
            inject_pauses_flag: bool = True,
            ) -> str:
    # 1. 删除连接词（规则 5）
    if remove_connectors_flag:
        text = remove_connectors(text)

    # 2. 简化心理描写短语（规则 5 延伸）
    if simplify_psych:
        text = simplify_psych_verbs(text)

    # 3. 心理→动作（规则 8）
    if psych_to_action_flag:
        text = psych_to_action(text)

    # 4. 句长波动（规则 10）
    if sentence_length:
        text = perturb_sentence_length(text)

    # 5. 段落节奏打乱（规则 3）
    if paragraph_rhythm:
        text = perturb_paragraph_rhythm(text)

    # 6. 注入模糊语气（规则 11、12）
    if do_inject_vagueness:
        text = inject_vagueness(text)

    # 7. 信息分散（规则 6）
    text = disperse_info(text)

    # 8. 注入停顿/生活感（规则 2）
    if inject_pauses_flag:
        text = inject_pauses(text)

    # 9. 注入无效对白（规则 10）
    text = inject_invalid_dialogue(text)

    # 收尾：清理多余标点/空行
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"，。", "。", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 1:
        with open(args[0], "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    result = process(text)

    if len(args) >= 2:
        with open(args[1], "w", encoding="utf-8") as f:
            f.write(result)
        print(f"已写入: {args[1]}", file=sys.stderr)
    else:
        sys.stdout.write(result)
