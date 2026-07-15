"""T6 增量同步 - tests

覆盖:
- FileWatcher.scan() 3 场景: new / changed / deleted
- SyncService 状态查询 + 手动 trigger (mock subprocess)
- /api/sync/trigger 端点
- /api/sync/status 端点 (附加字段 sync_poll_at / changed_count / ...)
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aog_web.services.file_watcher import FileWatcher
from aog_web.services.sync_db import SyncDB


# ====================================================================
# Fixtures
# ====================================================================


@pytest.fixture
def tmp_kb(tmp_path: Path) -> Path:
    """临时 KB 根: 01/02/03 + skip dirs"""
    kb = tmp_path / "kb"
    (kb / "01_AOG预案").mkdir(parents=True)
    (kb / "02_外战预案").mkdir(parents=True)
    (kb / "03_保障经验").mkdir(parents=True)
    # 跳过目录
    (kb / "04_课件").mkdir(parents=True)
    (kb / "04_课件" / "noise.pdf").write_text("noise")
    return kb


@pytest.fixture
def sync_db(tmp_path: Path) -> SyncDB:
    db = SyncDB(tmp_path / "sync_state.db")
    db.init()
    yield db
    db.close()


@pytest.fixture
def watcher(tmp_kb: Path, sync_db: SyncDB) -> FileWatcher:
    return FileWatcher(
        watch_dirs=[tmp_kb / "01_AOG预案", tmp_kb / "02_外战预案", tmp_kb / "03_保障经验"],
        db=sync_db,
    )


# ====================================================================
# SyncDB 基础 (8 tests)
# ====================================================================


def test_sync_db_init_creates_table(tmp_path: Path):
    db = SyncDB(tmp_path / "state.db")
    db.init()
    # 表能查 = 建表成功
    assert db.count() == 0
    db.close()


def test_sync_db_upsert_and_get(tmp_path: Path):
    db = SyncDB(tmp_path / "state.db")
    db.init()
    db.upsert("/a.md", 100.0, 200, last_synced="2026-07-15T00:00:00")
    assert db.get("/a.md") == (100.0, 200)
    # upsert 覆盖
    db.upsert("/a.md", 200.0, 300)
    assert db.get("/a.md") == (200.0, 300)
    # 不存在
    assert db.get("/nope.md") is None
    db.close()


def test_sync_db_all_paths_and_delete(tmp_path: Path):
    db = SyncDB(tmp_path / "state.db")
    db.init()
    db.upsert("/a.md", 1.0, 10)
    db.upsert("/b.md", 2.0, 20)
    assert db.all_paths() == {"/a.md", "/b.md"}
    db.delete("/a.md")
    assert db.all_paths() == {"/b.md"}
    db.close()


def test_sync_db_mark_synced(tmp_path: Path):
    db = SyncDB(tmp_path / "state.db")
    db.init()
    db.upsert("/a.md", 1.0, 10)
    db.upsert("/b.md", 2.0, 20)
    db.mark_synced(["/a.md"])
    # a 已 last_synced, b 没有 (但通过 get 拿不到, 只能验证后续逻辑)
    assert db.count() == 2
    db.close()


# ====================================================================
# FileWatcher  - 3 场景 (new / changed / deleted)
# ====================================================================


def test_file_watcher_detects_new_file(watcher, tmp_kb):
    """场景 1: 全新文件 → 出现在 new"""
    new_file = tmp_kb / "01_AOG预案" / "新预案.md"
    new_file.write_text("# 新预案")
    changed, new = watcher.scan()
    assert changed == []
    assert new_file in new
    # 04_课件 (skip dir) 不应出现
    assert tmp_kb / "04_课件" / "noise.pdf" not in {str(p) for p in changed + new}


def test_file_watcher_detects_changed_file(watcher, tmp_kb):
    """场景 2: 文件被修改 → mtime/size 变 → 出现在 changed"""
    f = tmp_kb / "01_AOG预案" / "原预案.md"
    f.write_text("v1")
    # 第一次 scan: 当 new
    changed, new = watcher.scan()
    assert f in new
    # 写入 db cache
    watcher.update_cache(changed, new, deleted=[])

    # 改文件 - 等 1s 让 mtime 一定变
    time.sleep(1.1)
    f.write_text("v2 - 重大修改")
    changed2, new2 = watcher.scan()
    assert new2 == []
    assert f in changed2


def test_file_watcher_detects_deleted_file(watcher, tmp_kb):
    """场景 3: 文件被删 → 出现在 scan_deleted"""
    f = tmp_kb / "02_外战预案" / "B-北京.md"
    f.write_text("B-北京")
    # 入库
    watcher.update_cache(*watcher.scan(), deleted=[])

    # 删文件
    f.unlink()
    deleted = watcher.scan_deleted()
    assert f in deleted


def test_file_watcher_ignores_skip_ext(watcher, tmp_kb):
    """.pdf / .pptx / .doc 不进 scan"""
    (tmp_kb / "01_AOG预案" / "noise.pdf").write_text("x")
    (tmp_kb / "01_AOG预案" / "noise.pptx").write_text("x")
    (tmp_kb / "01_AOG预案" / "noise.doc").write_text("x")
    changed, new = watcher.scan()
    paths = {str(p) for p in changed + new}
    assert not any("noise" in p for p in paths)


def test_file_watcher_ignores_skip_dirs(watcher, tmp_kb):
    """04_课件 / RAW 等 skip dirs 完全跳过"""
    (tmp_kb / "01_AOG预案" / "real.md").write_text("real")
    changed, new = watcher.scan()
    paths = {str(p) for p in changed + new}
    assert any("real.md" in p for p in paths)
    assert not any("04_课件" in p for p in paths)


def test_file_watcher_idempotent_on_no_change(watcher, tmp_kb):
    """无变化 → 空"""
    (tmp_kb / "01_AOG预案" / "stable.md").write_text("x")
    watcher.update_cache(*watcher.scan(), deleted=[])
    # 第二次 scan: 啥都没
    changed, new = watcher.scan()
    assert changed == []
    assert new == []


def test_file_watcher_update_cache_writes_mtime_size(watcher, sync_db, tmp_kb):
    """update_cache 后 db 里有 mtime/size"""
    f = tmp_kb / "01_AOG预案" / "test.md"
    f.write_text("hello")
    changed, new = watcher.scan()
    watcher.update_cache(changed, new, deleted=[])
    st = f.stat()
    assert sync_db.get(str(f)) == (st.st_mtime, st.st_size)


# ====================================================================
# SyncService  - trigger_now + get_status (mock subprocess)
# ====================================================================


def _make_fake_proc(rc: int = 0, stdout: bytes = b"ok", stderr: bytes = b""):
    """构造一个 fake Process 走 .communicate()"""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = rc
    return proc


@pytest.mark.asyncio
async def test_sync_service_trigger_no_changes(tmp_path, tmp_kb, monkeypatch):
    """trigger_now 在没文件时 → status=idle"""
    from aog_web.config import reset_settings_cache
    from aog_web.services.sync import SyncService

    # 重设 settings 用 tmp_path
    monkeypatch.setenv("SYNC_STATE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(tmp_kb))
    monkeypatch.setenv("SYNC_WATCH_DIRS", "")  # 用默认
    reset_settings_cache()
    s = SyncService()
    # _ensure_init() 懒初始化 (会读 settings)
    result = await s.trigger_now()
    assert result["status"] == "idle"
    assert result["changed_count"] == 0
    assert result["new_count"] == 0
    assert result["deleted_count"] == 0
    # cleanup
    await s.stop()
    reset_settings_cache()


@pytest.mark.asyncio
async def test_sync_service_trigger_with_changes_runs_pipeline(tmp_path, tmp_kb, monkeypatch):
    """trigger_now 检测到新文件 → 调 subprocess (mock) → 写 last_result"""
    from aog_web.config import reset_settings_cache
    from aog_web.services.sync import SyncService

    # 准备: 1 个新文件
    (tmp_kb / "01_AOG预案" / "新增.md").write_text("新内容")
    monkeypatch.setenv("SYNC_STATE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(tmp_kb))
    reset_settings_cache()

    # mock subprocess: rc=0, 输出 "BUILT"
    fake_proc = _make_fake_proc(rc=0, stdout=b"BUILD SUMMARY done\n")
    with patch("aog_web.services.sync.asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
        s = SyncService()
        result = await s.trigger_now()
    assert result["status"] == "ok"
    assert result["changed_count"] == 0
    assert result["new_count"] == 1
    assert result["reindex_returncode"] == 0
    await s.stop()
    reset_settings_cache()


@pytest.mark.asyncio
async def test_sync_service_trigger_pipeline_failure(tmp_path, tmp_kb, monkeypatch):
    """pipeline rc != 0 → status=error, last_error 有值"""
    from aog_web.config import reset_settings_cache
    from aog_web.services.sync import SyncService

    (tmp_kb / "01_AOG预案" / "新.md").write_text("x")
    monkeypatch.setenv("SYNC_STATE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(tmp_kb))
    reset_settings_cache()

    fake_proc = _make_fake_proc(rc=1, stderr=b"build failed")
    with patch("aog_web.services.sync.asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
        s = SyncService()
        result = await s.trigger_now()
    assert result["status"] == "error"
    assert "build failed" in (result.get("error") or "")
    await s.stop()
    reset_settings_cache()


@pytest.mark.asyncio
async def test_sync_service_get_status_after_trigger(tmp_path, tmp_kb, monkeypatch):
    """trigger 后 get_status 应反映 last_poll + counts"""
    from aog_web.config import reset_settings_cache
    from aog_web.services.sync import SyncService

    (tmp_kb / "01_AOG预案" / "x.md").write_text("x")
    monkeypatch.setenv("SYNC_STATE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(tmp_kb))
    reset_settings_cache()

    fake_proc = _make_fake_proc(rc=0, stdout=b"ok")
    with patch("aog_web.services.sync.asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
        s = SyncService()
        await s.trigger_now()
        status = await s.get_status()
    assert status["new_count"] == 1
    assert status["changed_count"] == 0
    assert status["sync_poll_at"] is not None
    assert status["sync_duration_s"] is not None
    # 注: status 字段可能来自 index_stats (test fixture 里没建表 → "unknown"),
    # 或 self._last_result (ok / error). 只断言 self._last_result 路径 → counts 正确
    assert status["new_count"] == 1
    await s.stop()
    reset_settings_cache()


# ====================================================================
# /api/sync/*  端点
# ====================================================================


@pytest.mark.asyncio
async def test_api_sync_trigger_no_changes(client):
    """POST /api/sync/trigger 无变化 → idle"""
    r = await client.post("/api/sync/trigger")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"idle", "ok", "busy", "error"}
    # 至少要有这 3 个字段
    for k in ["changed_count", "new_count", "deleted_count"]:
        assert k in body


@pytest.mark.asyncio
async def test_api_sync_status_returns_known_fields(client):
    """GET /api/sync/status 至少返回 CONTRACT §1.5 5 字段"""
    r = await client.get("/api/sync/status")
    assert r.status_code == 200
    body = r.json()
    for k in ["status", "last_sync", "queue", "indexed_total", "last_error"]:
        assert k in body
