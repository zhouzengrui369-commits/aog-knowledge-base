"""GET /api/sync/status - CONTRACT §2.9

读取 SQLite index_stats 表 (T3 pipeline 写入)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from aog_web.models.chat import SyncStatus
from aog_web.services.sqlite_client import get_sqlite_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status", response_model=SyncStatus)
async def sync_status(request: Request) -> SyncStatus:
    """同步状态"""
    sqlite = get_sqlite_client()
    stats = await sqlite.get_index_stats()
    return SyncStatus(**stats)
