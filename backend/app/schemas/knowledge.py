from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class KnowledgeCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    category: str = "general"
    tags: Optional[List[str]] = []
    source: str = "manual"
    source_type: Optional[str] = None
    source_id: Optional[UUID] = None
    locked: Optional[int] = 0
    status: Optional[str] = "active"


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    locked: Optional[int] = None
    status: Optional[str] = None


class KnowledgeResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    content: Optional[str] = None
    category: str
    tags: Optional[List[str]] = []
    source: str = "manual"
    source_type: Optional[str] = None
    source_id: Optional[UUID] = None
    locked: int = 0
    status: str = "active"
    confidence: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    def __init__(self, **data):
        # Map DB column name confidence_int to response field confidence
        if "confidence_int" in data:
            data["confidence"] = data.pop("confidence_int")
        super().__init__(**data)