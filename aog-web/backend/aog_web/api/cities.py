"""City list/detail endpoints with release trust and usage enforcement."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from aog_web.services.production_policy import (
    apply_city_release_policy,
    city_view_counts,
    increment_city_view,
)
from aog_web.services.sqlite_client import get_sqlite_client

router = APIRouter(prefix="/api", tags=["cities"])


@router.get("/cities")
async def list_cities(
    request: Request,
    region: Optional[str] = Query(None, description="地区筛选"),
    status: Optional[str] = Query(None, description="现行|暂停|已废"),
    letter: Optional[str] = Query(None, description="拼音首字母 A-Z"),
) -> list[dict]:
    if letter is not None and (not letter.isalpha() or len(letter) != 1):
        raise HTTPException(400, detail={"error": "invalid query", "field": "letter"})
    if status is not None and status not in {"现行", "暂停", "已废"}:
        raise HTTPException(400, detail={"error": "invalid query", "field": "status"})

    client = get_sqlite_client()
    cities = await client.list_cities(region=region, status=status, letter=letter)
    counts = await asyncio.to_thread(city_view_counts, client.db_path)
    return [
        apply_city_release_policy(city, view_count=counts.get(str(city.get("code")), 0))
        for city in cities
    ]


@router.get("/city/{code}")
async def get_city(request: Request, code: str) -> dict:
    client = get_sqlite_client()
    city = await client.get_city(code)
    if city is None:
        raise HTTPException(404, detail={"error": "city not found", "code": code})
    count = await asyncio.to_thread(increment_city_view, client.db_path, code)
    return apply_city_release_policy(city, view_count=count)
