"""AI generation service."""
import json
from pathlib import Path
from typing import AsyncGenerator

import yaml
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.ai_client import AIClient
from app.models.app_config import AppConfig
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.project import Project
from app.models.genre_template import GenreTemplate

# ── Phase 13.3：反幻觉三定律（注入每个 AI 生成的 system prompt）──────
ANTI_HALLUCINATION_LAWS = """
# 反幻觉三定律（必须严格遵守，不得违背）

## 第一定律：大纲即法律
你正在创作的是大纲已经确定的章节。必须严格遵循章节大纲中设定的情节、人物动作、场景转换。
不得在无大纲依据的情况下增加重大情节转折、新角色登场或角色关系变更。
如果大纲中某节写了"三人对峙"，不能写成"两人密谋"。

## 第二定律：设定即物理
世界观设定是笔下世界的物理定律，不是建议。
角色已有境界、已有物品、已发生的地点转换、已建立的人物关系——这些不可自相矛盾。
如果主角已设定为"筑基期"，不能在本章无交代地变成"金丹期"。

## 第三定律：发明需识别
任何新出现的角色名、地名、物品名、功法名、势力名——如果首次出现，
必须在描写中明确交代其身份/属性/用途，让读者知道这是新设定。
不得出现"叶尘取出灵剑，施展玄阴掌"而前文从未交代过玄阴掌来源的情况。
"""
from app.models.volume import Volume


