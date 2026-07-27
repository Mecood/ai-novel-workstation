"""Skill API endpoints.

GET  /api/v1/skills                     — list all built-in skills (from registry)
GET  /api/v1/projects/{id}/skills        — query project skills
POST /api/v1/projects/{id}/skills        — enable a skill for project
DELETE /api/v1/projects/{id}/skills/{skill_name}  — disable a skill for project
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.project import Project
from app.models.skill import ProjectSkill
from app.schemas.skill import (
    ProjectSkillCreate,
    ProjectSkillResponse,
    SkillDefinitionResponse,
    SkillsListResponse,
)
from app.services.skill_registry import get_registry

logger = logging.getLogger(__name__)

# Two routers: one standalone (/skills), one nested under /projects/{id}
skills_router = APIRouter(prefix="/skills", tags=["skills"])
project_skills_router = APIRouter(
    prefix="/projects/{project_id}/skills", tags=["project-skills"]
)

# ──────────────────────────────────────────────────────────────────
# GET /api/v1/skills — list all built-in skills
# ──────────────────────────────────────────────────────────────────

@skills_router.get("", response_model=list[SkillDefinitionResponse])
async def list_builtin_skills() -> list[SkillDefinitionResponse]:
    """Return all built-in skill definitions from the filesystem registry."""
    registry = get_registry()
    all_skills = registry.list_all()
    return [
        SkillDefinitionResponse(
            name=s.name,
            category=s.category,
            description=s.description,
            version=s.version,
            tasks=s.tasks,
            triggers=s.triggers,
            priority=s.priority,
        )
        for s in all_skills
    ]


# ─────────────────────────────────────────────────────────────────────────
# GET /api/v1/projects/{project_id}/skills — list project skill enablement
# ─────────────────────────────────────────────────────────────────────────

@project_skills_router.get("", response_model=SkillsListResponse)
async def list_project_skills(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SkillsListResponse:
    """Return built-in skills + per-project enablement records."""
    # Validate project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Builtin skills from registry
    registry = get_registry()
    all_skills = registry.list_all()

    # Project enablement records
    result = await db.execute(
        select(ProjectSkill).where(
            ProjectSkill.project_id == project_id,
            ProjectSkill.enabled == True,
        )
    )
    project_skills = list(result.scalars().all())

    return SkillsListResponse(
        builtin_skills=[
            SkillDefinitionResponse(
                name=s.name,
                category=s.category,
                description=s.description,
                version=s.version,
                tasks=s.tasks,
                triggers=s.triggers,
                priority=s.priority,
            )
            for s in all_skills
        ],
        project_skills=[
            ProjectSkillResponse.model_validate(ps) for ps in project_skills
        ],
    )


# ─────────────────────────────────────────────────────────────────────────
# POST /api/v1/projects/{project_id}/skills — enable a skill
# ─────────────────────────────────────────────────────────────────────────

@project_skills_router.post("", response_model=ProjectSkillResponse, status_code=201)
async def enable_project_skill(
    project_id: UUID,
    data: ProjectSkillCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectSkillResponse:
    """Enable a skill for the given project.

    If the skill is already enabled (marked enabled=True), return existing record.
    If it was disabled, re-enable it.
    Otherwise, create a new record.
    """
    # Validate project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate skill exists in registry
    registry = get_registry()
    definition = registry.get_by_name(data.skill_name)
    if not definition:
        raise HTTPException(
            status_code=404,
            detail=f"Built-in skill '{data.skill_name}' not found.",
        )

    # Check for existing record
    result = await db.execute(
        select(ProjectSkill).where(
            ProjectSkill.project_id == project_id,
            ProjectSkill.skill_name == data.skill_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if not existing.enabled:
            existing.enabled = True
            await db.commit()
            await db.refresh(existing)
        return ProjectSkillResponse.model_validate(existing)

    # Create new record
    ps = ProjectSkill(
        project_id=project_id,
        skill_name=definition.name,
        skill_category=definition.category,
        enabled=True,
    )
    db.add(ps)
    await db.commit()
    await db.refresh(ps)
    return ProjectSkillResponse.model_validate(ps)


# ─────────────────────────────────────────────────────────────────────────
# DELETE /api/v1/projects/{project_id}/skills/{skill_name} — disable skill
# ─────────────────────────────────────────────────────────────────────────

@project_skills_router.delete("/{skill_name}")
async def disable_project_skill(
    project_id: UUID,
    skill_name: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disable a skill for a project by setting enabled=False.

    (Soft-delete — the record stays in the DB.)
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(ProjectSkill).where(
            ProjectSkill.project_id == project_id,
            ProjectSkill.skill_name == skill_name,
        )
    )
    ps = result.scalar_one_or_none()
    if not ps:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{skill_name}' is not enabled for this project.",
        )

    ps.enabled = False
    await db.commit()