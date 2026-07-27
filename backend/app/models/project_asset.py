"""ProjectAsset model — stores generated images and other project assets."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base, GUID


class ProjectAsset(Base):
    __tablename__ = "project_assets"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(
        GUID,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(50), nullable=False, default="scene_image")
    label = Column(String(255), nullable=True)
    url = Column(String(1024), nullable=False)
    prompt = Column(String(2048), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )