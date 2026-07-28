from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class ForeshadowingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_chapter: Optional[int] = None
    status: str = "planted"
    # 证据链
    evidence_line: Optional[str] = None
    evidence_chapter: Optional[int] = None
    evidence_text: Optional[str] = None
    # 提醒等级
    reminder_level: str = "low"


class ForeshadowingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_chapter: Optional[int] = None
    status: Optional[str] = None
    # 证据链
    evidence_line: Optional[str] = None
    evidence_chapter: Optional[int] = None
    evidence_text: Optional[str] = None
    # 提醒等级
    reminder_level: Optional[str] = None
    # 回收时间（resolve 时自动设置）
    resolved_at: Optional[datetime] = None
    # DAG
    depends_on: Optional[list] = None
    dependency_type: Optional[str] = None
    expected_redemption_chapter: Optional[int] = None
    auto_check_enabled: Optional[bool] = None


class ForeshadowingResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: str
    target_chapter: Optional[int] = None
    status: str
    # 证据链
    evidence_line: Optional[str] = None
    evidence_chapter: Optional[int] = None
    evidence_text: Optional[str] = None
    # 提醒等级
    reminder_level: str = "low"
    # 回收时间
    resolved_at: Optional[datetime] = None
    # DAG
    depends_on: Optional[list] = None
    dependency_type: Optional[str] = None
    expected_redemption_chapter: Optional[int] = None
    auto_check_enabled: bool = True
    payoff_chapter: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}