"""ProjectSkill model — per-project skill enablement tracking.

Skill definitions live in the filesystem (SKILL.md).
This table only records which skills a project has enabled.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class ProjectSkill(Base):
    """Tracks skill enablement per project.

    Does NOT store skill definitions — those come from filesystem SKILL.md files.
    """
    __tablename__ = "project_skills"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(
        GUID,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_name = Column(String(255), nullable=False)
    skill_category = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )