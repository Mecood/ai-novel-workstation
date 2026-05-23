from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from uuid import UUID


class VolumeCreate(BaseModel):
    volume_number: Optional[int] = None
    title: str
    description: Optional[str] = None
    chapter_start: int = 1
    chapter_end: Optional[int] = None
    highlight_rhythm: Optional[Any] = None
    emotion_arc: Optional[Any] = None
    foreshadowing_notes: Optional[Any] = None
    twists: Optional[Any] = None


class VolumeUpdate(BaseModel):
    volume_number: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    chapter_start: Optional[int] = None
    chapter_end: Optional[int] = None
    highlight_rhythm: Optional[Any] = None
    emotion_arc: Optional[Any] = None
    foreshadowing_notes: Optional[Any] = None
    twists: Optional[Any] = None


class VolumeResponse(BaseModel):
    id: UUID
    project_id: UUID
    volume_number: int
    title: str
    description: Optional[str] = None
    chapter_start: int
    chapter_end: Optional[int] = None
    highlight_rhythm: Optional[Any] = None
    emotion_arc: Optional[Any] = None
    foreshadowing_notes: Optional[Any] = None
    twists: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
