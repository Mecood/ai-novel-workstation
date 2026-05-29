from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from uuid import UUID


class CharacterCreate(BaseModel):
    name: str
    role_type: str
    personality: Optional[Any] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    relationships: Optional[Any] = None
    arc: Optional[Any] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    role_type: Optional[str] = None
    personality: Optional[Any] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    relationships: Optional[Any] = None
    arc: Optional[Any] = None


class CharacterResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    role_type: str
    personality: Optional[Any] = None
    background: Optional[str] = None
    appearance: Optional[str] = None
    relationships: Optional[Any] = None
    arc: Optional[Any] = None
    version: Optional[int] = Field(None, alias="_version")
    stale: Optional[str] = Field(None, alias="_stale")
    based_on: Optional[Any] = Field(None, alias="_based_on")
    history: Optional[Any] = Field(None, alias="_history")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}