"""GET /api/experiences, /api/experience/{id} - CONTRACT §2.4 + §2.5

list endpoint 不返 content_md (避 SCF 6MB HTTP 上限)
- 2026-07-17: NJX 拍板 default limit=3 (前 15 经验 + 完整 content_md → 6MB+ 触发 502)
- 单条 /api/experience/{id} 仍返完整 (含 content_md)
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from aog_web.models.experience import ExperienceSummary
from aog_web.services.sqlite_client import get_sqlite_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["experiences"])


# SCF 6MB HTTP response limit - 经验 content_md 平均 400KB, 15 条超 6MB
# NJX 2026-07-17 拍板 default=3 (列表页 3 条够用), max=15 (全量导出/调试用)
MAX_LIST_LIMIT = 15
DEFAULT_LIST_LIMIT = 3


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
    """经验列表 - 不含 content_md (避 SCF 6MB limit)

    过滤 (category/status/q) + 分页 (limit/offset) 都在 service 层
    list 拿全集 (in-memory), 然后 slice; 数据规模 < 100 条, 无需 SQL LIMIT
    """
    client = get_sqlite_client()
    all_exps = await client.list_experiences(category=category, status=status, q=q)
    sliced = all_exps[offset : offset + limit]
    # 去掉 content_md (heavy) - 走 Pydantic model 自动 exclude
    return [ExperienceSummary.model_validate(e) for e in sliced]


@router.get("/experience/{exp_id}")
async def get_experience(request: Request, exp_id: str) -> dict:
    """经验详情 - 返完整 (含 content_md)"""
    client = get_sqlite_client()
    exp = await client.get_experience(exp_id)
    if exp is None:
        raise HTTPException(status_code=404, detail={"error": "experience not found", "id": exp_id})
    return exp
