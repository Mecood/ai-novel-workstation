"""
内置 12 题材模板种子数据。
"""
from app.models.genre_template import GenreTemplate

BUILTIN_TEMPLATES = [
    GenreTemplate(
        name="修仙",
        category="cultivation",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 5, "first_arc_chapters": 30},
            "structure": {"chapter_word_count_range": [1500, 4000], "chapter_count_range": [50, 300]},
            "style": {"vocabulary": "文白夹杂", "combat_scene_ratio": 0.3, "dialogue_ratio": 0.3, "sensory_focus": ["visual", "tactile", "kinesthetic"]},
            "review": {"key_dimensions": ["setting_consistency", "power_balance", "cultivation_logic"], "weight_overrides": {"coolpoint_density": 0.9}},
        },
    ),
    GenreTemplate(
        name="都市",
        category="urban",
        config={
            "pacing": {"typical_chapter_word_count": 3000, "min_hook_per_chapter": 1, "recommended_arcs": 3, "first_arc_chapters": 20},
            "structure": {"chapter_word_count_range": [2000, 5000], "chapter_count_range": [30, 200]},
            "style": {"vocabulary": "现代口语", "combat_scene_ratio": 0.05, "dialogue_ratio": 0.5, "sensory_focus": ["visual", "auditory"]},
            "review": {"key_dimensions": ["character_relationship", "reality_logic"], "weight_overrides": {"coolpoint_density": 0.5}},
        },
    ),
    GenreTemplate(
        name="悬疑",
        category="mystery",
        config={
            "pacing": {"typical_chapter_word_count": 2000, "min_hook_per_chapter": 2, "recommended_arcs": 3, "first_arc_chapters": 15},
            "structure": {"chapter_word_count_range": [1500, 3500], "chapter_count_range": [20, 150]},
            "style": {"vocabulary": "克制描写", "combat_scene_ratio": 0.1, "dialogue_ratio": 0.35, "sensory_focus": ["visual", "auditory", "tactile"]},
            "review": {"key_dimensions": ["clue_consistency", "timeline"], "weight_overrides": {"coolpoint_density": 0.3}},
        },
    ),
    GenreTemplate(
        name="仙侠",
        category="xianxia",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 5, "first_arc_chapters": 30},
            "structure": {"chapter_word_count_range": [1500, 4000], "chapter_count_range": [50, 300]},
            "style": {"vocabulary": "古风文雅", "combat_scene_ratio": 0.25, "dialogue_ratio": 0.35, "sensory_focus": ["visual", "auditory", "olfactory"]},
            "review": {"key_dimensions": ["power_balance", "setting_consistency", "artifact_logic"], "weight_overrides": {"coolpoint_density": 0.85}},
        },
    ),
    GenreTemplate(
        name="玄幻",
        category="fantasy",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 5, "first_arc_chapters": 25},
            "structure": {"chapter_word_count_range": [1500, 4500], "chapter_count_range": [50, 300]},
            "style": {"vocabulary": "宏大叙事", "combat_scene_ratio": 0.3, "dialogue_ratio": 0.3, "sensory_focus": ["visual", "kinesthetic"]},
            "review": {"key_dimensions": ["setting_consistency", "golden_finger_logic"], "weight_overrides": {"coolpoint_density": 0.9}},
        },
    ),
    GenreTemplate(
        name="言情",
        category="romance",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 3, "first_arc_chapters": 20},
            "structure": {"chapter_word_count_range": [1500, 4000], "chapter_count_range": [30, 200]},
            "style": {"vocabulary": "细腻描写", "combat_scene_ratio": 0.02, "dialogue_ratio": 0.55, "sensory_focus": ["visual", "emotional", "tactile"]},
            "review": {"key_dimensions": ["emotional_logic", "character_motivation"], "weight_overrides": {"coolpoint_density": 0.2}},
        },
    ),
    GenreTemplate(
        name="历史",
        category="historical",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 4, "first_arc_chapters": 25},
            "structure": {"chapter_word_count_range": [2000, 5000], "chapter_count_range": [30, 200]},
            "style": {"vocabulary": "考据风格", "combat_scene_ratio": 0.15, "dialogue_ratio": 0.35, "sensory_focus": ["visual", "auditory", "olfactory"]},
            "review": {"key_dimensions": ["historical_logic", "character_behavior"], "weight_overrides": {"coolpoint_density": 0.4}},
        },
    ),
    GenreTemplate(
        name="科幻",
        category="sci_fi",
        config={
            "pacing": {"typical_chapter_word_count": 3000, "min_hook_per_chapter": 1, "recommended_arcs": 4, "first_arc_chapters": 20},
            "structure": {"chapter_word_count_range": [2000, 5000], "chapter_count_range": [30, 200]},
            "style": {"vocabulary": "理性叙述", "combat_scene_ratio": 0.15, "dialogue_ratio": 0.3, "sensory_focus": ["visual", "auditory"]},
            "review": {"key_dimensions": ["tech_logic", "worldview_consistency"], "weight_overrides": {"coolpoint_density": 0.5}},
        },
    ),
    GenreTemplate(
        name="灵异",
        category="supernatural",
        config={
            "pacing": {"typical_chapter_word_count": 2000, "min_hook_per_chapter": 2, "recommended_arcs": 3, "first_arc_chapters": 15},
            "structure": {"chapter_word_count_range": [1200, 3500], "chapter_count_range": [20, 150]},
            "style": {"vocabulary": "心理描写", "combat_scene_ratio": 0.05, "dialogue_ratio": 0.25, "sensory_focus": ["visual", "auditory", "tactile"]},
            "review": {"key_dimensions": ["foreshadowing_consistency", "atmosphere"], "weight_overrides": {"coolpoint_density": 0.5}},
        },
    ),
    GenreTemplate(
        name="武侠",
        category="wuxia",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 4, "first_arc_chapters": 25},
            "structure": {"chapter_word_count_range": [1500, 4000], "chapter_count_range": [30, 200]},
            "style": {"vocabulary": "写意描写", "combat_scene_ratio": 0.3, "dialogue_ratio": 0.3, "sensory_focus": ["visual", "kinesthetic"]},
            "review": {"key_dimensions": ["martial_arts_logic", "sect_setting"], "weight_overrides": {"coolpoint_density": 0.8}},
        },
    ),
    GenreTemplate(
        name="游戏",
        category="game",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 5, "first_arc_chapters": 25},
            "structure": {"chapter_word_count_range": [1500, 4000], "chapter_count_range": [50, 300]},
            "style": {"vocabulary": "轻快风格", "combat_scene_ratio": 0.3, "dialogue_ratio": 0.35, "sensory_focus": ["visual", "auditory"]},
            "review": {"key_dimensions": ["value_logic", "skill_system"], "weight_overrides": {"coolpoint_density": 0.9}},
        },
    ),
    GenreTemplate(
        name="穿越",
        category="time_travel",
        config={
            "pacing": {"typical_chapter_word_count": 2500, "min_hook_per_chapter": 1, "recommended_arcs": 4, "first_arc_chapters": 20},
            "structure": {"chapter_word_count_range": [1500, 4000], "chapter_count_range": [30, 200]},
            "style": {"vocabulary": "轻松幽默", "combat_scene_ratio": 0.1, "dialogue_ratio": 0.45, "sensory_focus": ["visual", "emotional"]},
            "review": {"key_dimensions": ["worldview_transition_logic"], "weight_overrides": {"coolpoint_density": 0.7}},
        },
    ),
]