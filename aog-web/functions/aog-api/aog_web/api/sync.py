"""GET /api/sync/status + POST /api/sync/trigger - CONTRACT §2.9

GET  /api/sync/status      - 当前同步状态 (读 SQLite index_stats + self._last_result)
POST /api/sync/trigger     - 手动触发一次 poll (admin 用, 阻塞等结果)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from aog_web.models.chat import SyncStatus
from aog_web.services.sqlite_client import get_sqlite_client
from aog_web.services.sync import get_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status", response_model=SyncStatus)
async def sync_status(request: Request) -> SyncStatus:
    """同步状态 - 合并 SQLite index_stats + SyncService self._last_result"""
    svc = get_sync_service()
    status_dict = await svc.get_status()
    # SyncStatus 模型字段 (status / last_sync / queue / indexed_total / last_error)
    # 额外字段 (changed_count / new_count / deleted_count / sync_poll_at / sync_duration_s)
    # 由 pydantic 默默丢弃 (extra=allow 默认)
    return SyncStatus(
        status=status_dict.get("status", "idle"),
        last_sync=status_dict.get("last_sync"),
        queue=status_dict.get("queue", 0),
        indexed_total=status_dict.get("indexed_total", 0),
        last_error=status_dict.get("last_error"),
    )


@router.post("/trigger")
async def sync_trigger(request: Request) -> dict:
    """手动触发一次 poll - 阻塞等结果 (admin)

    返回: {status, changed_count, new_count, deleted_count, reindex_returncode, last_poll, duration_s}
    状态: idle (没变化) / ok (有变化 + 成功 reindex) / error / busy
    """
    svc = get_sync_service()
    result = await svc.trigger_now()
    logger.info("manual sync trigger: %s", result)
    return result
