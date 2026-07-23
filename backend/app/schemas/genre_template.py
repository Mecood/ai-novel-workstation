from pydantic import BaseModel
from uuid import UUID
from typing import Any


class GenreTemplateResponse(BaseModel):
    id: UUID
    name: str
    category: str
    config: Any
    created_at: Any

    class Config:
        from_attributes = True