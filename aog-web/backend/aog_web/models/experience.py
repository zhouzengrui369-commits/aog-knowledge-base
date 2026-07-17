"""Experience 模型 - CONTRACT §1.2"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


Category = Literal["流程", "规范", "案例", "培训", "技术", "管理"]
Status = Literal["现行", "历史", "待审", "已废"]


class Experience(BaseModel):
    """保障经验 - CONTRACT §1.2"""

    id: str = Field(..., description="主键, 例 'exp-001'")
    title: str
    category: Category
    status: Status
    tags: List[str] = Field(default_factory=list)
    summary: str = Field(..., max_length=200, description="≤ 200 字")
    content_md: str
    related_pn: List[str] = Field(default_factory=list, description="相关件号")
    source_path: str
    updated_at: str = Field(..., description="ISO8601")


class ExperienceSummary(BaseModel):
    """经验列表轻量子集 - 不含 content_md

    列表页 (/api/experiences) 用, 避免 SCF 6MB HTTP 上限
    详情页 (/api/experience/{id}) 仍走 Experience (含 content_md)
    """

    id: str
    title: str
    category: Category
    status: Status
    tags: List[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=200, description="≤ 200 字")
    related_pn: List[str] = Field(default_factory=list, description="相关件号")
    source_path: str = ""
    updated_at: str = ""
