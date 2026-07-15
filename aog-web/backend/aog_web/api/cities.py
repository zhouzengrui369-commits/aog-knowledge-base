"""GET /api/cities, /api/city/{code} - CONTRACT §2.2 + §2.3"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from aog_web.services.sqlite_client import get_sqlite_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cities"])


@router.get("/cities")
async def list_cities(
    request: Request,
    region: Optional[str] = Query(None, description="地区筛选, 例 '华北'"),
    status: Optional[str] = Query(None, description="状态筛选, '现行'|'暂停'|'已废'"),
    letter: Optional[str] = Query(None, description="首字母 A-Z (按 pinyin)"),
) -> list[dict]:
    """城市列表 - 按 pinyin 排序"""
    if letter is not None:
        if not letter.isalpha() or len(letter) != 1:
            raise HTTPException(status_code=400, detail={"error": "invalid query", "field": "letter"})
    if status is not None and status not in {"现行", "暂停", "已废"}:
        raise HTTPException(status_code=400, detail={"error": "invalid query", "field": "status"})
    client = get_sqlite_client()
    return await client.list_cities(region=region, status=status, letter=letter)


@router.get("/city/{code}")
async def get_city(request: Request, code: str) -> dict:
    """城市详情 - code 需 URL-encoded"""
    client = get_sqlite_client()
    city = await client.get_city(code)
    if city is None:
        raise HTTPException(status_code=404, detail={"error": "city not found", "code": code})
    return city
