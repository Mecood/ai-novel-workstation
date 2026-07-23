"""
Layer 6 创意组合引擎 — IdeaCombinator（创意种子随机组合器）+ PlotFramework（情节框架库）

IdeaCombinator: 从角色原型×场景类型×冲突类型×主题方向×结构框架随机抽取组合，
生成发给 AI 的创意激发 prompt。
PlotFramework: 6 种中文情节框架（英雄之旅/三幕结构/七点结构/环状叙事/双线并行/反向叙事）。
"""
import random
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# 创意维度常量（全中文）
# ─────────────────────────────────────────────────────────────────────────────
CHARACTER_ARCHETYPES = [
    "孤儿英雄 — 出身卑微或失去至亲，命中注定要成就非凡",
    "反英雄 — 道德灰色地带行走者，为达目的不择手段但内心有底线",
    "智谋型主角 — 不靠武力靠头脑，用计谋和知识扭转局势",
    "守护者 — 为保护某人/某物/某信念而战的忠诚战士",
    "双面间谍 — 游走在两大阵营之间，身份随时可能暴露",
    "觉醒的平凡者 — 普通人在极端事件中被逼出隐藏潜能",
]

SCENE_TYPES = [
    "暗巷追逐 — 狭窄空间里的紧张追逃，光影交错",
    "高塔对话 — 权力者居高临下的对话，压迫感十足",
    "荒野绝境 — 自然环境中的极限求生",
    "密室解谜 — 封闭空间内靠线索推进剧情",
    "市集交锋 — 人群中暗藏杀机，表面热闹实则暗流涌动",
    "深海/太空 — 极端环境放大人性弱点与光辉",
    "宫廷宴会 — 衣香鬓影下的政治角力",
    "废墟重生 — 毁灭后的希望萌芽，象征意味浓厚",
]

CONFLICT_TYPES = [
    "爱与责任的撕裂 — 想守护一个人却必须背叛更大的使命",
    "兄弟反目 — 曾经并肩的挚友因价值分歧走向对立",
    "身份暴露危机 — 秘密在关键时刻濒临曝光",
    "时间赛跑 — 必须在倒计时内完成不可能的任务",
    "道德困境 — 拯救多数人必须牺牲少数无辜者",
    "权力争夺 — 多方势力围绕一个核心资源血腥博弈",
    "记忆与真相 — 主角发现自己的记忆是被篡改过的",
    "文明碰撞 — 两种价值观/文化体系的正面冲突",
    "信仰崩塌 — 主角一直信奉的教条被发现是谎言",
    "两难抉择 — 无论选哪条路都会失去重要的东西",
]

THEME_DIRECTIONS = [
    "自由的代价 — 探讨获得真正自由需要付出什么牺牲",
    "身份的迷宫 — 我是谁？扮演的角色还是真实的自己？",
    "秩序与混沌 — 维持秩序还是拥抱混沌才能让世界更好",
    "时间的重量 — 过去的选择如何塑造现在，现在的选择如何影响未来",
    "人性的灰度 — 没有纯粹的黑与白，每个人都在灰色地带挣扎",
    "传承与断裂 — 新旧世代的价值冲突，该继承还是打破",
    "爱的暴力 — 以爱为名的控制与伤害更隐蔽也更致命",
    "沉默的代价 — 面对不公选择沉默，最终每个人都是共犯",
]

STRUCTURE_FRAMEWORKS = [
    "英雄之旅 — 12 步从平凡世界到王者归来",
    "三幕结构 — 建置/对抗/结局，经典好莱坞叙事骨架",
    "七点结构 — 钩子→转折1→中点→转折2→危机→高潮→解决",
    "环状叙事 — 开头即结尾，循环往复揭示更深真相",
    "双线并行 — 两条时间线/视角线交替推进，最终交汇",
    "反向叙事 — 从结局往前追溯，观众已知结果看角色如何走向必然",
]

# ─────────────────────────────────────────────────────────────────────────────
# 6 种情节框架（中文描述，内嵌常量）
# ─────────────────────────────────────────────────────────────────────────────
PLOT_FRAMEWORKS: dict[str, Any] = {
    "英雄之旅": {
        "name": "英雄之旅",
        "description": "约瑟夫·坎贝尔提出、克里斯托弗·沃格勒适配编剧的 12 步结构。主角从平凡世界出发，经历召唤→拒绝→导师→跨越阈限→试炼→接近洞穴→磨难→奖励→返回之路→重生→满载而归。",
        "steps": [
            {"step": 1, "name": "平凡世界", "desc": "展示主角在冒险前的日常生活与环境，建立对比基线"},
            {"step": 2, "name": "冒险召唤", "desc": "打破平衡的事件发生，主角被牵引进入旅程"},
            {"step": 3, "name": "拒绝召唤", "desc": "主角犹豫/恐惧，抗拒离开舒适区，增加张力和真实感"},
            {"step": 4, "name": "遇见导师", "desc": "导师出现，给予武器/知识/信心，推动主角迈出第一步"},
            {"step": 5, "name": "跨越第一阈限", "desc": "主角正式踏入特殊世界，无路可退，故事真正开始"},
            {"step": 6, "name": "试炼·盟友·敌人", "desc": "在新世界经受初步考验，结识盟友，辨认敌人"},
            {"step": 7, "name": "接近最深的洞穴", "desc": "接近核心危机所在地，紧张感攀升，准备终极对决"},
            {"step": 8, "name": "磨难", "desc": "面临最大恐惧/最残酷考验，看似失败/死亡，实为蜕变前夜"},
            {"step": 9, "name": "奖励（夺取宝剑）", "desc": "度过磨难后获得关键资源/能力/盟友/真相"},
            {"step": 10, "name": "返回之路", "desc": "带着奖励返回平凡世界，路上遭遇最后的追击/阻力"},
            {"step": 11, "name": "重生/复活", "desc": "在归途中经历二次净化/蜕变，旧我彻底死亡，新我诞生"},
            {"step": 12, "name": "满载而归", "desc": "将奖励/智慧/和平带回平凡世界，改变自己也改变他人"},
        ],
    },
    "三幕结构": {
        "name": "三幕结构",
        "description": "最经典、最通用的叙事骨架：第一幕建置（setup）→第二幕对抗（confrontation）→第三幕结局（resolution），每一幕承担不同的叙事功能。",
        "steps": [
            {"step": 1, "name": "建置", "desc": "介绍主角/世界/基调，埋下核心欲望与冲突种子。以激励事件结束——一件迫使主角无法回头的事"},
            {"step": 2, "name": "对抗", "desc": "主角主动对抗层层升级的障碍，局势不断恶化（'一坏再坏'）。中点出现虚假胜利或虚假失败。二幕尾跌入最低点——'一切尽失时刻'"},
            {"step": 3, "name": "结局", "desc": "从最低点反弹，主角找到新的力量/视角/盟友发起最终决战。高潮解决核心冲突，收束人物弧光与主题"},
        ],
    },
    "七点结构": {
        "name": "七点结构",
        "description": "由 Dan Wells 根据 Star Trek RPG 叙事引擎提炼的 7 个关键节点，强调从起点到终点的对称转折。",
        "steps": [
            {"step": 1, "name": "钩子", "desc": "开场即抓人，用一个反常/高张力/神秘的场景或状态吸引读者"},
            {"step": 2, "name": "转折点 1", "desc": "主角被从初始状态推出舒适区，主动或被动踏入冲突主线"},
            {"step": 3, "name": "中点", "desc": "迎来一次重大反转——看似胜利其实暗藏危机，或看似失败其实打开新路"},
            {"step": 4, "name": "转折点 2", "desc": "中点之后局势再度恶化，主角遭受最大打击（'一切尽失时刻'），旧策略彻底失效"},
            {"step": 5, "name": "危机", "desc": "最低点后的抉择时刻——主角必须在两条路中选择，选哪条都意味着牺牲"},
            {"step": 6, "name": "高潮", "desc": "主角做出抉择后全力一搏，所有支线汇聚，正面解决核心冲突"},
            {"step": 7, "name": "解决", "desc": "冲突平息后的新平衡状态，展示主角/世界的改变，点明主题"},
        ],
    },
    "环状叙事": {
        "name": "环状叙事",
        "description": "故事的开头与结尾形成闭环——结尾场景呼应/镜像开场，揭示隐藏信息使读者对开头产生全新理解。适合悬疑、宿命论、存在主义题材。",
        "steps": [
            {"step": 1, "name": "入环", "desc": "以一个看似平常但充满疑问/不安的场景开场（'这件事以前发生过'）"},
            {"step": 2, "name": "展开", "desc": "逐层展开事件的全貌，每次揭示更多背景，但保留一个核心谜团"},
            {"step": 3, "name": "裂变", "desc": "出现一个颠覆性信息/事件，让之前所有解读都变得可疑"},
            {"step": 4, "name": "回溯", "desc": "角色或叙事回到过去的关键节点重新审视，读者看到同一事件的另一面"},
            {"step": 5, "name": "闭环绕", "desc": "以呼应/反转/镜像开头场景的方式结束——开头那句话/那个人有了全新的含义"},
        ],
    },
    "双线并行": {
        "name": "双线并行",
        "description": "两条叙事线（不同时间/空间/视角）交替推进，各自有完整的悬念节奏，最终交汇产生化学反应。适合双主角、跨时空、Table vs Field 题材。",
        "steps": [
            {"step": 1, "name": "A线奠基", "desc": "建立 A 线主角/世界/核心冲突，让读者先投入一方"},
            {"step": 2, "name": "B线入局", "desc": "引入 B 线，可能与 A 线看似无关，但氛围/细节暗示有深层联系"},
            {"step": 3, "name": "交替攀升", "desc": "A/B 线交替推进，各自遭遇重大转折，开始出现交叉信号"},
            {"step": 4, "name": "第一次碰撞", "desc": "两条线在某个关键点首次直接交叉——可能是一个共享角色/同一事件的不同视角"},
            {"step": 5, "name": "双线合并", "desc": "A/B 线完全汇合，所有分立的伏笔在一个统一的高潮中引爆"},
        ],
    },
    "反向叙事": {
        "name": "反向叙事",
        "description": "从结局开始往前讲述，观众已知'结果'但不知道'为什么'。每一段往前的时间推进都揭示导致下一步的深层动机。适合悲剧、犯罪、溯源题材。",
        "steps": [
            {"step": 1, "name": "结局定格", "desc": "先展示最终状态——谁赢了/输了，谁还活着/已经死去"},
            {"step": 2, "name": "倒溯第一层", "desc": "跳到高潮前的一个关键节点，揭示是什么直接导致了结局"},
            {"step": 3, "name": "倒溯第二层", "desc": "再往前跳到更早的转折点，揭示更深层的因果链"},
            {"step": 4, "name": "源头揭示", "desc": "回到故事的最初起点——那个看似微不足道的选择/事件，展示它如何如多米诺骨牌般导致了结局"},
            {"step": 5, "name": "最终回望", "desc": "再次回到结局场景，观众此时的理解已截然不同——不再是'发生了什么'而是'为什么必然发生'"},
        ],
    },
}


