"""SyncDB - 文件 hash 缓存 (T6 增量同步)

设计:
- 单一表 file_hashes: (path, mtime, size, last_seen, last_synced)
- 存 mtime + size 当轻量 hash (不读内容, 避免大文件 IO)
- 同步异步 IO 用 stdlib sqlite3 (写操作很轻量, 没必要 aiosqlite)
- 启动 init 时建表 (idempotent)
- 纯同步接口 (测试和 watcher 都同步调用, sync 触发处用 asyncio.to_thread 隔离)
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS file_hashes (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    last_seen TEXT NOT NULL,
    last_synced TEXT
);
CREATE INDEX IF NOT EXISTS idx_file_hashes_mtime ON file_hashes(mtime);
"""


class SyncDB:
    """文件 hash 缓存 (stdlib sqlite3, 同步接口)

    用法:
        db = SyncDB(Path("./data/sync_state.db"))
        db.init()
        db.upsert(path, mtime, size, last_synced=now)
        old = db.get(path)  # -> (mtime, size) or None
        all_paths = db.all_paths()  # set[str]
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def init(self) -> None:
        """启动时调用: 建表 (idempotent)"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False 让 connection 能跨 asyncio.to_thread 用
        # (SQLite 内部仍会 serialise write, 满足 fsync 语义)
        self._conn = sqlite3.connect(
            str(self.db_path), isolation_level=None, check_same_thread=False
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)
        logger.info("SyncDB initialized: %s", self.db_path)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SyncDB not initialized; call init() first")
        return self._conn

    def get(self, path: str) -> Optional[tuple[float, int]]:
        """查 path -> (mtime, size) or None"""
        conn = self._ensure_conn()
        cur = conn.execute("SELECT mtime, size FROM file_hashes WHERE path = ?", (path,))
        row = cur.fetchone()
        return (row[0], row[1]) if row else None

    def upsert(self, path: str, mtime: float, size: int, last_synced: Optional[str] = None) -> None:
        """insert or replace path + mtime + size + (可选) last_synced"""
        conn = self._ensure_conn()
        now = last_synced or datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO file_hashes (path, mtime, size, last_seen, last_synced)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                mtime = excluded.mtime,
                size = excluded.size,
                last_seen = excluded.last_seen,
                last_synced = COALESCE(excluded.last_synced, file_hashes.last_synced)
            """,
            (path, mtime, size, now, last_synced),
        )

    def touch_seen(self, path: str) -> None:
        """更新 last_seen (不改 mtime/size/last_synced)"""
        conn = self._ensure_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE file_hashes SET last_seen = ? WHERE path = ?",
            (now, path),
        )

    def delete(self, path: str) -> None:
        """删 path (不抛错即使不存在)"""
        conn = self._ensure_conn()
        conn.execute("DELETE FROM file_hashes WHERE path = ?", (path,))

    def all_paths(self) -> set[str]:
        """所有已知 path 集合 (用于算 deleted)"""
        conn = self._ensure_conn()
        cur = conn.execute("SELECT path FROM file_hashes")
        return {row[0] for row in cur.fetchall()}

    def mark_synced(self, paths: list[str]) -> None:
        """批量标记 last_synced (给指定 paths 列表)"""
        if not paths:
            return
        conn = self._ensure_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "UPDATE file_hashes SET last_synced = ? WHERE path = ?",
            [(now, p) for p in paths],
        )

    def count(self) -> int:
        conn = self._ensure_conn()
        cur = conn.execute("SELECT COUNT(*) FROM file_hashes")
        return cur.fetchone()[0]