class AIService:
    """Service for AI-powered story generation."""

    PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"

    async def _build_client(self, db: AsyncSession) -> AIClient:
        """Build an AIClient using the active provider configured in AppConfig."""
        result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
        app_config = result.scalar_one_or_none()
        config = (app_config.config if app_config else None) or {}

        active_idx = config.get("active_provider")
        providers = config.get("providers") or []
        if active_idx is None or not providers:
            raise HTTPException(400, "未配置 AI 提供商，请前往设置页面添加并选中一个提供商")

        if isinstance(active_idx, int):
            provider = providers[active_idx] if 0 <= active_idx < len(providers) else None
        else:
            provider = next((p for p in providers if p.get("name") == active_idx), None)
        if not provider:
            raise HTTPException(400, f"未找到激活的 AI 提供商：{active_idx}")

        url = provider.get("url")
        api_key = provider.get("api_key")
        model = provider.get("selected_model")
        if not url or not api_key:
            raise HTTPException(400, "AI 提供商配置不完整（缺少 url 或 api_key）")
        if not model:
            raise HTTPException(400, "请在设置页面选择一个模型")

        return AIClient(url=url, api_key=api_key, model=model)

    async def generate_story_core(self, db: AsyncSession, project: Project) -> str:
        """Generate story core based on project info."""
        prompt = self._load_prompt("story_core")
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"].format(
                name=project.name,
                description=project.description or "",
                genre=project.genre,
            )},
        ]
        client = await self._build_client(db)
        try:
            return await client.chat(messages, temperature=0.8)
        finally:
            await client.close()

    async def generate_worldview(self, db: AsyncSession, project: Project, story_core: str) -> str:
        """Generate worldview based on story core."""
        prompt = self._load_prompt("worldview")
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"].format(
                name=project.name,
                genre=project.genre,
                story_core=story_core,
            )},
        ]
        client = await self._build_client(db)
        try:
            return await client.chat(messages, temperature=0.8)
        finally:
            await client.close()

    async def generate_characters(
        self, db: AsyncSession, project: Project, story_core: str, worldview: str
    ) -> str:
        """Generate characters based on story core and worldview."""
        prompt = self._load_prompt("character")
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"].format(
                name=project.name,
                genre=project.genre,
                story_core=story_core,
                worldview=worldview,
            )},
        ]
        client = await self._build_client(db)
        try:
            return await client.chat(messages, temperature=0.85)
        finally:
            await client.close()

    async def generate_chapter_stream(
        self, db: AsyncSession, project: Project, chapter_number: int,
        story_core: str, worldview: str, characters: list[Character],
        previous_chapters: list[Chapter],
        vector_context: str = "",
        outline_detail: dict | None = None,
        style_guidance: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chapter generation with optional vector context and style guidance."""
        prompt = self._load_prompt("chapter")

        char_summary = "\n".join([
            f"- {c.name}（{c.role_type}）: {c.background}"
            for c in characters
        ])

        # ── Phase 17: 记忆系统替换 context_service ─────────────────
        prev_summary = ""
        memory_episodic_section = ""
        memory_semantic_section = ""
        try:
            from app.services.memory_orchestrator import build_memory_pack_for_chapter
            memory_pack = await build_memory_pack_for_chapter(
                db, str(project.id), chapter_number, task_type="write",
            )

            # working memory → prev_summary（与前文兼容）
            working_lines = memory_pack.get("working_memory", [])
            if working_lines:
                prev_summary = "\n".join(str(w) for w in working_lines)

            # episodic memory → 情节记忆注入 prompt
            episodic = memory_pack.get("episodic_memory", [])
            if episodic:
                memory_episodic_section = (
                    "\n\n### 情节记忆（近期事件）\n"
                    + "\n".join(str(e) for e in episodic)
                )

            # semantic memory → 长期事实注入 prompt
            semantic = memory_pack.get("semantic_memory", [])
            if semantic:
                sem_lines = []
                for s in semantic:
                    subj = s.get("subject", "")
                    fld = s.get("field", "")
                    val = s.get("value", "")
                    cat = s.get("category", "")
                    line = f"- [{cat}] {subj}"
                    if fld:
                        line += f".{fld}"
                    if val:
                        line += f": {val[:200]}"
                    sem_lines.append(line)
                if sem_lines:
                    memory_semantic_section = (
                        "\n\n### 长期记忆（世界观/角色/伏笔/知识）\n"
                        + "\n".join(sem_lines)
                    )
        except Exception:
            # 回退：简单的最近 3 章摘要
            if previous_chapters:
                prev_summary = "\n".join([
                    f"第{c.chapter_number}章 {c.title}: {c.summary}"
                    for c in previous_chapters[-3:]
                ])

        # 将向量检索结果拼入 prompt 作为额外上下文
        extra_context = ""
        if vector_context:
            extra_context = f"\n\n### 相关历史内容（向量检索）\n以下是与本章相关的历史情节片段：\n{vector_context}"

        # ── Phase 14.3：风格指导注入 ──────────────────────────────────
        style_section = ""
        if style_guidance:
            style_section = (
                "\n\n### 写作风格要求\n"
                "基于历史章节检测，请注意以下写作风格问题：\n"
                + "\n".join(f"- {s}" for s in style_guidance)
                + "\n请尽量规避上述问题，让文风更自然、更像人类作家。"
            )

        # ── Phase 15.1：题材模板配置注入 ──────────────────────────────
        template_section = ""
        if project.template_id:
            try:
                t_result = await db.execute(
                    select(GenreTemplate).where(GenreTemplate.id == project.template_id)
                )
                template = t_result.scalar_one_or_none()
                if template and template.config:
                    cfg = template.config
                    style = cfg.get("style", {})
                    pacing = cfg.get("pacing", {})
                    review = cfg.get("review", {})
                    parts = []
                    if style.get("vocabulary"):
                        parts.append(f"语言风格：{style['vocabulary']}")
                    wc = pacing.get("typical_chapter_word_count", 2500)
                    parts.append(f"本章建议字数：约 {wc} 字")
                    if pacing.get("min_hook_per_chapter"):
                        parts.append(f"本章至少包含 {pacing['min_hook_per_chapter']} 个钩子")
                    if review.get("key_dimensions"):
                        parts.append(f"审查重点维度：{', '.join(review['key_dimensions'])}")
                    template_section = (
                        "\n\n### 题材模板配置\n"
                        f"题材：{template.name}\n"
                        + "\n".join(parts)
                    )
            except Exception:
                pass  # 模板加载失败不影响主流程

        # 构建本章细纲段落
        outline_section = ""
        if outline_detail:
            parts = []
            label_map = {
                "opening": "开场",
                "events": "核心事件",
                "purpose": "目的",
                "conflict": "冲突",
                "character_arc": "角色弧线",
                "pacing": "情感节奏",
                "hooks": "钩子",
                "highlights": "爽点",
                "suspense": "悬念",
            }
            for key, label in label_map.items():
                val = outline_detail.get(key)
                if val:
                    parts.append(f"- {label}：{val}")
            if parts:
                outline_section = "### 本章细纲（严格参照以下细纲写作）\n" + "\n".join(parts)

        # ── Phase 16：写作指南 + 去AI味 + 风格约束 注入 ──────────
        writing_guide_section = ""
        try:
            from app.services.writing_guide_service import build_writing_prompt_section
            chapter_type = (outline_detail or {}).get("pacing", "normal")
            # pacing 字段可能是"快/慢/中速"等节奏描述，映射到类型
            pacing_map = {"快": "combat", "极快": "combat", "慢": "emotional", "中速": "normal"}
            chapter_type = pacing_map.get(chapter_type, chapter_type)
            writing_guide_section = build_writing_prompt_section(
                chapter_type=chapter_type,
                genre=project.genre if project.genre else None,
                include_anti_ai=True,
                include_style=True,
            )
        except Exception:
            pass  # 指南加载失败不影响主流程

        # ── Context Agent：五段式写作任务书注入 ──────────────────────
        task_book_section = ""
        try:
            from app.services.context_agent_service import ContextAgentService
            context_agent = ContextAgentService(db, str(project.id), chapter_number)
            task_book = await context_agent.build_writing_task_book()
            if task_book:
                task_book_section = "\n\n### 写作任务书\n" + task_book
        except Exception:
            pass  # 任务书加载失败不影响章节生成

        messages = [
            {"role": "system", "content": prompt["system"] + ANTI_HALLUCINATION_LAWS + "\n\n" + writing_guide_section},
            {"role": "user", "content": prompt["user"].format(
                name=project.name,
                genre=project.genre,
                story_core=story_core,
                worldview=worldview,
                characters=char_summary,
                chapter_number=chapter_number,
                prev_summary=prev_summary,
                extra_context=extra_context,
                outline_section=outline_section,
                style_section=style_section,
                template_section=template_section,
                memory_episodic_section=memory_episodic_section,
                memory_semantic_section=memory_semantic_section,
            )},
        ]

        client = await self._build_client(db)
        try:
            # 尝试流式生成
            streamed = False
            async for chunk in await client.chat(messages, temperature=0.8, stream=True):
                yield chunk
                streamed = True
            # 如果流式没输出任何内容，回退到非流式
            if not streamed:
                result = await client.chat(messages, temperature=0.8, stream=False)
                yield str(result)
        finally:
            await client.close()

    async def generate_chapter_meta(self, db: AsyncSession, content: str, chapter_number: int) -> dict:
        """Generate title and summary for a chapter after it's written."""
        messages = [
            {"role": "system", "content": "你是小说编辑。根据给出的章节正文，生成标题和摘要。严格按JSON格式输出。"},
            {"role": "user", "content": f"""以下是第{chapter_number}章的正文内容（前2000字）：

{content[:2000]}

请输出JSON格式：
{{"title": "第{chapter_number}章 XXX", "summary": "100字以内的章节摘要"}}

注意：title 必须以"第{chapter_number}章"开头。"""},
        ]
        client = await self._build_client(db)
        try:
            result = await client.chat(messages, temperature=0.3, max_tokens=300)
            text = str(result)
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {}
        finally:
            await client.close()

    async def check_consistency(
        self, db: AsyncSession, new_content: str, existing_content: list[dict]
    ) -> str:
        """Check consistency of new content against existing content."""
        prompt = self._load_prompt("consistency")
        existing_text = json.dumps(existing_content, ensure_ascii=False)
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"].format(
                new_content=new_content,
                existing_content=existing_text,
            )},
        ]
        client = await self._build_client(db)
        try:
            return await client.chat(messages, temperature=0.3)
        finally:
            await client.close()

    async def generate_outline(
        self, db: AsyncSession, project: Project,
        story_core: str, worldview: str, characters: list[Character],
    ) -> str:
        """Generate a full outline with volumes and chapter outlines."""
        prompt = self._load_prompt("outline")

        char_summary = "\n".join([
            f"- {c.name}（{c.role_type}）: {c.background} 性格：{', '.join(c.personality if isinstance(c.personality, list) else [])}"
            for c in characters
        ])

        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"].format(
                name=project.name,
                genre=project.genre,
                story_core=story_core,
                worldview=worldview,
                characters=char_summary,
            )},
        ]
        client = await self._build_client(db)
        try:
            return await client.chat(messages, temperature=0.85, max_tokens=8192)
        finally:
            await client.close()

    async def extract_knowledge(
        self, db: AsyncSession, content: str, source_type: str
    ) -> list[dict]:
        """Extract knowledge items from content using AI."""
        prompt = self._load_prompt("knowledge_extract")
        messages = [
            {"role": "system", "content": prompt["system"]},
            {
                "role": "user",
                "content": prompt["user"].format(
                    source_type=source_type,
                    content=content[:3000],  # Limit content length
                ),
            },
        ]
        client = await self._build_client(db)
        try:
            result = str(await client.chat(messages, temperature=0.3, max_tokens=2000))
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                return json.loads(match.group())
            return []
        except Exception:
            return []
        finally:
            await client.close()

    async def de_ai_rewrite_stream(
        self, db: AsyncSession, content: str
    ) -> AsyncGenerator[str, None]:
        """Stream de-AI rewrite of chapter content."""
        prompt = self._load_prompt("de_ai")
        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"].format(
                original_content=content,
            )},
        ]
        client = await self._build_client(db)
        try:
            async for chunk in await client.chat(messages, temperature=0.9, stream=True):
                yield chunk
        finally:
            await client.close()

    def _load_prompt(self, name: str) -> dict:
        """Load prompt template from YAML file."""
        path = self.PROMPT_DIR / f"{name}.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {
            "system": data["system"],
            "user": data["user"],
        }
