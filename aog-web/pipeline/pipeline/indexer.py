"""Index: 把 chunks + metadata 写 Chroma + SQLite。

设计:
- 每次 build DROP TABLE / collection 全清, 简单可靠
- Chroma collection name: 'aog_knowledge'
- SQLite 三表: cities / experiences / core_plans
- 每个 chunk 在 Chroma 里的 metadata 包含 source_type/source_id/source_path/chunk_index
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

CHROMA_COLLECTION = "aog_knowledge"


# ---------- SQLite ----------

CITIES_SCHEMA = """
CREATE TABLE cities (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    airport TEXT,
    iata TEXT,
    pinyin TEXT,
    region TEXT,
    status TEXT,
    tags TEXT,            -- JSON array string
    fleet TEXT,           -- JSON array string
    parts TEXT,           -- JSON array string
    contacts TEXT,        -- JSON array string
    warehouse TEXT,       -- JSON object string
    logistics TEXT,       -- JSON object string
    content_md TEXT,
    source_path TEXT,
    updated_at TEXT,
    -- ★ P0-5 数据可信度 10 字段 (Owner 7/29 授权, D-044-D)
    source_document TEXT,        -- 源文件相对路径
    source_location TEXT,        -- 源在仓库的位置
    source_version TEXT,         -- 源版本
    reviewed_at TEXT,            -- 最后审核时间 ISO8601
    reviewed_by TEXT,            -- 审核人
    review_status TEXT DEFAULT 'UNVERIFIED',  -- VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED
    confidence REAL,             -- 0.0-1.0
    environment TEXT DEFAULT 'all',  -- dev/staging/production/all
    pii_classification TEXT DEFAULT 'none'  -- none/internal/confidential/restricted
);
"""

EXPERIENCES_SCHEMA = """
CREATE TABLE experiences (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT,
    status TEXT,
    tags TEXT,            -- JSON
    summary TEXT,
    content_md TEXT,
    related_pn TEXT,      -- JSON
    source_path TEXT,
    updated_at TEXT
);
"""

CORE_PLANS_SCHEMA = """
CREATE TABLE core_plans (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    type TEXT,
    content_md TEXT,
    source_path TEXT,
    updated_at TEXT
);
"""


class SqliteIndex:
    """封装 SQLite 写入。"""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(str(self.db_path))
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("PRAGMA synchronous = NORMAL")
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def reset(self) -> None:
        """DROP TABLE IF EXISTS, 全清重建。"""
        with self._conn() as c:
            c.execute("DROP TABLE IF EXISTS cities")
            c.execute("DROP TABLE IF EXISTS experiences")
            c.execute("DROP TABLE IF EXISTS core_plans")
            c.execute(CITIES_SCHEMA)
            c.execute(EXPERIENCES_SCHEMA)
            c.execute(CORE_PLANS_SCHEMA)
            # ★ P0-5: migration idempotent, 旧 aog.db 缺 10 字段时加列
            self._migrate_p05(c)

    def _migrate_p05(self, c) -> None:
        """★ P0-5 migration: 给已存在的 cities 表加 10 字段 (idempotent)

        - 旧 aog.db (7/26 V14 时代) 没 10 字段, ALTER TABLE 补
        - 已存在列 (重复 ALTER) → 静默 skip
        - 新 db 已有 10 字段 → ALTER 失败 (duplicate column) → 静默 skip
        """
        _P05_CITY_COLUMNS = [
            ("source_document", "TEXT"),
            ("source_location", "TEXT"),
            ("source_version", "TEXT"),
            ("reviewed_at", "TEXT"),
            ("reviewed_by", "TEXT"),
            ("review_status", "TEXT DEFAULT 'UNVERIFIED'"),
            ("confidence", "REAL"),
            ("environment", "TEXT DEFAULT 'all'"),
            ("pii_classification", "TEXT DEFAULT 'none'"),
        ]
        for col, col_def in _P05_CITY_COLUMNS:
            try:
                c.execute(f"ALTER TABLE cities ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError as e:
                # duplicate column (idempotent) → 静默
                if "duplicate column" not in str(e).lower():
                    raise

    def upsert_city(self, c: dict) -> None:
        """写入 city 全字段, 含 P0-5 数据可信度 10 字段 (D-044-D)

        c 字典必须含 c['trust'] 字段 (10 字段子字典), 或显式提供 10 字段顶层 key
        旧调用方式 (c.get('source_document') 等) 仍兼容 (向后兼容)
        """
        # ★ P0-5: 优先从 c['trust'] 子字典读, 兼容旧调用 (c 直接有 10 字段)
        trust = c.get("trust", {})
        def _t(key: str, default=None):
            return trust.get(key, c.get(key, default))

        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cities
                (code, name, airport, iata, pinyin, region, status, tags, fleet, parts, contacts, warehouse, logistics, content_md, source_path, updated_at,
                 source_document, source_location, source_version, reviewed_at, reviewed_by, review_status, confidence, environment, pii_classification)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    c["code"],
                    c["name"],
                    c.get("airport", ""),
                    c.get("iata", ""),
                    c.get("pinyin", ""),
                    c.get("region", ""),
                    c.get("status", ""),
                    json.dumps(c.get("tags", []), ensure_ascii=False),
                    json.dumps(c.get("fleet", []), ensure_ascii=False),
                    json.dumps(c.get("parts", []), ensure_ascii=False),
                    json.dumps(c.get("contacts", []), ensure_ascii=False),
                    json.dumps(c.get("warehouse", {}), ensure_ascii=False),
                    json.dumps(c.get("logistics", {}), ensure_ascii=False),
                    c.get("content_md", ""),
                    c.get("source_path", ""),
                    c.get("updated_at", ""),
                    # ★ P0-5: 10 字段 (default UNVERIFIED/all/none)
                    _t("source_document"),
                    _t("source_location"),
                    _t("source_version"),
                    _t("reviewed_at"),
                    _t("reviewed_by"),
                    _t("review_status", "UNVERIFIED"),
                    _t("confidence"),
                    _t("environment", "all"),
                    _t("pii_classification", "none"),
                ),
            )

    def upsert_experience(self, e: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO experiences
                (id, title, category, status, tags, summary, content_md, related_pn, source_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    e["id"],
                    e["title"],
                    e.get("category", ""),
                    e.get("status", ""),
                    json.dumps(e.get("tags", []), ensure_ascii=False),
                    e.get("summary", ""),
                    e.get("content_md", ""),
                    json.dumps(e.get("related_pn", []), ensure_ascii=False),
                    e.get("source_path", ""),
                    e.get("updated_at", ""),
                ),
            )

    def upsert_core_plan(self, p: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO core_plans
                (id, title, type, content_md, source_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    p["id"],
                    p["title"],
                    p.get("type", ""),
                    p.get("content_md", ""),
                    p.get("source_path", ""),
                    p.get("updated_at", ""),
                ),
            )

    def count(self, table: str) -> int:
        with self._conn() as c:
            row = c.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            return int(row["n"])


# ---------- Chroma ----------

class ChromaIndex:
    """封装 Chroma 写入。

    每次 reset 整个 collection (简单可靠)。
    """

    def __init__(self, persist_dir: Path | str, collection_name: str = CHROMA_COLLECTION):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _ensure_client(self):
        if self._client is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        return self._client

    def reset(self) -> None:
        """删 collection, 重建。"""
        client = self._ensure_client()
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def collection(self):
        if self._collection is None:
            client = self._ensure_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_chunks(
        self,
        ids: Sequence[str],
        texts: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        metadatas: Sequence[dict],
    ) -> None:
        """批量添加。chroma 单次 add 上限建议 5000。"""
        if not ids:
            return
        col = self.collection()
        col.add(
            ids=list(ids),
            documents=list(texts),
            embeddings=list(embeddings),
            metadatas=list(metadatas),
        )

    def count(self) -> int:
        return self.collection().count()

    def query(self, query_text: str, n_results: int = 3):
        col = self.collection()
        return col.query(query_texts=[query_text], n_results=n_results)


# ---------- 总入口 ----------

@dataclass
class IndexStats:
    files_scanned: int = 0
    files_indexed: int = 0
    files_failed: list[dict] = None
    chunks_total: int = 0
    cities_count: int = 0
    experiences_count: int = 0
    core_plans_count: int = 0

    def __post_init__(self):
        if self.files_failed is None:
            self.files_failed = []
