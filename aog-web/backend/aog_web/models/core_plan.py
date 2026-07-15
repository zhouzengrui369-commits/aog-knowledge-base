"""CorePlan 模型 - CONTRACT §1.3"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CorePlanType = Literal["master", "checklist", "manual", "catalog"]


class CorePlan(BaseModel):
    """核心 AOG 预案 - CONTRACT §1.3"""

    id: str = Field(..., description="主键, 例 'core-20260204'")
    title: str
    type: CorePlanType
    content_md: str
    source_path: str
    updated_at: str = Field(..., description="ISO8601")
