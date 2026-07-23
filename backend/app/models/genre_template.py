"""
题材模板模型 — 节奏/字数/风格/审查维度的全套配置。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, JSON, DateTime
from app.core.database import Base, GUID


class GenreTemplate(Base):
    __tablename__ = "genre_templates"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50), nullable=False, index=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def config_schema(self) -> dict:
        return {
            "pacing": {
                "typical_chapter_word_count": 2500,
                "min_hook_per_chapter": 1,
                "recommended_arcs": 5,
                "first_arc_chapters": 30,
            },
            "structure": {
                "chapter_word_count_range": [2000, 5000],
                "chapter_count_range": [50, 300],
            },
            "style": {
                "vocabulary": "文白夹杂",
                "combat_scene_ratio": 0.2,
                "dialogue_ratio": 0.4,
                "sensory_focus": ["visual", "tactile"],
            },
            "review": {
                "key_dimensions": ["setting_consistency", "timeline", "character"],
                "weight_overrides": {"coolpoint_density": 0.8},
            },
        }