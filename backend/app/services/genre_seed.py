"""
题材模板种子数据 — 将裂变创作的 35+ 题材模板导入工作站。

每个模板含完整 config：
  pacing    — 节奏配置（字数、钩子密度、弧线）
  structure — 结构配置（章节数范围、卷结构）
  style     — 风格配置（语体、对话比、感官侧重）
  review    — 审查维度权重
  tropes    — 题材特有套路/爽点

运行方式（CLI）：
  cd backend && python -m app.services.genre_seed --apply

或作为 API 端点调用（POST /templates/seed）。
"""
import pathlib
import re
from datetime import datetime, timezone

# ── 35 大题材模板定义 ──────────────────────────────────────────────
# 来源：裂变创作 templates/genres/ 目录 + references/genre-profiles.md
# 每个模板的 pacing/structure/style/review 配置经人工核对，
# 符合当前网文市场（2026）的创作实践。

GENRE_CATEGORIES = {
    "男频": ["玄幻", "仙侠", "高武", "都市异能", "末世", "科幻", "游戏", "电竞",
             "西幻", "克苏鲁", "无限流", "系统流", "都市脑洞", "历史脑洞",
             "抗战谍战", "都市日常", "职场婚恋"],
    "女频": ["古言", "宫斗宅斗", "幻想言情", "青春甜宠", "民国言情", "豪门总裁",
             "现言脑洞", "替身文", "狗血言情", "女频悬疑", "种田"],
    "悬疑/规则": ["悬疑灵异", "悬疑脑洞", "规则怪谈", "黑暗题材"],
    "现实/年代": ["现实题材", "年代", "历史古代"],
    "创新/复合": ["多子多福", "直播文", "知乎短篇"],
}

def _flat():
    """展平为 {题材: 类别} 映射。"""
    out = {}
    for cat, genres in GENRE_CATEGORIES.items():
        for g in genres:
            out[g] = cat
    return out

GENRE_CATEGORY_MAP = _flat()