class IdeaCombinator:
    """创意种子随机组合器 — 从 5 个维度随机抽取，组合成创意描述。"""

    DIMENSIONS = {
        "角色原型": CHARACTER_ARCHETYPES,
        "场景类型": SCENE_TYPES,
        "冲突类型": CONFLICT_TYPES,
        "主题方向": THEME_DIRECTIONS,
        "结构框架": STRUCTURE_FRAMEWORKS,
    }

    def combine(self, genre: str = "奇幻", complexity: str = "high") -> dict[str, Any]:
        """随机组合各维度元素，生成创意组合结果。

        Args:
            genre: 题材方向（影响组合的解释角度）
            complexity: 复杂程度（high / medium / low）

        Returns:
            {
                "genre": 题材,
                "complexity": 复杂程度,
                "combo": {维度名: 选中的元素},
                "idea_prompt": 发给 AI 的创意激发 prompt,
                "dimension_counts": {维度名: 可选数},
            }
        """
        combo = {}
        for dim_name, items in self.DIMENSIONS.items():
            combo[dim_name] = random.choice(items)

        idea_prompt = self.generate_idea_prompt(combo, genre, complexity)

        return {
            "genre": genre,
            "complexity": complexity,
            "combo": combo,
            "idea_prompt": idea_prompt,
            "dimension_counts": {name: len(items) for name, items in self.DIMENSIONS.items()},
        }

    def generate_idea_prompt(self, combo: dict[str, str], genre: str = "奇幻", complexity: str = "high") -> str:
        """根据组合结果生成发给 AI 的创意激发 prompt。

        Args:
            combo: 维度→选中元素的映射
            genre: 题材
            complexity: 复杂度

        Returns:
            一条中文 prompt 字符串
        """
        complexity_hint = {
            "high": "请设计至少3层伏笔、2条支线和1个贯穿始终的核心隐喻",
            "medium": "请设计1条主要支线和2个关键伏笔",
            "low": "请聚焦主线，设计1个核心伏笔即可",
        }.get(complexity, "请设计1条支线和1个伏笔")

        roles = combo.get("角色原型", "")
        scenes = combo.get("场景类型", "")
        conflicts = combo.get("冲突类型", "")
        themes = combo.get("主题方向", "")
        structures = combo.get("结构框架", "")

        prompt = (
            f"请基于以下创意组合，为【{genre}】题材生成一份完整的故事概念案（500-800字），包含：\n"
            f"1. 核心梗概（一句话）\n"
            f"2. 主角设定：{roles}\n"
            f"3. 核心冲突：{conflicts}\n"
            f"4. 主题锚点：{themes}\n"
            f"5. 叙事结构建议：{structures}\n"
            f"6. 最具张力的推荐场景：{scenes}\n"
            f"\n复杂度要求：{complexity}级 —— {complexity_hint}。"
        )
        return prompt


