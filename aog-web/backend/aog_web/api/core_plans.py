"""GET /api/core-plans, /api/core-plan/{id} - CONTRACT §2.6"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from aog_web.services.sqlite_client import get_sqlite_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["core-plans"])


@router.get("/core-plans")
async def list_core_plans(request: Request) -> list[dict]:
    """核心预案列表"""
    client = get_sqlite_client()
    return await client.list_core_plans()


@router.get("/core-plan/{plan_id}")
async def get_core_plan(request: Request, plan_id: str) -> dict:
    """核心预案详情"""
    client = get_sqlite_client()
    plan = await client.get_core_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail={"error": "core plan not found", "id": plan_id})
    return plan
