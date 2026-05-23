from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class KnowledgeCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    category: str = "general"
    tags: Optional[List[str]] = []


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class KnowledgeResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    content: Optional[str] = None
    category: str
    tags: Optional[List[str]] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}