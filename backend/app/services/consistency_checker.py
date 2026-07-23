"""
设定一致性检查服务。
对比 story_core / character / worldview 之间的关键信息冲突。
"""
import re
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.character import Character
from app.models.worldview import Worldview


def _extract_names(text: str) -> set[str]:
    """从文本中提取2-4字中文词组，用于人名检测。"""
    skip = {'少年', '铁匠', '学徒', '公主', '剑客', '精灵', '教会', '教廷',
            '大陆', '世界', '戒指', '力量', '时空', '元素', '生命', '死亡',
            '黑暗', '远古', '上古', '千年', '第一', '本源', '核心', '容器',
            '混沌', '秩序', '帝国', '人类', '情感', '议会',
            '规则', '裂隙', '自由', '真相', '任务', '家族', '长老',
            '被迫', '三人', '枚元', '阴谋', '召唤', '异端',
            '追捕', '逃亡', '救赎', '命运', '传说', '元戒',
            '持有', '使用', '代价', '信任', '危机', '平衡',
            '三枚', '时间', '空间', '体系', '简单',
            '伙伴', '互补', '团队', '秘密', '成长', '互动', '富含',
            '戏剧', '张力', '内在', '外在', '对抗', '同时',
            '还要', '必须', '做出', '抉择', '成为', '救世', '还是',
            '让元', '永封', '虚无', '之中', '真正', '强大', '在于',
            '拥有', '毁灭', '选择', '如何', '运用', '守护', '所爱',
            '之人与', '之后', '集齐', '能重', '塑造',
            '当黑', '教团', '浮出水', '他们', '试图',
            '邪神', '降临', '需要', '加速', '不用',
            '保护', '同伴', '阻止', '使用力量', '不用力量',
            '艾瑟诺', '艾瑟拉', '暗影', '教团', '教会', '教廷',
            '黑暗', '远古', '上古', '千年', '第一', '本源',
            '第一缕', '元素之', '力量', '时间', '空间'}
    candidates: set[str] = set()
    for m in re.finditer(r'[\u4e00-\u9fff]{2,4}', text):
        word = m.group()
        if word not in skip and len(word) >= 2:
            candidates.add(word)
    return candidates


def _contains_name(text: str, name: str) -> bool:
    """检查文本中是否包含某名字（至少2字以上）。"""
    if len(name) < 2:
        return False
    return name in text


