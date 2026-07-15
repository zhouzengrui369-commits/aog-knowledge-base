"""GET /api/experiences, /api/experience/{id} - CONTRACT §2.4 + §2.5"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from aog_web.services.sqlite_client import get_sqlite_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["experiences"])


@router.get("/experiences")
async def list_experiences(
    request: Request,
    category: Optional[str] = Query(None, description="主题: 流程/规范/案例/培训/技术/管理"),
    status: Optional[str] = Query(None, description="状态: 现行/历史/待审/已废"),
    q: Optional[str] = Query(None, description="全文搜索关键词"),
) -> list[dict]:
    """经验列表 - 按 updated_at desc"""
    client = get_sqlite_client()
    return await client.list_experiences(category=category, status=status, q=q)


@router.get("/experience/{exp_id}")
async def get_experience(request: Request, exp_id: str) -> dict:
    """经验详情"""
    client = get_sqlite_client()
    exp = await client.get_experience(exp_id)
    if exp is None:
        raise HTTPException(status_code=404, detail={"error": "experience not found", "id": exp_id})
    return exp
