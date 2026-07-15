"""Sync service stub - 增量同步 (Wave 1 简化)

实际重建由 T3 pipeline 完成 (写 SQLite + Chroma)
本服务:
- 后台定时轮询 (placeholder)
- 提供 status 状态 (从 SQLite index_stats 读)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aog_web.config import get_settings
from aog_web.services.sqlite_client import get_sqlite_client

logger = logging.getLogger(__name__)


class SyncService:
    """Wave 1 占位: 真实增量同步由 pipeline 跑, 后端只读状态"""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        """启动后台 polling (Wave 1 简化: 不做事)"""
        s = get_settings()
        logger.info("SyncService started (interval=%ds, mock)", s.SYNC_INTERVAL_S)
        # 真实实现: 定时扫文件清单 → 对比 hash → 触发 reindex

    async def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def get_status(self) -> dict:
        """当前状态 - 读 SQLite index_stats"""
        sqlite = get_sqlite_client()
        return await sqlite.get_index_stats()


_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    global _service
    if _service is None:
        _service = SyncService()
    return _service
