from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class ForeshadowingCreate(BaseModel):
    title: str
    description: str
    target_chapter: Optional[int] = None
    status: str = "planted"


class ForeshadowingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_chapter: Optional[int] = None
    status: Optional[str] = None


class ForeshadowingResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: str
    target_chapter: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}