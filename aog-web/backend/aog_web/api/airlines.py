"""GET /api/airlines + /api/airlines/{iata} + /api/airlines/search - Sprint C

- 数据源: data/airlines.json (静态 JSON, 启动时 load)
- 3 个端点:
    GET /api/airlines                       -> list (支持 letter/alliance/hub 过滤)
    GET /api/airlines/{iata}                -> 单个航司详情 (大写 IATA)
    GET /api/airlines/search?q=xxx          -> 模糊搜索 (iata/icao/name_cn/name_en)
- 每个 hub 加 city 字段 (从 sqlite 查 iata → name), city 不存在时 city=null
- 离线 fallback: airlines.json 缺失 → 返回空 list, 不崩
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from aog_web.services.airlines_client import get_airlines_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/airlines", tags=["airlines"])


async def _enrich_hub_with_city(
    request: Request, hub: Dict[str, Any]
) -> Dict[str, Any]:
    """为 hub 加 city 字段 (从 sqlite 查 iata → name/code)

    city_code 不在 codes.json (前端硬编码) → city=null (前端降级为纯文本)
    city_code 在 → city={code, name, iata, status}
    """
    city_code = hub.get("city_code")
    if not city_code:
        return {**hub, "city": None}

    sqlite = getattr(request.app.state, "sqlite", None)
    if sqlite is None:
        # 启动未完成 / 离线模式 — 仅返回原始 hub
        return {**hub, "city": None}

    try:
        city = await sqlite.get_city(city_code)
        if city is None:
            return {**hub, "city": None}
        return {
            **hub,
            "city": {
                "code": city.get("code"),
                "name": city.get("name"),
                "iata": city.get("iata"),
                "status": city.get("status"),
            },
        }
    except Exception as e:
        logger.warning("Hub city lookup failed for %s: %s", city_code, e)
        return {**hub, "city": None}


async def _enrich_airline(
    request: Request, airline: Dict[str, Any]
) -> Dict[str, Any]:
    """给一个 airline 文档的所有 hub 加 city 字段"""
    enriched_hubs = []
    for h in airline.get("hubs", []):
        enriched_hubs.append(await _enrich_hub_with_city(request, h))
    return {**airline, "hubs": enriched_hubs}


@router.get("")
async def list_airlines(
    request: Request,
    letter: Optional[str] = Query(None, description="IATA 首字母 A-Z"),
    alliance: Optional[str] = Query(None, description="联盟过滤"),
    hub: Optional[str] = Query(None, description="基地 city_code 过滤"),
) -> List[Dict[str, Any]]:
    """航司列表 (按 IATA 字母序)"""
    if letter is not None:
        if not letter.isalpha() or len(letter) != 1:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid query", "field": "letter"},
            )
    client = get_airlines_client()
    raw = client.list(letter=letter, alliance=alliance, hub=hub)
    # 并发 enrich (N small hubs × N airlines ~25*2 = 50 queries max)
    return [await _enrich_airline(request, a) for a in raw]


@router.get("/search")
async def search_airlines(
    request: Request,
    q: str = Query(..., min_length=1, max_length=64, description="搜索关键字"),
    limit: int = Query(20, ge=1, le=50, description="最大结果数"),
) -> List[Dict[str, Any]]:
    """按 IATA / ICAO / 中文名 / 英文名 模糊搜索"""
    client = get_airlines_client()
    raw = client.search(q, limit=limit)
    return [await _enrich_airline(request, a) for a in raw]


@router.get("/{iata}")
async def get_airline(request: Request, iata: str) -> Dict[str, Any]:
    """按 IATA 2-letter code 查航司详情"""
    if not iata or len(iata) != 2 or not iata.isalnum():
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid iata", "iata": iata},
        )
    client = get_airlines_client()
    airline = client.get(iata)
    if airline is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "airline not found", "iata": iata.upper()},
        )
    return await _enrich_airline(request, airline)
