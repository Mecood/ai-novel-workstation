from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}