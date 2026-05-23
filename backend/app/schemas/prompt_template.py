from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel
from uuid import UUID


class PromptTemplateCreate(BaseModel):
    name: str
    category: str = "chapter"
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_default: int = 0


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_default: Optional[int] = None


class PromptTemplateResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    category: str
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_default: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