async def check_setting_consistency(
    db: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    """
    检查 project 的 story_core / characters / worldview 一致性。
    返回冲突列表，每项包含：
      - type: 冲突类型 (protagonist_name / entity_conflict / faction_name)
      - severity: critical / warning
      - detail: 人类可读描述
      - sources: 冲突来源字段列表
    """
    conflicts: list[dict[str, Any]] = []

    # ── 加载数据 ────────────────────────────────────────────────────
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        return {"conflicts": conflicts, "healthy": True}

    story_core = project.story_core or {}
    story_text = json.dumps(story_core, ensure_ascii=False)

    ch_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = ch_result.scalars().all()

    wv_result = await db.execute(
        select(Worldview).where(Worldview.project_id == project_id)
    )
    worldviews = wv_result.scalars().all()

    worldview_text = "\n".join(
        w.description or "" for w in worldviews
    )

    # ── 1. 主角名字一致性 ──────────────────────────────────────────
    protagonist = next(
        (c for c in characters if c.role_type == "主角"), None
    )
    if protagonist and protagonist.name:
        p_name = protagonist.name
        summary = story_core.get("summary", "")

        # 提取 story_core summary 中的名字候选
        name_candidates: set[str] = set()
        # skip list defined early for all patterns
        skip_names = {'少年', '铁匠', '学徒', '公主', '剑客', '精灵',
                      '教会', '教廷', '大陆', '世界', '戒指', '力量',
                      '时空', '元素', '生命', '死亡', '黑暗', '远古',
                      '上古', '千年', '第一', '本源', '核心', '容器',
                      '混沌', '秩序', '帝国', '人类', '情感', '议会',
                      '被迫', '三人', '枚元', '阴谋', '召唤', '异端',
                      '追捕', '逃亡', '救赎', '命运', '传说', '元戒',
                      '持有', '使用', '代价', '信任', '危机', '平衡',
                      '三枚', '时间', '空间', '体系', '简单',
                      '伙伴', '互补', '团队', '秘密', '成长', '互动',
                      '富含', '戏剧', '张力', '内在', '外在', '对抗',
                      '同时', '还要', '必须', '做出', '抉择', '成为',
                      '救世', '还是', '让元', '永封', '虚无', '之中',
                      '真正', '强大', '在于', '拥有', '毁灭', '选择',
                      '如何', '运用', '守护', '所爱', '之人与', '之后',
                      '集齐', '能重', '塑造', '当黑', '教团', '浮出水',
                      '他们', '试图', '邪神', '降临', '需要', '加速',
                      '不用', '保护', '同伴', '阻止', '使用力量',
                      '不用力量', '艾瑟诺', '艾瑟拉', '暗影', '了', '之',
                      '意外', '继承', '手持', '邂逅', '掌握', '决定',
                      '犹豫', '神秘', '之戒', '持有者'}

        # 模式1："少年铁匠学徒{名字}"
        for m in re.finditer(r'少年铁匠学徒([\u4e00-\u9fff]{2,4})', summary):
            word = m.group(1)
            if word not in skip_names:
                name_candidates.add(word)

        # 模式2："{名字}必须"、"{名字}决定"
        for m in re.finditer(r'([\u4e00-\u9fff]{2})(?:必须|决定)', summary):
            word = m.group(1)
            if word not in skip_names:
                name_candidates.add(word)

        # 模式3："邂逅了{名字}的"、"守护{名字}元戒"、"掌握{名字}元戒"
        for m in re.finditer(r'(?:邂逅了|守护|掌握)([\u4e00-\u9fff]{2,3})(?:的|元戒)', summary):
            word = m.group(1)
            if word not in skip_names and '元戒' not in word:
                name_candidates.add(word)

        # 模式4："{名字}的精灵"、"{名字}的公主"
        for m in re.finditer(r'([\u4e00-\u9fff]{2,4})(?:的(?:精灵|神秘|剑客|公主))', summary):
            word = m.group(1)
            if word not in skip_names:
                name_candidates.add(word)

        # 最终过滤
        name_candidates = {n for n in name_candidates if n not in skip_names and len(n) >= 2}

        if p_name not in summary and name_candidates:
            conflicts.append({
                "type": "protagonist_name",
                "severity": "critical",
                "detail": (
                    f"主角名字不一致：角色设定为「{p_name}」，"
                    f"但故事核心中提到「{', '.join(sorted(name_candidates)[:3])}」"
                ),
                "sources": ["character.name", "story_core.summary"],
            })

    # ── 2. 元戒数量设定冲突 ────────────────────────────────────────
    # 检查 story_core 和 worldview 中元戒数量的冲突
    sc_mentions_three = "三枚" in story_text or "三戒" in story_text
    sc_mentions_unique = ("唯一" in story_text and ("元戒" in story_text or "戒指" in story_text))

    wv_mentions_unique = "唯一" in worldview_text and ("元戒" in worldview_text or "第一缕" in worldview_text)
    wv_mentions_three = "三枚" in worldview_text

    if sc_mentions_three and wv_mentions_unique:
        conflicts.append({
            "type": "entity_conflict",
            "severity": "critical",
            "detail": (
                "元戒数量设定冲突：故事核心说「三枚元戒」，"
                "世界观设定说「元戒是唯一」"
            ),
            "sources": ["story_core.summary", "worldview.description"],
        })

    # ── 3. 反派组织名称冲突 ────────────────────────────────────────
    all_char_text = "\n".join(
        c.background or "" for c in characters
    )
    factions_sc = re.findall(r'(黑暗教廷|教廷|暗影教团|教团|教会)', story_text)
    factions_char = re.findall(r'(黑暗教廷|教廷|暗影教团|教团|教会)', all_char_text)

    sc_factions = set(factions_sc)
    char_factions = set(factions_char)
    both = sc_factions & char_factions
    if not both and sc_factions and char_factions:
        conflicts.append({
            "type": "faction_name",
            "severity": "warning",
            "detail": (
                f"反派组织名称不一致：故事核心提到「{', '.join(sc_factions)}」，"
                f"角色设定提到「{', '.join(char_factions)}」"
            ),
            "sources": ["story_core.summary", "character.background"],
        })

    healthy = len(conflicts) == 0
    return {"conflicts": conflicts, "healthy": healthy}