"""AI generation service."""
import json
from pathlib import Path
from typing import AsyncGenerator

import yaml

from app.core.ai_client import AIClient
from app.models.project import Project
from app.models.worldview import Worldview
from app.models.character import Character
from app.models.chapter import Chapter


class AIService:
    """Service for AI-powered story generation."""
    
    PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"
    
    def __init__(self):
        self.client = AIClient()
    
    async def generate_story_core(self, project: Project) -> str:
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
        return await self.client.chat(messages, temperature=0.8)
    
    async def generate_worldview(self, project: Project, story_core: str) -> str:
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
        return await self.client.chat(messages, temperature=0.8)
    
    async def generate_characters(self, project: Project, story_core: str, worldview: str) -> str:
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
        return await self.client.chat(messages, temperature=0.85)
    
    async def generate_chapter_stream(
        self, project: Project, chapter_number: int,
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
        
        async for chunk in await self.client.chat(messages, temperature=0.8, stream=True):
            yield chunk
    
    async def check_consistency(
        self, new_content: str, existing_content: list[dict]
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
        return await self.client.chat(messages, temperature=0.3)
    
    def _load_prompt(self, name: str) -> dict:
        """Load prompt template from YAML file."""
        path = self.PROMPT_DIR / f"{name}.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {
            "system": data["system"],
            "user": data["user"],
        }
    
    async def close(self):
        await self.client.close()