from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from uuid import UUID


class WorldviewCreate(BaseModel):
    name: str
    description: str
    rules: Optional[Any] = None
    timeline: Optional[Any] = None


class WorldviewUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[Any] = None
    timeline: Optional[Any] = None


class WorldviewResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str
    rules: Optional[Any] = None
    timeline: Optional[Any] = None
    version: Optional[int] = Field(None, alias="_version")
    stale: Optional[str] = Field(None, alias="_stale")
    based_on: Optional[Any] = Field(None, alias="_based_on")
    history: Optional[Any] = Field(None, alias="_history")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}