"""Chat / Sync models - CONTRACT §1.4 + §1.5."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /api/chat request."""

    q: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    context_codes: Optional[List[str]] = Field(
        None, description="可选, 限定城市 code 列表"
    )


ReferenceVerificationStatus = Literal[
    "VERIFIED", "UNVERIFIED", "STALE", "MISSING", "FIXTURE", "REDACTED"
]


class Reference(BaseModel):
    """AI source reference with an explicit route and trust decision.

    Unsupported source kinds are represented as `available=false` and
    `href=null`; they never degrade to a raw document ID route.
    """

    id: str
    title: str
    href: Optional[str] = None
    snippet: str = Field(..., max_length=200, description="≤ 200 字片段")
    score: float = Field(..., ge=0.0, le=1.0)
    available: bool = True
    source_type: str = "unknown"
    verification_status: ReferenceVerificationStatus = "UNVERIFIED"
    reason: Optional[str] = None


ChatSectionType = Literal[
    "heading",
    "paragraph",
    "table",
    "list",
    "ordered_list",
    "code",
    "alert",
    "quote",
]


class ChatSection(BaseModel):
    """A structurally rendered answer section."""

    type: ChatSectionType
    level: Optional[int] = Field(None, ge=1, le=3)
    text: Optional[str] = None
    header: Optional[List[str]] = None
    rows: Optional[List[List[str]]] = None
    items: Optional[List[str]] = None
    language: Optional[str] = None
    variant: Optional[Literal["info", "warning", "danger", "success"]] = None


class ChatResponse(BaseModel):
    """POST /api/chat response."""

    answer: str = Field(..., description="AI 回答 markdown")
    sections: Optional[List[ChatSection]] = None
    references: List[Reference] = Field(..., min_length=1)
    model: str
    latency_ms: int


class SyncStatus(BaseModel):
    status: Literal["idle", "running", "error"]
    last_sync: Optional[str] = None
    queue: int = 0
    indexed_total: int = 0
    last_error: Optional[str] = None