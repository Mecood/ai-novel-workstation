from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel
from uuid import UUID


class ChapterCreate(BaseModel):
    chapter_number: int
    title: str
    content: Optional[Any] = None
    summary: Optional[str] = None
    word_count: int = 0
    status: str = "draft"


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[Any] = None
    summary: Optional[str] = None
    word_count: Optional[int] = None
    status: Optional[str] = None


class ChapterResponse(BaseModel):
    id: UUID
    project_id: UUID
    chapter_number: int
    title: str
    content: Optional[Any] = None
    summary: Optional[str] = None
    word_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}