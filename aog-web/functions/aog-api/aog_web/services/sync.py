"""SyncService - T6 增量同步主控

设计:
- 后台 asyncio 任务每 SYNC_INTERVAL_S 跑一次 FileWatcher.scan
- 发现 changed/new 触发 T3 pipeline 子进程 (uv run python -m pipeline.build_index --paths ...)
- deleted 走下次全量 reindex (MVP 简化 - 不为删除单独写删索引逻辑, 因为 T3 当前是 reset+upsert 模式)
- 单次失败不挂服务, logger.exception 继续下个 interval
- 提供 get_status() 给 /api/sync/status (读 index_stats + 自己的 last_poll)
- 提供 trigger_now() 给 /api/sync/trigger (立即跑一次, 不等 interval)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aog_web.config import get_settings
from aog_web.services.file_watcher import FileWatcher
from aog_web.services.sqlite_client import get_sqlite_client
from aog_web.services.sync_db import SyncDB

logger = logging.getLogger(__name__)


class SyncService:
    """T6 增量同步主服务

    启动: app lifespan 调用 start() → 启动后台 poll 任务
    关闭: app lifespan 调用 stop() → 取消 task + 关闭 sync_db
    手动: POST /api/sync/trigger → trigger_now()
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._running = False  # 是否有 poll 在跑 (防并发)
        self._last_poll: Optional[str] = None  # ISO8601
        self._last_result: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None
        self._db: Optional[SyncDB] = None
        self._watcher: Optional[FileWatcher] = None
        self._initialized = False

    def _ensure_init(self) -> None:
        """懒初始化 (Settings 必须先就绪) - 单例首次 start() 时调用"""
        if self._initialized:
            return
        s = get_settings()
        self._db = SyncDB(s.sync_state_db_path)
        self._db.init()
        self._watcher = FileWatcher(s.watch_dirs, self._db)
        self._initialized = True
        logger.info(
            "SyncService initialized: watch_dirs=%s interval=%ds",
            s.watch_dirs,
            s.SYNC_INTERVAL_S,
        )

    async def start(self) -> None:
        """启动后台 polling 任务 (lifespan 调用)"""
        s = get_settings()
        if not s.SYNC_ENABLED:
            logger.info("SyncService disabled (SYNC_ENABLED=false)")
            return
        if self._task and not self._task.done():
            logger.warning("SyncService already started, skip")
            return
        self._stop.clear()
        self._ensure_init()
        self._task = asyncio.create_task(self._poll_loop(), name="sync-poll")
        logger.info("SyncService started (interval=%ds)", s.SYNC_INTERVAL_S)

    async def stop(self) -> None:
        """停止 polling 任务 + 关闭 db"""
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._db:
            self._db.close()
            self._db = None
        self._watcher = None
        self._initialized = False
        logger.info("SyncService stopped")

    async def _poll_loop(self) -> None:
        """后台 loop: 每 SYNC_INTERVAL_S 跑一次 poll"""
        s = get_settings()
        # 启动先跑一次 (best-effort, 失败不阻塞)
        try:
            await self._poll_once()
        except Exception as e:  # noqa: BLE001
            logger.exception("initial sync poll error: %s", e)

        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=float(s.SYNC_INTERVAL_S)
                )
                # _stop 被 set → 退出
                break
            except asyncio.TimeoutError:
                # 正常 tick
                try:
                    await self._poll_once()
                except Exception as e:  # noqa: BLE001
                    logger.exception("sync poll error: %s", e)

    async def trigger_now(self) -> Dict[str, Any]:
        """手动触发一次 poll (POST /api/sync/trigger) - 阻塞等结果

        返回: {status, changed_count, new_count, deleted_count, reindex_ok, reindex_returncode, error}
        """
        self._ensure_init()
        if self._running:
            return {
                "status": "busy",
                "message": "sync already running, skip trigger",
                "changed_count": 0,
                "new_count": 0,
                "deleted_count": 0,
            }
        return await self._poll_once()

    async def _poll_once(self) -> Dict[str, Any]:
        """单次 poll: scan → trigger_reindex → 写 stats"""
        if self._running:
            return {
                "status": "busy",
                "message": "already running",
                "changed_count": 0,
                "new_count": 0,
                "deleted_count": 0,
            }
        self._running = True
        t0 = time.time()
        try:
            # 1. scan (同步, 调 to_thread 不阻塞 event loop)
            loop = asyncio.get_running_loop()
            assert self._watcher is not None
            assert self._db is not None
            scan_result: Tuple[List[Path], List[Path]] = await loop.run_in_executor(
                None, self._watcher.scan
            )
            changed, new = scan_result
            deleted = await loop.run_in_executor(
                None, self._watcher.scan_deleted
            )

            now = datetime.now(timezone.utc).isoformat()
            self._last_poll = now

            if not (changed or new or deleted):
                self._last_result = {
                    "status": "idle",
                    "changed_count": 0,
                    "new_count": 0,
                    "deleted_count": 0,
                    "last_poll": now,
                    "duration_s": round(time.time() - t0, 3),
                }
                self._last_error = None
                logger.info("sync poll: no changes")
                return self._last_result

            # 2. 触发 pipeline (changed + new 走增量; deleted 单独处理 - 触发全量 reindex)
            to_reindex = changed + new
            if deleted and not to_reindex:
                # 只有删除 → 触发全量 reindex (pipeline reset+upsert 会让 deleted 自然消失)
                logger.info("sync poll: %d deleted → full reindex", len(deleted))
                reindex_ok, rc, err = await self._trigger_reindex(paths=None)
            elif to_reindex:
                reindex_ok, rc, err = await self._trigger_reindex(paths=to_reindex)
            else:
                # both changed/new and deleted → 增量 (因为 T3 reset+upsert 会让 deleted 也消失)
                reindex_ok, rc, err = await self._trigger_reindex(paths=to_reindex)

            # 3. 写 sync_db cache (无论 reindex 成功失败, 都更新 mtime/size)
            await loop.run_in_executor(
                None,
                lambda: self._watcher.update_cache(changed, new, deleted),  # type: ignore[union-attr]
            )
            if reindex_ok:
                # 标记 last_synced (用 ISO 时间, 不依赖子进程输出时间)
                now_str = datetime.now(timezone.utc).isoformat()
                await loop.run_in_executor(
                    None,
                    lambda: self._db.mark_synced([str(p) for p in changed + new]),  # type: ignore[union-attr]
                )

            self._last_result = {
                "status": "ok" if reindex_ok else "error",
                "changed_count": len(changed),
                "new_count": len(new),
                "deleted_count": len(deleted),
                "reindex_returncode": rc,
                "error": err if not reindex_ok else None,
                "last_poll": now,
                "duration_s": round(time.time() - t0, 3),
            }
            self._last_error = err
            if reindex_ok:
                logger.info(
                    "sync poll: changed=%d new=%d deleted=%d reindex=%ds rc=%d",
                    len(changed), len(new), len(deleted),
                    self._last_result["duration_s"], rc,
                )
            else:
                logger.error("sync poll reindex failed: rc=%d err=%s", rc, err)
            return self._last_result

        except Exception as e:  # noqa: BLE001
            self._last_error = str(e)
            self._last_poll = datetime.now(timezone.utc).isoformat()
            self._last_result = {
                "status": "error",
                "error": str(e),
                "last_poll": self._last_poll,
                "duration_s": round(time.time() - t0, 3),
            }
            logger.exception("sync poll exception: %s", e)
            return self._last_result
        finally:
            self._running = False

    async def _trigger_reindex(
        self, paths: Optional[List[Path]]
    ) -> Tuple[bool, int, Optional[str]]:
        """调 T3 pipeline 子进程, 返回 (ok, returncode, error_msg)"""
        s = get_settings()
        cmd = ["uv", "run", "python", "-m", "pipeline.build_index"]
        if paths:
            cmd += ["--paths", *[str(p) for p in paths]]
        cwd = s.pipeline_dir
        if not cwd.exists():
            err = f"pipeline dir not found: {cwd}"
            logger.error(err)
            return False, -1, err

        logger.info("trigger reindex: cmd=%s cwd=%s", " ".join(cmd[:6]), cwd)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except Exception as e:  # noqa: BLE001
            err = f"subprocess exec failed: {e}"
            logger.exception(err)
            return False, -1, err

        try:
            stdout, stderr = await proc.communicate()
        except Exception as e:  # noqa: BLE001
            err = f"subprocess communicate failed: {e}"
            logger.exception(err)
            return False, -1, err

        rc = proc.returncode or 0
        if rc != 0:
            err_msg = (stderr.decode("utf-8", errors="replace") or "")[-1500:]
            return False, rc, err_msg
        # 成功 - log stdout 末行作为 evidence
        out_tail = (stdout.decode("utf-8", errors="replace") or "").splitlines()[-3:]
        logger.info("reindex ok: rc=%d tail=%s", rc, out_tail)
        return True, rc, None

    async def get_status(self) -> Dict[str, Any]:
        """当前状态: 合并 self._last_result + SQLite index_stats"""
        # 读 SQLite index_stats (T3 写的)
        try:
            sqlite = get_sqlite_client()
            stats = await sqlite.get_index_stats()
        except Exception as e:  # noqa: BLE001
            logger.warning("get_index_stats failed: %s", e)
            stats = {
                "status": "unknown",
                "last_sync": None,
                "queue": 0,
                "indexed_total": 0,
                "last_error": None,
            }

        # 合并 self._last_result
        if self._last_result:
            stats["changed_count"] = self._last_result.get("changed_count", 0)
            stats["new_count"] = self._last_result.get("new_count", 0)
            stats["deleted_count"] = self._last_result.get("deleted_count", 0)
            stats["sync_poll_at"] = self._last_poll
            stats["sync_duration_s"] = self._last_result.get("duration_s")
            # 如果 self._last_result 是 error, 覆盖
            if self._last_result.get("status") == "error":
                stats["status"] = "error"
                stats["last_error"] = self._last_error
        else:
            stats["changed_count"] = 0
            stats["new_count"] = 0
            stats["deleted_count"] = 0
            stats["sync_poll_at"] = None
            stats["sync_duration_s"] = None
        return stats


# 全局单例
_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    global _service
    if _service is None:
        _service = SyncService()
    return _service


def reset_sync_service() -> None:
    """测试 helper"""
    global _service
    _service = None