class PlotFramework:
    """情节框架库 — 6 种中文叙事框架的查询与概览。"""

    def get_framework(self, name: str) -> dict[str, Any] | None:
        """获取指定名称的框架完整信息（步骤 + 说明）。

        Args:
            name: 框架名称（如 "英雄之旅"、"三幕结构" 等）

        Returns:
            {name, description, steps: [{step, name, desc}]} 或 None
        """
        return PLOT_FRAMEWORKS.get(name)

    def get_all_frameworks(self) -> list[dict[str, Any]]:
        """返回所有框架的概览（不含详细步骤，仅 name + description + step_count）。

        Returns:
            框架概览列表
        """
        return [
            {
                "name": name,
                "description": framework["description"],
                "step_count": len(framework["steps"]),
            }
            for name, framework in PLOT_FRAMEWORKS.items()
        ]

    def list_framework_names(self) -> list[str]:
        """返回所有框架名称列表。"""
        return list(PLOT_FRAMEWORKS.keys())

    def recommend_for_genre(self, genre: str) -> list[str]:
        """根据题材推荐合适的框架。"""
        if not genre:
            return ["三幕结构", "英雄之旅"]

        genre_lower = genre.lower()
        # 悬疑/解谜/推理 → 环状/七点
        if any(w in genre_lower for w in ("悬疑", "灵异", "规则", "解谜", "犯罪", "侦探")):
            return ["环状叙事", "七点结构"]
        # 修仙/玄幻/高武 → 英雄之旅
        if any(w in genre_lower for w in ("修仙", "玄幻", "奇幻", "高武", "西幻")):
            return ["英雄之旅", "三幕结构"]
        # 言情/甜宠 → 双线/三幕
        if any(w in genre_lower for w in ("言情", "甜宠", "总裁", "甜", "甜文", "虐")):
            return ["双线并行", "三幕结构"]
        # 都市/脑洞/系统 → 七点
        if any(w in genre_lower for w in ("都市", "脑洞", "系统", "直播")):
            return ["七点结构", "三幕结构"]
        # 历史/年代 → 反向叙事/双线
        if any(w in genre_lower for w in ("历史", "年代", "抗战", "民国")):
            return ["双线并行", "反向叙事"]
        # 科幻/末世/无限流 → 英雄之旅/反向
        if any(w in genre_lower for w in ("科幻", "末世", "无限流", "系统")):
            return ["英雄之旅", "反向叙事"]

        return ["三幕结构", "七点结构"]