"""Chat / Sync 模型 - CONTRACT §1.4 + §1.5

V30 (NJX 7/27 22:14 拍板 🅰️): 加 ChatSection, ChatResponse 加 sections 字段.
   LLM 输出结构化 JSON, 前端用 React 组件渲染. 治本 LLM 输出 markdown 不规范.
"""
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


# ====== V30 ChatSection: 结构化输出 ======
# LLM 输出 JSON 数组, 每元素 = 一个 section
# type: heading/paragraph/table/list/ordered_list/code/alert/quote
# 失败 fallback: sections=None, 客户端用 markdown 渲染 (answer 字段)
ChatSectionType = Literal[
    "heading",       # heading.text + level (1-3)
    "paragraph",     # paragraph.text
    "table",         # table.header + table.rows
    "list",          # list.items
    "ordered_list",  # ordered_list.items
    "code",          # code.text (inline) or code (block)
    "alert",         # alert.text + alert.variant (info/warning/danger/success)
    "quote",         # quote.text
]


class ChatSection(BaseModel):
    """V30 治本: LLM 输出的一个结构化 section

    后端负责解析 LLM JSON, 前端根据 type 渲染对应组件.
    这样 LLM 不用严格遵循 markdown 标记, 视觉完全可控.
    """

    type: ChatSectionType
    # heading: level 1-3
    level: Optional[int] = Field(None, ge=1, le=3)
    # text (paragraph/heading/code/quote)
    text: Optional[str] = None
    # table: header + rows
    header: Optional[List[str]] = None
    rows: Optional[List[List[str]]] = None
    # list/ordered_list
    items: Optional[List[str]] = None
    # code (block)
    language: Optional[str] = None
    # alert
    variant: Optional[Literal["info", "warning", "danger", "success"]] = None


class ChatResponse(BaseModel):
    """POST /api/chat 响应 - CONTRACT §1.4 + V30 扩展"""

    answer: str = Field(..., description="AI 回答 markdown (fallback 或 sections 渲染版)")
    # V30: 结构化 sections, LLM 输出 JSON 时填充
    # fallback: None, 前端用 v29d++ markdown 渲染
    sections: Optional[List[ChatSection]] = Field(
        None, description="V30 治本: 结构化 sections, 前端用组件化渲染"
    )
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
