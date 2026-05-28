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
from app.models.character import Character
from app.models.chapter import Chapter
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
    ) -> AsyncGenerator[str, None]:
        """Stream chapter generation with optional vector context."""
        prompt = self._load_prompt("chapter")

        char_summary = "\n".join([
            f"- {c.name}（{c.role_type}）: {c.background}"
            for c in characters
        ])

        prev_summary = ""
        if previous_chapters:
            prev_summary = "\n".join([
                f"第{c.chapter_number}章 {c.title}: {c.summary}"
                for c in previous_chapters[-3:]  # Last 3 chapters context
            ])

        # 将向量检索结果拼入 prompt 作为额外上下文
        extra_context = ""
        if vector_context:
            extra_context = f"\n\n### 相关历史内容（向量检索）\n以下是与本章相关的历史情节片段：\n{vector_context}"

        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"].format(
                name=project.name,
                genre=project.genre,
                story_core=story_core,
                worldview=worldview,
                characters=char_summary,
                chapter_number=chapter_number,
                prev_summary=prev_summary,
                extra_context=extra_context,
            )},
        ]

        client = await self._build_client(db)
        try:
            async for chunk in await client.chat(messages, temperature=0.8, stream=True):
                yield chunk
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

    def _load_prompt(self, name: str) -> dict:
        """Load prompt template from YAML file."""
        path = self.PROMPT_DIR / f"{name}.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {
            "system": data["system"],
            "user": data["user"],
        }
