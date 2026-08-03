"""GET /api/experiences, /api/experience/{id} - CONTRACT §2.4 + §2.5

List responses omit ``content_md`` to stay below the SCF response-size limit.
P0-1 publication gate: records marked ``has_content=false`` are excluded from
both the public list and direct detail access.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from aog_web.models.experience import ExperienceSummary
from aog_web.services.experience_content import (
    contentful_experience_ids,
    filter_contentful_experiences,
)
from aog_web.services.sqlite_client import get_sqlite_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["experiences"])


# SCF 6MB HTTP response limit - 经验 content_md 平均 400KB, 15 条超 6MB
# NJX 2026-07-17 拍板 default=3, max=15.
MAX_LIST_LIMIT = 15
DEFAULT_LIST_LIMIT = 3


async def _published_ids() -> set[str]:
    """Return durable publication flags without blocking the event loop."""
    client = get_sqlite_client()
    return await asyncio.to_thread(contentful_experience_ids, client.db_path)


@router.get("/experiences", response_model=List[ExperienceSummary])
async def list_experiences(
    request: Request,
    category: Optional[str] = Query(None, description="主题: 流程/规范/案例/培训/技术/管理"),
    status: Optional[str] = Query(None, description="状态: 现行/历史/待审/已废"),
    q: Optional[str] = Query(None, description="全文搜索关键词"),
    limit: int = Query(
        DEFAULT_LIST_LIMIT,
        ge=1,
        le=MAX_LIST_LIMIT,
        description=f"返回条数 (1-{MAX_LIST_LIMIT}, default {DEFAULT_LIST_LIMIT})",
    ),
    offset: int = Query(0, ge=0, description="跳过的条数 (default 0)"),
) -> List[ExperienceSummary]:
    """Return only experiences with verified non-empty content.

    Filtering happens before pagination so the default page still contains up
    to three usable experiences instead of empty shells.
    """
    client = get_sqlite_client()
    published_ids = await _published_ids()
    all_exps = await client.list_experiences(category=category, status=status, q=q)
    visible = filter_contentful_experiences(all_exps, published_ids)
    sliced = visible[offset : offset + limit]
    return [ExperienceSummary.model_validate(e) for e in sliced]


@router.get("/experience/{exp_id}")
async def get_experience(request: Request, exp_id: str) -> dict:
    """Return a complete experience only when it passed the content gate."""
    published_ids = await _published_ids()
    if exp_id not in published_ids:
        raise HTTPException(
            status_code=404,
            detail={"error": "experience not published", "id": exp_id},
        )

    client = get_sqlite_client()
    exp = await client.get_experience(exp_id)
    if exp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "experience not found", "id": exp_id},
        )
    return exp
