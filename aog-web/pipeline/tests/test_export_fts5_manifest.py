"""P0-3 阶段 2B: export_fts5 manifest 8 项自动化测试 (Owner 7/29 严令)

测试目标:
  1. export 命令 exit 0
  2. build_manifest 恰好一行
  3. tokenizer=trigram
  4. build_commit 非空
  5. source_manifest_hash 为 64 位 SHA256
  6. fts5_schema_version 精确匹配
  7. FTS5Client.validate_manifest_or_fail() PASS
  8. 删除 manifest / 改 tokenizer / 改 schema 时均 fail-closed

运行:
  cd aog-web/pipeline
  ../backend/.venv/bin/python -m pytest tests/test_export_fts5_manifest.py -v --tb=short
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

# 把 pipeline/scripts + backend 加进 sys.path
PIPELINE_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PIPELINE_ROOT.parent / "backend"
SCRIPTS_DIR = PIPELINE_ROOT / "scripts"
for p in (str(SCRIPTS_DIR), str(BACKEND_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402

from scripts.export_fts5 import (  # noqa: E402
    EXPECTED_SCHEMA_VERSION,
    EXPECTED_TOKENIZER,
    _create_fts5_db,
    _get_git_commit,
    _hash_sqlite_manifest,
    _write_build_manifest,
)


def _run(coro):
    """sync 包装 async 测试, 不依赖 pytest-asyncio"""
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ============ 1. export _write_build_manifest 基础: exit 0 + 1 行 + 字段正确 ============

class TestManifestWrite:
    """测试 _write_build_manifest 函数本身"""

    @pytest.fixture
    def tmp_fts5(self, tmp_path: Path) -> Path:
        """临时 fts5 db (含 schema)"""
        out = tmp_path / "fts5_index.db"
        con = _create_fts5_db(out)
        con.close()
        return out

    @pytest.fixture
    def tmp_source_db(self, tmp_path: Path) -> Path:
        """临时 aog.db (sqlite file)"""
        p = tmp_path / "aog.db"
        p.write_bytes(b"fake aog.db content for hash test " * 100)
        return p

    def test_write_manifest_exit_zero(self, tmp_fts5: Path):
        """1. 写 manifest 成功 (无异常 → exit 0)"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="abc1234567890",
            build_branch="p0/integration-main-convergence",
            source_manifest_hash="0" * 64,
            chunks_count=100, exp_count=5, cities_count=50,
            core_count=3, wiki_count=2,
            db_size_bytes=12345,
            schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        con.close()
        assert tmp_fts5.exists()

    def test_manifest_one_row(self, tmp_fts5: Path):
        """2. build_manifest 恰好一行"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="abc1234",
            build_branch="main",
            source_manifest_hash="0" * 64,
            chunks_count=1, exp_count=1, cities_count=1, core_count=1, wiki_count=1,
            db_size_bytes=100, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        # 再写一次 (UPSERT) → 仍 1 行
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="def5678",
            build_branch="main",
            source_manifest_hash="1" * 64,
            chunks_count=2, exp_count=2, cities_count=2, core_count=2, wiki_count=2,
            db_size_bytes=200, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        rows = con.execute("SELECT count(*) FROM build_manifest").fetchone()[0]
        con.close()
        assert rows == 1, f"build_manifest 应仅 1 行, 实际 {rows}"

    def test_manifest_tokenizer_trigram(self, tmp_fts5: Path):
        """3. tokenizer=trigram"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="x", build_branch="b",
            source_manifest_hash="0" * 64,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=0, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        row = con.execute("SELECT tokenizer FROM build_manifest WHERE id=1").fetchone()
        con.close()
        assert row[0] == "trigram", f"tokenizer 应 'trigram', 实际 {row[0]!r}"

    def test_manifest_build_commit_nonempty(self, tmp_fts5: Path):
        """4. build_commit 非空"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="abc123def456",
            build_branch="p0/integration-main-convergence",
            source_manifest_hash="0" * 64,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=0, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        commit = con.execute("SELECT build_commit FROM build_manifest WHERE id=1").fetchone()[0]
        con.close()
        assert commit and len(commit) >= 7, f"build_commit 应非空且 ≥ 7 字符, 实际 {commit!r}"

    def test_manifest_source_hash_sha256(self, tmp_fts5: Path, tmp_source_db: Path):
        """5. source_manifest_hash 为 64 位 SHA256"""
        h = _hash_sqlite_manifest(tmp_source_db)
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="abc",
            build_branch="b",
            source_manifest_hash=h,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=0, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        row_hash = con.execute("SELECT source_manifest_hash FROM build_manifest WHERE id=1").fetchone()[0]
        con.close()
        assert len(row_hash) == 64, f"hash 应 64 字符 SHA256, 实际 {len(row_hash)}"
        assert all(c in "0123456789abcdef" for c in row_hash), f"hash 应只含 0-9a-f, 实际 {row_hash!r}"
        assert row_hash == h, f"manifest hash 应等于计算值, 实际 {row_hash!r} != {h!r}"

    def test_manifest_schema_version_exact(self, tmp_fts5: Path):
        """6. fts5_schema_version 精确匹配 EXPECTED_SCHEMA_VERSION"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="x",
            build_branch="b",
            source_manifest_hash="0" * 64,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=0, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        ver = con.execute("SELECT fts5_schema_version FROM build_manifest WHERE id=1").fetchone()[0]
        con.close()
        assert ver == EXPECTED_SCHEMA_VERSION, f"schema version 应精确等于 {EXPECTED_SCHEMA_VERSION!r}, 实际 {ver!r}"


