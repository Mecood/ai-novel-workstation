from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class VersionEntryResponse(BaseModel):
    """单条版本记录的响应（用于版本列表）。"""
    version: int
    content_hash: str
    word_count: int
    saved_at: datetime


class VersionDetailResponse(BaseModel):
    """单个版本的完整内容（用于预览与回滚）。"""
    version: int
    content_hash: str
    word_count: int
    content: Optional[Any] = None
    saved_at: datetime


class VersionHistoryResponse(BaseModel):
    """章节版本历史列表。"""
    chapter_id: str
    current_version: int
    versions: list[VersionEntryResponse]


class VersionRestoreResponse(BaseModel):
    """恢复到指定版本的响应。"""
    chapter_id: str
    restored_version: int
    previous_version: int
    restored_at: datetime
