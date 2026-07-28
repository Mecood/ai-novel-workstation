from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel, Field
from uuid import UUID


class ChapterCreate(BaseModel):
    chapter_number: int
    title: str
    content: Optional[Any] = None
    summary: Optional[str] = None
    outline_detail: Optional[Any] = None
    word_count: int = 0
    status: str = "draft"
    skeleton: Optional[dict[str, Any]] = None
    content_marks: Optional[list[dict[str, Any]]] = None
    group: Optional[str] = None
    tags: Optional[list[str]] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[Any] = None
    summary: Optional[str] = None
    outline_detail: Optional[Any] = None
    word_count: Optional[int] = None
    status: Optional[str] = None
    skeleton: Optional[dict[str, Any]] = None
    content_marks: Optional[list[dict[str, Any]]] = None
    group: Optional[str] = None
    tags: Optional[list[str]] = None


class ChapterResponse(BaseModel):
    id: UUID
    project_id: UUID
    chapter_number: int
    title: str
    content: Optional[Any] = None
    summary: Optional[str] = None
    outline_detail: Optional[Any] = None
    word_count: int
    status: str
    version: Optional[int] = Field(None, alias="_version")
    stale: Optional[str] = Field(None, alias="_stale")
    based_on: Optional[Any] = Field(None, alias="_based_on")
    history: Optional[Any] = Field(None, alias="_history")
    skeleton: Optional[dict[str, Any]] = Field(None, alias="_skeleton")
    content_marks: Optional[list[dict[str, Any]]] = None
    group: Optional[str] = None
    tags: Optional[list[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}