# ============ 7+8. FTS5Client.validate_manifest_or_fail PASS / fail-closed ============

class TestValidateManifest:
    """测试 FTS5Client.validate_manifest_or_fail fail-closed 行为"""

    @pytest.fixture
    def tmp_fts5(self, tmp_path: Path) -> Path:
        out = tmp_path / "fts5_index.db"
        con = _create_fts5_db(out)
        con.close()
        return out

    @pytest.fixture
    def written_manifest_db(self, tmp_fts5: Path) -> Path:
        """含合法 manifest 的 fts5 db (db_size/chunks_count 真实值)"""
        # 先写 manifest 用 placeholder, 然后 close, 写 chunks, 再 reopen 写真实 manifest
        # 简化做法: 用 (0, 0, 0) 写 manifest, 然后 close, reopen, 读真实 size + count, 重写 manifest
        con = sqlite3.connect(str(tmp_fts5))
        # 写一个 dummy chunk 测真实 count
        con.execute(
            "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("dummy chunk", "dummy", "f", "T-1", "city", "华北", "现行", "T-1", 0)
        )
        con.commit()
        # close, 看实际 size
        con.close()
        actual_size = tmp_fts5.stat().st_size
        # reopen, 写真实 manifest
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="abc1234567",
            build_branch="p0/integration-main-convergence",
            source_manifest_hash="a" * 64,
            chunks_count=1, exp_count=2, cities_count=3, core_count=1, wiki_count=1,
            db_size_bytes=actual_size, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        con.close()
        return tmp_fts5

    def _make_client(self, db_path: Path):
        """构造 FTS5Client (避免依赖 get_settings singleton)"""
        from aog_web.services.fts5_client import FTS5Client
        return FTS5Client(db_path)

    def test_validate_manifest_pass(self, written_manifest_db: Path):
        """7. 合法 manifest → validate PASS"""
        client = self._make_client(written_manifest_db)
        manifest = _run(client.validate_manifest_or_fail())
        assert manifest["tokenizer"] == "trigram"
        assert manifest["build_commit"] == "abc1234567"
        assert manifest["fts5_schema_version"] == EXPECTED_SCHEMA_VERSION

    def test_validate_no_manifest_fail_closed(self, tmp_fts5: Path):
        """8a. 删除 manifest 行 → fail-closed (RuntimeError)"""
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="build_manifest 不存在"):
            _run(client.validate_manifest_or_fail())

    def test_validate_wrong_tokenizer_fail_closed(self, tmp_fts5: Path):
        """8b. 改 tokenizer=unicode61 → fail-closed"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer="unicode61",  # 故意错
            build_commit="abc",
            build_branch="b",
            source_manifest_hash="0" * 64,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=100, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        con.close()
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="tokenizer"):
            _run(client.validate_manifest_or_fail())

    def test_validate_wrong_schema_version_fail_closed(self, tmp_fts5: Path):
        """8c. 改 schema_version=old → fail-closed"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="abc",
            build_branch="b",
            source_manifest_hash="0" * 64,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=100,
            schema_version="v14-unicode61",  # 故意低版本
        )
        con.commit()
        con.close()
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="fts5_schema_version"):
            _run(client.validate_manifest_or_fail())

    def test_validate_empty_build_commit_fail_closed(self, tmp_fts5: Path):
        """8d. build_commit='unknown' → fail-closed"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="unknown",  # 故意无效
            build_branch="b",
            source_manifest_hash="0" * 64,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=100, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        con.close()
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="build_commit"):
            _run(client.validate_manifest_or_fail())

    def test_validate_zero_db_size_fail_closed(self, tmp_fts5: Path):
        """8e. db_size_bytes=0 → fail-closed"""
        con = sqlite3.connect(str(tmp_fts5))
        _write_build_manifest(
            con,
            tokenizer=EXPECTED_TOKENIZER,
            build_commit="abc",
            build_branch="b",
            source_manifest_hash="0" * 64,
            chunks_count=0, exp_count=0, cities_count=0, core_count=0, wiki_count=0,
            db_size_bytes=0,  # 故意空
            schema_version=EXPECTED_SCHEMA_VERSION,
        )
        con.commit()
        con.close()
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="db_size_bytes"):
            _run(client.validate_manifest_or_fail())

    # ====== P0-7 阶段 7 增强校验 (Owner 7/29 严令) ======

    def _write_realistic_manifest(self, db_path: Path, **overrides) -> Path:
        """写一个真实 manifest (db_size + chunks_count 准确)"""
        con = sqlite3.connect(str(db_path))
        # 写 N 个 chunk (可控)
        n_chunks = overrides.pop("n_chunks", 1)
        for i in range(n_chunks):
            con.execute(
                "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"chunk {i}", "t", "f", f"T-{i}", "city", "华北", "现行", f"T-{i}", 0)
            )
        con.commit()
        con.close()
        # 读实际 size
        actual_size = db_path.stat().st_size
        # reopen 写真实 manifest
        con = sqlite3.connect(str(db_path))
        kwargs = dict(
            tokenizer=EXPECTED_TOKENIZER,
            build_commit=overrides.pop("build_commit", "abc1234567"),
            build_branch=overrides.pop("build_branch", "p0/integration-main-convergence"),
            source_manifest_hash=overrides.pop("source_manifest_hash", "a" * 64),
            chunks_count=n_chunks, exp_count=2, cities_count=3, core_count=1, wiki_count=1,
            db_size_bytes=actual_size, schema_version=EXPECTED_SCHEMA_VERSION,
        )
        kwargs.update(overrides)
        _write_build_manifest(con, **kwargs)
        con.commit()
        con.close()
        return db_path

    def test_validate_db_size_mismatch_fail_closed(self, tmp_fts5: Path):
        """P0-7.6: manifest db_size_bytes 与实际文件大小不一致 → fail-closed"""
        # 写真实 manifest
        self._write_realistic_manifest(tmp_fts5)
        # reopen 改 manifest db_size_bytes 改成假值
        con = sqlite3.connect(str(tmp_fts5))
        con.execute("UPDATE build_manifest SET db_size_bytes = 999999 WHERE id = 1")
        con.commit()
        con.close()
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="db_size_bytes"):
            _run(client.validate_manifest_or_fail())

    def test_validate_chunks_count_mismatch_fail_closed(self, tmp_fts5: Path):
        """P0-7.8: chunks_count manifest 与实际表行数不一致 → fail-closed"""
        self._write_realistic_manifest(tmp_fts5, n_chunks=3)  # 写 3 个
        # 改 manifest chunks_count 改成 100
        con = sqlite3.connect(str(tmp_fts5))
        con.execute("UPDATE build_manifest SET chunks_count = 100 WHERE id = 1")
        con.commit()
        con.close()
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="chunks_count"):
            _run(client.validate_manifest_or_fail())

    def test_validate_app_commit_sha_match_pass(self, tmp_fts5: Path, monkeypatch):
        """P0-7.7: APP_COMMIT_SHA 与 build_commit 前 8 字符匹配 → PASS"""
        real_commit = "abc1234567890"
        self._write_realistic_manifest(tmp_fts5, build_commit=real_commit)
        monkeypatch.setenv("APP_COMMIT_SHA", "abc12345")
        client = self._make_client(tmp_fts5)
        m = _run(client.validate_manifest_or_fail())
        assert m["build_commit"] == real_commit

    def test_validate_app_commit_sha_mismatch_fail_closed(self, tmp_fts5: Path, monkeypatch):
        """P0-7.7: APP_COMMIT_SHA 与 build_commit 不匹配 → fail-closed"""
        self._write_realistic_manifest(tmp_fts5, build_commit="abc1234567")
        monkeypatch.setenv("APP_COMMIT_SHA", "deadbeef")
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="APP_COMMIT_SHA"):
            _run(client.validate_manifest_or_fail())

    def test_validate_no_app_commit_sha_env_skipped(self, tmp_fts5: Path, monkeypatch):
        """P0-7.7: APP_COMMIT_SHA 未设 (dev 环境) → 跳过此校验"""
        monkeypatch.delenv("APP_COMMIT_SHA", raising=False)
        self._write_realistic_manifest(tmp_fts5)
        client = self._make_client(tmp_fts5)
        m = _run(client.validate_manifest_or_fail())  # 不抛
        assert m["tokenizer"] == "trigram"

    def test_validate_source_manifest_hash_mismatch_fail_closed(self, tmp_fts5: Path, tmp_path: Path, monkeypatch):
        """P0-7.9: source_manifest_hash 与 aog.db 实际 SHA256 不一致 → fail-closed"""
        self._write_realistic_manifest(tmp_fts5, source_manifest_hash="a" * 64)
        # 写临时 aog.db
        aog_db = tmp_path / "aog.db"
        aog_db.write_bytes(b"actual aog db content" * 100)
        monkeypatch.setenv("AOG_DB_PATH", str(aog_db))
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="source_manifest_hash"):
            _run(client.validate_manifest_or_fail())

    def test_validate_source_manifest_hash_match_pass(self, tmp_fts5: Path, tmp_path: Path, monkeypatch):
        """P0-7.9: source_manifest_hash 与 aog.db 实际 SHA256 匹配 → PASS"""
        # 写临时 aog.db, 算 sha256
        aog_db = tmp_path / "aog.db"
        content = b"aog db content for hash test" * 50
        aog_db.write_bytes(content)
        import hashlib
        h = hashlib.sha256()
        h.update(content)
        actual_hash = h.hexdigest()
        self._write_realistic_manifest(tmp_fts5, source_manifest_hash=actual_hash)
        monkeypatch.setenv("AOG_DB_PATH", str(aog_db))
        client = self._make_client(tmp_fts5)
        m = _run(client.validate_manifest_or_fail())
        assert m["source_manifest_hash"] == actual_hash

    def test_validate_schema_version_exact_equal_not_less_than(self, tmp_fts5: Path):
        """P0-7.3: schema version 精确等 (不用 < 比较) — 'v30-d038-d043' == 'v30-d038-d043' OK"""
        # 之前 8c test 用 'v14-unicode61' 校验 < 比较, 现在 schema 字段已经改精确等
        # 这里测精确等通过
        self._write_realistic_manifest(tmp_fts5)  # 默认用 EXPECTED_SCHEMA_VERSION
        client = self._make_client(tmp_fts5)
        m = _run(client.validate_manifest_or_fail())  # 不抛
        assert m["fts5_schema_version"] == "v30-d038-d043"

    def test_validate_schema_version_extra_fail_closed(self, tmp_fts5: Path):
        """P0-7.3: 'v30-d038-d043-extra' 也不应通过 (精确等)"""
        self._write_realistic_manifest(tmp_fts5)  # 默认 v30-d038-d043
        con = sqlite3.connect(str(tmp_fts5))
        con.execute("UPDATE build_manifest SET fts5_schema_version = 'v30-d038-d043-extra' WHERE id = 1")
        con.commit()
        con.close()
        client = self._make_client(tmp_fts5)
        with pytest.raises(RuntimeError, match="fts5_schema_version"):
            _run(client.validate_manifest_or_fail())
