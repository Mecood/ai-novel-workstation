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


class AIService:
    """Service for AI-powered story generation."""

    PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"

    async def _build_client(self, db: AsyncSession) -> AIClient:
        """Build an AIClient using the active provider configured in AppConfig."""
        result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
        app_config = result.scalar_one_or_none()
        config = (app_config.config if app_config else None) or {}

        active_name = config.get("active_provider")
        providers = config.get("providers") or []
        if not active_name or not providers:
            raise HTTPException(400, "未配置 AI 提供商，请前往设置页面添加并选中一个提供商")

        provider = next((p for p in providers if p.get("name") == active_name), None)
        if not provider:
            raise HTTPException(400, f"未找到激活的 AI 提供商：{active_name}")

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
    ) -> AsyncGenerator[str, None]:
        """Stream chapter generation."""
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
            )},
        ]

        client = await self._build_client(db)
        try:
            async for chunk in await client.chat(messages, temperature=0.8, stream=True):
                yield chunk
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

    def _load_prompt(self, name: str) -> dict:
        """Load prompt template from YAML file."""
        path = self.PROMPT_DIR / f"{name}.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {
            "system": data["system"],
            "user": data["user"],
        }
