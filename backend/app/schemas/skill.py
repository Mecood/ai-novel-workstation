"""Skill Pydantic schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID


class SkillDefinitionResponse(BaseModel):
    """A built-in skill loaded from filesystem (read-only)."""
    name: str
    category: str
    description: str
    version: str
    tasks: list[str]
    triggers: list[str]
    priority: int

    model_config = {"from_attributes": False}


class ProjectSkillResponse(BaseModel):
    """Per-project skill enablement record."""
    id: UUID
    project_id: UUID
    skill_name: str
    skill_category: str
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectSkillCreate(BaseModel):
    """Request body for enabling a skill for a project."""
    skill_name: str = Field(..., min_length=1, max_length=255)


class SkillsListResponse(BaseModel):
    """Combined response: all builtin skills + project-specific enablement."""
    builtin_skills: list[SkillDefinitionResponse]
    project_skills: list[ProjectSkillResponse]