"""Chat / Sync 模型 - CONTRACT §1.4 + §1.5"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /api/chat 请求体 - CONTRACT §1.4"""

    q: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    context_codes: Optional[List[str]] = Field(
        None, description="可选, 限定城市 code 列表"
    )


class Reference(BaseModel):
    """AI 回答引用 (NSM-2 红线: 必须 ≥ 1)"""

    id: str
    title: str
    href: str
    snippet: str = Field(..., max_length=200, description="≤ 200 字片段")
    score: float = Field(..., ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    """POST /api/chat 响应 - CONTRACT §1.4"""

    answer: str = Field(..., description="AI 回答 markdown")
    references: List[Reference] = Field(..., min_length=1, description="NSM-2: ≥ 1")
    model: str
    latency_ms: int


class SyncStatus(BaseModel):
    """GET /api/sync/status - CONTRACT §1.5"""

    status: Literal["idle", "running", "error"]
    last_sync: Optional[str] = None
    queue: int = 0
    indexed_total: int = 0
    last_error: Optional[str] = None