# ── 题材模板数据 ──────────────────────────────────────────────────
# 每个模板：config 结构见 GenreTemplate.config_schema
GENRE_TEMPLATES = [
    {
        "name": "仙侠",
        "config": {
            "pacing": {"typical_chapter_word_count": 3000, "min_hook_per_chapter": 2,
                       "recommended_arcs": 8, "first_arc_chapters": 30,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [2000, 6000],
                          "chapter_count_range": [200, 600],
                          "volume_count_range": [8, 20]},
            "style": {"vocabulary": "文白夹杂偏白", "combat_scene_ratio": 0.35,
                      "dialogue_ratio": 0.25, "sensory_focus": ["visual", "tactile"],
                      "key_motifs": ["法宝", "灵脉", "渡劫", "闭关"]},
            "review": {"key_dimensions": ["境界压制", "战力崩坏", "因果合理性"],
                       "weight_overrides": {"coolpoint_density": 1.0, "power_consistency": 1.5}},
            "tropes": ["扮猪吃虎", "越级挑战", "机缘夺宝", "宗门崛起", "无敌流"],
        },
    },
    {
        "name": "玄幻",
        "config": {
            "pacing": {"typical_chapter_word_count": 2800, "min_hook_per_chapter": 2,
                       "recommended_arcs": 6, "first_arc_chapters": 25,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [2000, 5500],
                          "chapter_count_range": [150, 500],
                          "volume_count_range": [6, 15]},
            "style": {"vocabulary": "偏白", "combat_scene_ratio": 0.4,
                      "dialogue_ratio": 0.2, "sensory_focus": ["visual", "kinetic"],
                      "key_motifs": ["血脉", "秘境", "神祇", "王座"]},
            "review": {"key_dimensions": ["世界观一致性", "力量体系", "战力崩坏"],
                       "weight_overrides": {"coolpoint_density": 0.9, "power_consistency": 1.5}},
            "tropes": ["废柴逆袭", "远古血脉", "神祇苏醒", "跨界降临"],
        },
    },
    {
        "name": "高武",
        "config": {
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 2,
                       "recommended_arcs": 6, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [2000, 5000],
                          "chapter_count_range": [100, 300],
                          "volume_count_range": [5, 12]},
            "style": {"vocabulary": "偏白", "combat_scene_ratio": 0.45,
                      "dialogue_ratio": 0.15, "sensory_focus": ["kinetic", "visual"],
                      "key_motifs": ["武道", "气血", "宗师", "境界"]},
            "review": {"key_dimensions": ["武力升级逻辑", "武道境界压制"],
                       "weight_overrides": {"coolpoint_density": 1.1, "power_consistency": 1.3}},
            "tropes": ["少年武道天才", "气血如龙", "宗师对决", "武道高考"],
        },
    },
    {
        "name": "都市异能",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.3,
                      "dialogue_ratio": 0.35, "sensory_focus": ["visual", "urban"],
                      "key_motifs": ["异能觉醒", "异能者", "都市传说", "暗网"]},
            "review": {"key_dimensions": ["异能逻辑", "都市背景一致性"],
                       "weight_overrides": {"coolpoint_density": 0.8, "character_depth": 1.0}},
            "tropes": ["异能觉醒", "扮猪吃虎", "暗夜猎手", "能力进化"],
        },
    },
    {
        "name": "末世",
        "config": {
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 2,
                       "recommended_arcs": 5, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [2000, 5000],
                          "chapter_count_range": [100, 300],
                          "volume_count_range": [5, 12]},
            "style": {"vocabulary": "偏白", "combat_scene_ratio": 0.4,
                      "dialogue_ratio": 0.2, "sensory_focus": ["tactile", "kinetic"],
                      "key_motifs": ["丧尸", "避难所", "物资", "变异"]},
            "review": {"key_dimensions": ["生存逻辑", "物资平衡", "人性刻画"],
                       "weight_overrides": {"coolpoint_density": 0.9, "survival_consistency": 1.3}},
            "tropes": ["末世重生", "空间异能", "避难所建设", "人比鬼可怕"],
        },
    },
    {
        "name": "科幻",
        "config": {
            "pacing": {"typical_chapter_word_count": 2800, "min_hook_per_chapter": 1,
                       "recommended_arcs": 6, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [2000, 5500],
                          "chapter_count_range": [100, 300],
                          "volume_count_range": [5, 12]},
            "style": {"vocabulary": "偏白", "combat_scene_ratio": 0.25,
                      "dialogue_ratio": 0.3, "sensory_focus": ["visual", "conceptual"],
                      "key_motifs": ["星际", "机甲", "AI", "平行宇宙"]},
            "review": {"key_dimensions": ["科技逻辑", "世界观自洽"],
                       "weight_overrides": {"setting_consistency": 1.5, "timeline": 1.0}},
            "tropes": ["星际争霸", "机甲觉醒", "时间循环", "文明升级"],
        },
    },
    {
        "name": "系统流",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.3,
                      "dialogue_ratio": 0.3, "sensory_focus": ["visual"],
                      "key_motifs": ["系统面板", "任务", "奖励", "属性"]},
            "review": {"key_dimensions": ["系统规则一致性", "数值崩坏"],
                       "weight_overrides": {"coolpoint_density": 1.0, "system_logic": 1.3}},
            "tropes": ["签到系统", "升级系统", "任务强制", "系统BUG"],
        },
    },
    {
        "name": "游戏",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 18,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [100, 300],
                          "volume_count_range": [5, 12]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.35,
                      "dialogue_ratio": 0.3, "sensory_focus": ["visual", "kinetic"],
                      "key_motifs": ["副本", "装备", "排行榜", "公会"]},
            "review": {"key_dimensions": ["游戏机制", "数值平衡"],
                       "weight_overrides": {"coolpoint_density": 1.0, "game_logic": 1.3}},
            "tropes": ["满级大佬", "唯一隐藏职业", "游戏入侵现实"],
        },
    },
    {
        "name": "电竞",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [80, 200],
                          "volume_count_range": [4, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.45,
                      "dialogue_ratio": 0.4, "sensory_focus": ["kinetic", "visual"],
                      "key_motifs": ["职业联赛", "战队", "训练赛", "巅峰对决"]},
            "review": {"key_dimensions": ["竞技逻辑", "技术细节", "团队配合"],
                       "weight_overrides": {"coolpoint_density": 0.8, "technical_accuracy": 1.5}},
            "tropes": ["天才回归", "逆风翻盘", "巅峰赛事", "队友羁绊"],
        },
    },
    {
        "name": "西幻",
        "config": {
            "pacing": {"typical_chapter_word_count": 2800, "min_hook_per_chapter": 1,
                       "recommended_arcs": 6, "first_arc_chapters": 25,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [2000, 5500],
                          "chapter_count_range": [100, 350],
                          "volume_count_range": [6, 15]},
            "style": {"vocabulary": "半文半白", "combat_scene_ratio": 0.35,
                      "dialogue_ratio": 0.3, "sensory_focus": ["visual", "tactile"],
                      "key_motifs": ["王国", "魔法学院", "种族", "教廷"]},
            "review": {"key_dimensions": ["魔法体系", "世界观", "政治逻辑"],
                       "weight_overrides": {"setting_consistency": 1.3, "character_depth": 1.0}},
            "tropes": ["魔法学院", "龙与勇者", "穿越异世界", "魔法觉醒"],
        },
    },
    {
        "name": "克苏鲁",
        "config": {
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [2000, 5000],
                          "chapter_count_range": [80, 200],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "偏文", "combat_scene_ratio": 0.15,
                      "dialogue_ratio": 0.25, "sensory_focus": ["tactile", "psychological"],
                      "key_motifs": ["SAN值", "旧日支配者", "理智", "禁忌知识"]},
            "review": {"key_dimensions": ["氛围营造", "sanity系统", "世界观恐怖逻辑"],
                       "weight_overrides": {"atmosphere": 1.5, "character_depth": 1.0}},
            "tropes": ["SAN值狂掉", "疯狂与理智", "不可名状", "克系召唤"],
        },
    },
    {
        "name": "无限流",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 10,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [2000, 4500],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.4,
                      "dialogue_ratio": 0.3, "sensory_focus": ["kinetic", "psychological"],
                      "key_motifs": ["副本", "主神空间", "任务", "积分"]},
            "review": {"key_dimensions": ["副本逻辑", "任务可行性", "人物成长"],
                       "weight_overrides": {"coolpoint_density": 1.0, "mission_logic": 1.5}},
            "tropes": ["主神召唤", "新手试炼", "队友背叛", "副本BUG"],
        },
    },
    {
        "name": "都市脑洞",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 12,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [60, 200],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.2,
                      "dialogue_ratio": 0.4, "sensory_focus": ["visual", "psychological"],
                      "key_motifs": ["脑洞", "金手指", "打脸", "爽点"]},
            "review": {"key_dimensions": ["脑洞合理性", "爽点节奏"],
                       "weight_overrides": {"coolpoint_density": 1.2, "hook_strength": 1.1}},
            "tropes": ["脑补帝", "全民系统", "反套路", "脑洞大开"],
        },
    },
    {
        "name": "历史脑洞",
        "config": {
            "pacing": {"typical_chapter_word_count": 2600, "min_hook_per_chapter": 1,
                       "recommended_arcs": 6, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [2000, 5000],
                          "chapter_count_range": [100, 300],
                          "volume_count_range": [5, 12]},
            "style": {"vocabulary": "半文半白", "combat_scene_ratio": 0.35,
                      "dialogue_ratio": 0.35, "sensory_focus": ["visual", "historical"],
                      "key_motifs": ["穿越", "历史人物", "朝代", "谋略"]},
            "review": {"key_dimensions": ["历史合理性", "时代细节"],
                       "weight_overrides": {"setting_consistency": 1.5, "character_depth": 1.0}},
            "tropes": ["穿越改变历史", "历史名人", "种田强国", "权谋"],
        },
    },
    {
        "name": "历史古代",
        "config": {
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1,
                       "recommended_arcs": 6, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [2000, 5000],
                          "chapter_count_range": [100, 300],
                          "volume_count_range": [5, 12]},
            "style": {"vocabulary": "半文半白", "combat_scene_ratio": 0.3,
                      "dialogue_ratio": 0.4, "sensory_focus": ["visual", "historical"],
                      "key_motifs": ["朝代", "官场", "江湖", "家国"]},
            "review": {"key_dimensions": ["时代考据", "人物言行", "礼制规范"],
                       "weight_overrides": {"setting_consistency": 1.5, "historical_accuracy": 1.3}},
            "tropes": ["朝堂权谋", "江湖恩怨", "家国情怀", "武将逆袭"],
        },
    },
    {
        "name": "抗战谍战",
        "config": {
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 18,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [2000, 4800],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.4,
                      "dialogue_ratio": 0.35, "sensory_focus": ["kinetic", "psychological"],
                      "key_motifs": ["潜伏", "密码", "身份", "信念"]},
            "review": {"key_dimensions": ["谍战逻辑", "身份伪装", "时代细节"],
                       "weight_overrides": {"plot_logic": 1.3, "character_depth": 1.1}},
            "tropes": ["身份双重", "暗号密码", "潜伏卧底", "家国大义"],
        },
    },
    {
        "name": "都市日常",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [60, 180],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.05,
                      "dialogue_ratio": 0.5, "sensory_focus": ["tactile", "urban"],
                      "key_motifs": ["生活", "日常", "小确幸", "烟火气"]},
            "review": {"key_dimensions": ["情感真实", "细节考据"],
                       "weight_overrides": {"character_depth": 1.3, "emotion_authenticity": 1.2}},
            "tropes": ["慢生活", "治愈系", "人间烟火", "邻里关系"],
        },
    },
    {
        "name": "职场婚恋",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [60, 180],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.1,
                      "dialogue_ratio": 0.55, "sensory_focus": ["psychological", "visual"],
                      "key_motifs": ["职场", "爱情", "婚嫁", "成长"]},
            "review": {"key_dimensions": ["情感真实", "职场逻辑"],
                       "weight_overrides": {"character_depth": 1.3, "emotion_authenticity": 1.2}},
            "tropes": ["职场逆袭", "先婚后爱", "办公室恋情", "女性成长"],
        },
    },
    {
        "name": "古言",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "半文半白偏文", "combat_scene_ratio": 0.1,
                      "dialogue_ratio": 0.45, "sensory_focus": ["visual", "emotional"],
                      "key_motifs": ["宫阙", "公子", "闺阁", "琴书"]},
            "review": {"key_dimensions": ["时代考据", "情感刻画", "礼制"],
                       "weight_overrides": {"character_depth": 1.3, "emotion_authenticity": 1.2}},
            "tropes": ["权谋宅斗", "先婚后爱", "双向奔赴", "身份错位"],
        },
    },
    {
        "name": "宫斗宅斗",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "半文半白", "combat_scene_ratio": 0.05,
                      "dialogue_ratio": 0.5, "sensory_focus": ["psychological", "visual"],
                      "key_motifs": ["宫廷", "后宅", "阴谋", "权力"]},
            "review": {"key_dimensions": ["权谋逻辑", "情感刻画", "礼制"],
                       "weight_overrides": {"plot_logic": 1.3, "character_depth": 1.2}},
            "tropes": ["入宫夺嫡", "宅斗争宠", "逆袭上位", "智斗"],
        },
    },
    {
        "name": "幻想言情",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 18,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "偏文", "combat_scene_ratio": 0.15,
                      "dialogue_ratio": 0.45, "sensory_focus": ["visual", "emotional"],
                      "key_motifs": ["仙侠", "言情", "前世今生", "宿命"]},
            "review": {"key_dimensions": ["情感真实", "世界观"],
                       "weight_overrides": {"character_depth": 1.3, "emotion_authenticity": 1.2}},
            "tropes": ["仙侠言情", "三世情缘", "宿敌变情人", "双向救赎"],
        },
    },
    {
        "name": "青春甜宠",
        "config": {
            "pacing": {"typical_chapter_word_count": 2000, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 12,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1500, 4000],
                          "chapter_count_range": [50, 150],
                          "volume_count_range": [3, 6]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.02,
                      "dialogue_ratio": 0.6, "sensory_focus": ["emotional", "visual"],
                      "key_motifs": ["校园", "甜宠", "初恋", "成长"]},
            "review": {"key_dimensions": ["情感真实", "人物成长"],
                       "weight_overrides": {"emotion_authenticity": 1.2, "character_depth": 1.0}},
            "tropes": ["校园初恋", "欢喜冤家", "双向奔赴", "甜度超标"],
        },
    },
    {
        "name": "民国言情",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 18,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [80, 220],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "半文半白", "combat_scene_ratio": 0.15,
                      "dialogue_ratio": 0.45, "sensory_focus": ["visual", "emotional"],
                      "key_motifs": ["民国", "爱情", "家国", "风云"]},
            "review": {"key_dimensions": ["时代考据", "情感刻画"],
                       "weight_overrides": {"setting_consistency": 1.3, "character_depth": 1.2}},
            "tropes": ["乱世情缘", "家族恩怨", "家国大义", "乱世佳人"],
        },
    },
    {
        "name": "豪门总裁",
        "config": {
            "pacing": {"typical_chapter_word_count": 2000, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 12,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1500, 4000],
                          "chapter_count_range": [50, 150],
                          "volume_count_range": [3, 6]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.05,
                      "dialogue_ratio": 0.5, "sensory_focus": ["visual", "emotional"],
                      "key_motifs": ["豪门", "总裁", "契约", "真爱"]},
            "review": {"key_dimensions": ["情感真实", "豪门设定"],
                       "weight_overrides": {"character_depth": 1.0, "emotion_authenticity": 1.1}},
            "tropes": ["先婚后爱", "契约婚姻", "身份反差", "真爱至上"],
        },
    },
    {
        "name": "现言脑洞",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 12,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [50, 180],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.1,
                      "dialogue_ratio": 0.5, "sensory_focus": ["visual", "psychological"],
                      "key_motifs": ["脑洞", "金手指", "反套路", "爽点"]},
            "review": {"key_dimensions": ["脑洞合理性", "爽点节奏"],
                       "weight_overrides": {"coolpoint_density": 1.1, "hook_strength": 1.1}},
            "tropes": ["脑洞大开", "反套路", "金手指", "女主逆袭"],
        },
    },
    {
        "name": "替身文",
        "config": {
            "pacing": {"typical_chapter_word_count": 2000, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 12,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1500, 4000],
                          "chapter_count_range": [50, 150],
                          "volume_count_range": [3, 6]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.02,
                      "dialogue_ratio": 0.5, "sensory_focus": ["emotional", "psychological"],
                      "key_motifs": ["替身", "白月光", "虐", "反转"]},
            "review": {"key_dimensions": ["情感真实", "虐点节奏", "反转力度"],
                       "weight_overrides": {"emotion_authenticity": 1.2, "hook_strength": 1.0}},
            "tropes": ["白月光替身", "虐恋情深", "身份反转", "追妻火葬场"],
        },
    },
    {
        "name": "狗血言情",
        "config": {
            "pacing": {"typical_chapter_word_count": 2000, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 12,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [1500, 4000],
                          "chapter_count_range": [50, 150],
                          "volume_count_range": [3, 6]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.05,
                      "dialogue_ratio": 0.55, "sensory_focus": ["emotional"],
                      "key_motifs": ["误会", "虐", "反转", "虐心"]},
            "review": {"key_dimensions": ["虐点节奏", "情感真实"],
                       "weight_overrides": {"emotion_authenticity": 1.1, "hook_strength": 1.0}},
            "tropes": ["虐恋情深", "误会重重", "反转打脸", "虐心虐肺"],
        },
    },
    {
        "name": "女频悬疑",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [60, 180],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.2,
                      "dialogue_ratio": 0.4, "sensory_focus": ["psychological", "visual"],
                      "key_motifs": ["悬疑", "推理", "情感", "真相"]},
            "review": {"key_dimensions": ["剧情逻辑", "伏笔回收", "情感真实"],
                       "weight_overrides": {"plot_logic": 1.3, "character_depth": 1.1}},
            "tropes": ["身份秘密", "情感悬疑", "真相揭露", "反转"],
        },
    },
    {
        "name": "种田",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [100, 350],
                          "volume_count_range": [5, 15]},
            "style": {"vocabulary": "半文半白偏白", "combat_scene_ratio": 0.1,
                      "dialogue_ratio": 0.4, "sensory_focus": ["tactile", "visual"],
                      "key_motifs": ["农家", "经营", "田园", "致富"]},
            "review": {"key_dimensions": ["经济逻辑", "时代考据", "人物成长"],
                       "weight_overrides": {"setting_consistency": 1.3, "character_depth": 1.0}},
            "tropes": ["种田致富", "农家生活", "空间种田", "年代发家"],
        },
    },
    {
        "name": "悬疑灵异",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [80, 220],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.25,
                      "dialogue_ratio": 0.35, "sensory_focus": ["psychological", "visual"],
                      "key_motifs": ["灵异", "破案", "真相", "超自然"]},
            "review": {"key_dimensions": ["剧情逻辑", "氛围营造"],
                       "weight_overrides": {"plot_logic": 1.3, "atmosphere": 1.3}},
            "tropes": ["灵异破案", "阴阳眼", "诡事奇案", "真相揭秘"],
        },
    },
    {
        "name": "悬疑脑洞",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [60, 200],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.25,
                      "dialogue_ratio": 0.4, "sensory_focus": ["psychological", "visual"],
                      "key_motifs": ["脑洞", "悬疑", "反转", "真相"]},
            "review": {"key_dimensions": ["剧情逻辑", "脑洞合理性"],
                       "weight_overrides": {"plot_logic": 1.3, "coolpoint_density": 1.0}},
            "tropes": ["脑洞悬疑", "反转连连", "身份谜团", "真相反转"],
        },
    },
    {
        "name": "规则怪谈",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 3},
            "structure": {"chapter_word_count_range": [1800, 4500],
                          "chapter_count_range": [60, 180],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.2,
                      "dialogue_ratio": 0.35, "sensory_focus": ["psychological", "visual"],
                      "key_motifs": ["规则", "诡异", "生存", "推理"]},
            "review": {"key_dimensions": ["规则逻辑", "氛围营造", "生存逻辑"],
                       "weight_overrides": {"atmosphere": 1.5, "plot_logic": 1.3}},
            "tropes": ["规则生存", "诡异副本", "逻辑破局", "San值下降"],
        },
    },
    {
        "name": "黑暗题材",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [2000, 4800],
                          "chapter_count_range": [80, 220],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "偏文", "combat_scene_ratio": 0.3,
                      "dialogue_ratio": 0.3, "sensory_focus": ["psychological", "tactile"],
                      "key_motifs": ["黑暗", "人性", "挣扎", "深渊"]},
            "review": {"key_dimensions": ["深度刻画", "氛围营造"],
                       "weight_overrides": {"atmosphere": 1.3, "character_depth": 1.3}},
            "tropes": ["人性深渊", "黑暗成长", "善恶博弈", "黑暗反转"],
        },
    },
    {
        "name": "现实题材",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [1800, 4500],
                          "chapter_count_range": [60, 180],
                          "volume_count_range": [3, 8]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.1,
                      "dialogue_ratio": 0.45, "sensory_focus": ["tactile", "psychological"],
                      "key_motifs": ["现实", "社会", "生活", "奋斗"]},
            "review": {"key_dimensions": ["真实性", "情感刻画"],
                       "weight_overrides": {"character_depth": 1.3, "emotion_authenticity": 1.3}},
            "tropes": ["现实逆袭", "小人物奋斗", "社会话题", "生活真实"],
        },
    },
    {
        "name": "年代",
        "config": {
            "pacing": {"typical_chapter_word_count": 2400, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 20,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [1800, 4800],
                          "chapter_count_range": [100, 300],
                          "volume_count_range": [5, 12]},
            "style": {"vocabulary": "半文半白偏白", "combat_scene_ratio": 0.1,
                      "dialogue_ratio": 0.45, "sensory_focus": ["tactile", "historical"],
                      "key_motifs": ["年代", "致富", "时代", "家庭"]},
            "review": {"key_dimensions": ["时代考据", "经济逻辑", "家庭情感"],
                       "weight_overrides": {"setting_consistency": 1.3, "character_depth": 1.1}},
            "tropes": ["年代发家", "穿越致富", "家庭伦理", "时代变迁"],
        },
    },
    {
        "name": "多子多福",
        "config": {
            "pacing": {"typical_chapter_word_count": 2200, "min_hook_per_chapter": 1,
                       "recommended_arcs": 5, "first_arc_chapters": 15,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [1500, 4500],
                          "chapter_count_range": [80, 250],
                          "volume_count_range": [4, 10]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.25,
                      "dialogue_ratio": 0.4, "sensory_focus": ["visual", "emotional"],
                      "key_motifs": ["子嗣", "血脉", "传承", "家族"]},
            "review": {"key_dimensions": ["设定一致性", "爽点节奏"],
                       "weight_overrides": {"coolpoint_density": 1.0, "character_depth": 0.9}},
            "tropes": ["子嗣增益", "血脉传承", "家族崛起", "子孙满堂"],
        },
    },
    {
        "name": "直播文",
        "config": {
            "pacing": {"typical_chapter_word_count": 2000, "min_hook_per_chapter": 1,
                       "recommended_arcs": 4, "first_arc_chapters": 12,
                       "coolpoint_interval_chapters": 2},
            "structure": {"chapter_word_count_range": [1500, 4000],
                          "chapter_count_range": [50, 150],
                          "volume_count_range": [3, 6]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.2,
                      "dialogue_ratio": 0.5, "sensory_focus": ["visual", "kinetic"],
                      "key_motifs": ["直播", "弹幕", "粉丝", "流量"]},
            "review": {"key_dimensions": ["直播逻辑", "爽点节奏"],
                       "weight_overrides": {"coolpoint_density": 1.0, "hook_strength": 1.1}},
            "tropes": ["直播逆袭", "弹幕互动", "粉丝打榜", "流量爆红"],
        },
    },
    {
        "name": "知乎短篇",
        "config": {
            "pacing": {"typical_chapter_word_count": 800, "min_hook_per_chapter": 1,
                       "recommended_arcs": 3, "first_arc_chapters": 1,
                       "coolpoint_interval_chapters": 1},
            "structure": {"chapter_word_count_range": [1000, 15000],
                          "chapter_count_range": [1, 1],
                          "volume_count_range": [1, 1],
                          "total_target_words": [5000, 15000]},
            "style": {"vocabulary": "现代白话", "combat_scene_ratio": 0.2,
                      "dialogue_ratio": 0.4, "sensory_focus": ["emotional", "visual"],
                      "key_motifs": ["第一人称", "反转", "现实", "情感"]},
            "review": {"key_dimensions": ["开头抓人", "反转力度", "情感共鸣"],
                       "weight_overrides": {"hook_strength": 1.5, "emotion_authenticity": 1.2,
                                            "payoff_satisfaction": 1.3}},
            "tropes": ["第一人称叙事", "反转打脸", "情感共鸣", "短篇完本"],
        },
    },
    {
        "name": "西幻",
        "config": {
            "pacing": {"typical_chapter_word_count": 2800, "min_hook_per_chapter": 1,
                       "recommended_arcs": 6, "first_arc_chapters": 25,
                       "coolpoint_interval_chapters": 4},
            "structure": {"chapter_word_count_range": [2000, 5500],
                          "chapter_count_range": [100, 350],
                          "volume_count_range": [6, 15]},
            "style": {"vocabulary": "半文半白", "combat_scene_ratio": 0.35,
                      "dialogue_ratio": 0.3, "sensory_focus": ["visual", "tactile"],
                      "key_motifs": ["王国", "魔法学院", "种族", "教廷"]},
            "review": {"key_dimensions": ["魔法体系", "世界观", "政治逻辑"],
                       "weight_overrides": {"setting_consistency": 1.3, "character_depth": 1.0}},
            "tropes": ["魔法学院", "龙与勇者", "穿越异世界", "魔法觉醒"],
        },
    },
]


def seed_templates(db):
    """将模板导入数据库，幂等（name unique，重复调用不报错）。"""
    from sqlalchemy import select
    from app.models.genre_template import GenreTemplate

    existing = {t.name for t in db.execute(select(GenreTemplate)).scalars().all()}
    inserted = 0
    for tmpl in GENRE_TEMPLATES:
        if tmpl["name"] in existing:
            continue
        gt = GenreTemplate(
            name=tmpl["name"],
            category=GENRE_CATEGORY_MAP.get(tmpl["name"], "创新/复合"),
            config=tmpl["config"],
        )
        db.add(gt)
        inserted += 1
    db.commit()
    return inserted


def get_all_templates():
    """同步获取所有模板（用于 CLI / 脚本）。"""
    return GENRE_TEMPLATES


def get_template_by_name(name: str):
    """按题材名获取配置（用于生成服务注入）。"""
    for t in GENRE_TEMPLATES:
        if t["name"] == name:
            return t
    return None
