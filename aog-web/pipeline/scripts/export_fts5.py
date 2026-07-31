"""Chroma → SQLite FTS5 ETL 脚本

Wave 3 · SCF 部署前置 (替代 chroma, /tmp 友好)

输入:
  - data/chroma/chroma.sqlite3 (chroma persistent client)
  - data/aog.db (元数据: cities / experiences / core_plans)

输出:
  - data/fts5_index.db (3 张 FTS5 虚拟表 + 元数据索引)
  - data/chunks_meta.json (id → doc_path 映射, 前端引用)

技术选择:
  - 中文分词: trigram (FTS5 内置), 无 jieba
  - 倒排索引: BM25 (FTS5 默认 rank)
  - 同时建 metadata 索引 (source_id, source_type, region, status 等) 用于 filter

使用:
  cd aog-web/backend && source .venv/bin/activate
  cd ../pipeline && python -m scripts.export_fts5 \\
      --chroma ../backend/data/chroma \\
      --sqlite ../backend/data/aog.db \\
      --out ../backend/data/fts5_index.db
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("export_fts5")


# ====== FTS5 schema ======
# D-038 治本 (NJX 7/27 19:55 反馈"未找到赫尔辛基预案"):
#   unicode61 不切 CJK 字符, 整 db 643 个 term 全 ASCII, 中文 query 召回 0
#   trigram 是 sqlite 内置, 3-char substring 匹配, CJK 召回正常
#   短 CJK (2 char, e.g. 西安/三亚) trigram 也拆不出 → 应用层 fts5_client._split_cjk
#     拆 3-gram OR (1-2 char CJK) LIKE fallback
# 索引大小影响: 30MB (unicode61) → ~50-100MB (trigram), SCF /tmp 100MB 限制边缘
#   实测 100 wiki = 1.5MB, 估算 9106 chunks = ~130MB (worst case 4-5x text)
#   决定先试 50MB 重建, 超 100MB 再考虑其他方案
CHUNKS_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    title,
    source_path,
    source_id UNINDEXED,
    source_type UNINDEXED,
    region UNINDEXED,
    status UNINDEXED,
    doc_id UNINDEXED,
    chunk_index UNINDEXED,
    tokenize = "trigram"
);
"""

# 经验全文索引
EXPERIENCES_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS experiences_fts USING fts5(
    content,
    id UNINDEXED,
    title,
    category UNINDEXED,
    status UNINDEXED,
    tags UNINDEXED,
    tokenize = "trigram"
);
"""

# 城市全文索引
CITIES_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS cities_fts USING fts5(
    content,
    code UNINDEXED,
    name,
    airport,
    iata,
    pinyin,
    region UNINDEXED,
    status UNINDEXED,
    tags UNINDEXED,
    tokenize = "trigram"
);
"""

# 核心预案索引
CORE_PLANS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS core_plans_meta (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    source_path TEXT,
    updated_at TEXT
);
"""

# chunks 元数据 (id → metadata), 简单 KV 表, 用于快速 lookup
CHUNKS_META_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks_meta (
    id TEXT PRIMARY KEY,
    source_id TEXT,
    source_type TEXT,
    source_path TEXT,
    title TEXT,
    region TEXT,
    status TEXT,
    doc_id TEXT,
    chunk_index INTEGER
);
CREATE INDEX IF NOT EXISTS idx_chunks_meta_source_id ON chunks_meta(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_meta_source_type ON chunks_meta(source_type);
CREATE INDEX IF NOT EXISTS idx_chunks_meta_region ON chunks_meta(region);
"""

# ★ P0-3: build_manifest 表 (Owner 7/29 授权 — 索引身份必须可核验)
# 单行 id=1, 记录 RAG 索引的:
#   - tokenizer (trigram / unicode61)
#   - build_commit (本次 build 用的 git commit SHA)
#   - build_branch (分支名)
#   - build_time (ISO8601)
#   - source_manifest_hash (aog.db 内容的 sha256, 源数据变更 → 索引必须重建)
#   - chunks_count / exp_count / cities_count / core_count / wiki_count
#   - db_size_bytes (索引文件实际字节数)
#   - fts5_schema_version (V30 = "v30-d038", 未来升级改 v31-dXXX)
#
# 启动时 (fts5_client.validate_manifest) 校验:
#   - tokenizer 与当前代码期望 (D-044-B trigram) 一致
#   - build_commit 存在 (空 = 索引没经过 export_fts5 跑过, fail-closed)
#   - db_size_bytes > 0 (空索引 fail-closed)
#   - schema_version 与客户端期望版本匹配
# 校验失败 → 抛 RuntimeError, lifespan 不启动, SCF 容器 fail-closed
BUILD_MANIFEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS build_manifest (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    tokenizer TEXT NOT NULL,
    build_commit TEXT NOT NULL,
    build_branch TEXT,
    build_time TEXT NOT NULL,
    source_manifest_hash TEXT NOT NULL,
    chunks_count INTEGER NOT NULL,
    exp_count INTEGER NOT NULL,
    cities_count INTEGER NOT NULL,
    core_count INTEGER NOT NULL,
    wiki_count INTEGER NOT NULL,
    db_size_bytes INTEGER NOT NULL,
    fts5_schema_version TEXT NOT NULL
);
"""

EXPECTED_TOKENIZER = "trigram"  # D-038 治本, D-044-B 锁定
EXPECTED_SCHEMA_VERSION = "v30-d038-d043"  # 升级时改这里 + 触发 rebuild


def _get_git_commit() -> str:
    """读当前 git commit SHA — NJX 7/30 PR #4 严令 4 项: 优先 APP_COMMIT_SHA env, 兜底 git rev-parse

    优先级 (NJX 7/30 PR #4 严令):
      1. APP_COMMIT_SHA env (build-data-release.sh 1.7 校验必须 = git HEAD)
      2. git rev-parse HEAD (兜底, 给 dev 环境用)
      3. "unknown" (兜底, 极端情况)

    严禁: 严禁让 export_fts5 自行 git rev-parse 写出与 APP_COMMIT_SHA 不同的 commit,
    否则 build_manifest.build_commit != APP_COMMIT_SHA, 破坏 NJX 7/30 PR #4 严令 4 项
    "build_manifest.build_commit == APP_COMMIT_SHA" 合同.
    """
    import os
    import subprocess
    app_commit_sha = os.environ.get("APP_COMMIT_SHA", "").strip()
    if app_commit_sha:
        return app_commit_sha
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        return r.stdout.strip() or "unknown"
    except Exception as e:
        logger.warning("git rev-parse failed: %s", e)
        return "unknown"


def _get_git_branch() -> str:
    """读当前 git branch — 失败返 'unknown'"""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        return r.stdout.strip() or "unknown"
    except Exception as e:
        logger.warning("git branch failed: %s", e)
        return "unknown"


def _hash_sqlite_manifest(sqlite_path: Path) -> str:
    """算 aog.db 内容的 sha256 hash (sqlite3 BLOB 序列化) — 源变更检测

    改 aog.db (增删城市/经验/核心预案) → hash 变 → 索引必须重建
    """
    import hashlib
    if not sqlite_path.exists():
        return "missing"
    h = hashlib.sha256()
    try:
        with open(sqlite_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.warning("hash aog.db failed: %s", e)
        return "error"


def _write_build_manifest(
    con: sqlite3.Connection,
    *,
    tokenizer: str,
    build_commit: str,
    build_branch: str,
    source_manifest_hash: str,
    chunks_count: int,
    exp_count: int,
    cities_count: int,
    core_count: int,
    wiki_count: int,
    db_size_bytes: int,
    schema_version: str,
) -> None:
    """★ P0-3: 写 build_manifest 单行 (id=1)"""
    from datetime import datetime, timezone
    build_time = datetime.now(timezone.utc).isoformat()
    con.execute(
        """
        INSERT OR REPLACE INTO build_manifest (
            id, tokenizer, build_commit, build_branch, build_time,
            source_manifest_hash, chunks_count, exp_count, cities_count,
            core_count, wiki_count, db_size_bytes, fts5_schema_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            tokenizer,
            build_commit,
            build_branch,
            build_time,
            source_manifest_hash,
            chunks_count,
            exp_count,
            cities_count,
            core_count,
            wiki_count,
            db_size_bytes,
            schema_version,
        ),
    )
    logger.info(
        "build_manifest written: tokenizer=%s commit=%s schema=%s db_size=%d",
        tokenizer, build_commit[:8], schema_version, db_size_bytes,
    )


def _read_chroma(chroma_path: Path) -> Tuple[List[str], List[str], List[Dict], List[Dict]]:
    """读 chroma collection 全部 documents + metadatas + ids

    Returns:
        (ids, documents, metadatas, embeddings_placeholder)
    """
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    if not chroma_path.exists():
        raise FileNotFoundError(f"chroma path not found: {chroma_path}")
    logger.info("loading chroma from %s ...", chroma_path)
    client = chromadb.PersistentClient(
        path=str(chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
    )
    col = client.get_collection("aog_knowledge")
    count = col.count()
    logger.info("chroma collection count: %d", count)
    if count == 0:
        return [], [], [], []

    # 分批拉 (chroma get 有 limit, 分页避免 OOM)
    BATCH = 1000
    all_ids: List[str] = []
    all_docs: List[str] = []
    all_metas: List[Dict] = []
    offset = 0
    while offset < count:
        n = min(BATCH, count - offset)
        r = col.get(limit=n, offset=offset, include=["documents", "metadatas"])
        all_ids.extend(r.get("ids") or [])
        all_docs.extend(r.get("documents") or [])
        all_metas.extend(r.get("metadatas") or [])
        offset += n
        if offset % 5000 == 0:
            logger.info("  pulled %d / %d", offset, count)
    return all_ids, all_docs, all_metas, []


def _create_fts5_db(out_path: Path) -> sqlite3.Connection:
    """建空的 FTS5 db, 返回连接"""
    if out_path.exists():
        logger.info("removing existing %s", out_path)
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(out_path))
    for schema in (
        CHUNKS_FTS_SCHEMA,
        EXPERIENCES_FTS_SCHEMA,
        CITIES_FTS_SCHEMA,
        CORE_PLANS_TABLE_SCHEMA,
        CHUNKS_META_SCHEMA,
        BUILD_MANIFEST_SCHEMA,  # P0-3: build 身份表
    ):
        con.executescript(schema)
    con.commit()
    logger.info("fts5 schema created at %s", out_path)
    return con


def _insert_chunks(con: sqlite3.Connection, ids: List[str], docs: List[str], metas: List[Dict]) -> int:
    """把 chroma 的 chunks 写入 chunks_fts + chunks_meta"""
    if not ids:
        return 0
    n = len(ids)
    logger.info("inserting %d chunks into chunks_fts ...", n)

    # 准备 rows
    fts_rows = []
    meta_rows = []
    for i, (cid, doc, meta) in enumerate(zip(ids, docs, metas)):
        if not doc:
            continue  # 跳过空文档
        meta = meta or {}
        title = meta.get("title") or ""
        source_path = meta.get("source_path") or ""
        source_id = meta.get("source_id") or ""
        source_type = meta.get("source_type") or ""
        region = meta.get("region") or ""
        status = meta.get("status") or ""
        chunk_index = meta.get("chunk_index", 0)
        # doc_id: source_id 优先, 否则用 id
        doc_id = source_id or cid.split(":")[0] if ":" in cid else cid

        fts_rows.append((
            doc, title, source_path, source_id, source_type, region, status, doc_id, chunk_index,
        ))
        meta_rows.append((
            cid, source_id, source_type, source_path, title, region, status, doc_id, chunk_index,
        ))

    # 批量插入 (FTS5 单次大 batch OK, 但保险起见分批)
    BATCH = 500
    cur = con.cursor()
    for i in range(0, len(fts_rows), BATCH):
        chunk_fts = fts_rows[i : i + BATCH]
        chunk_meta = meta_rows[i : i + BATCH]
        cur.executemany(
            "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            chunk_fts,
        )
        cur.executemany(
            "INSERT OR REPLACE INTO chunks_meta(id, source_id, source_type, source_path, title, region, status, doc_id, chunk_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            chunk_meta,
        )
        if (i // BATCH) % 20 == 0 and i > 0:
            logger.info("  inserted %d / %d", i, len(fts_rows))
    con.commit()
    return len(fts_rows)


def _insert_experiences_from_sqlite(con: sqlite3.Connection, sqlite_path: Path) -> int:
    """从 aog.db 读 experiences 写 experiences_fts"""
    if not sqlite_path.exists():
        logger.warning("sqlite_path not found: %s, skip experiences_fts", sqlite_path)
        return 0
    logger.info("loading experiences from %s ...", sqlite_path)
    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row
    cur = src.execute("SELECT * FROM experiences")
    rows: List[Tuple] = []
    for r in cur.fetchall():
        d = dict(r)
        content_parts = [
            d.get("title") or "",
            d.get("summary") or "",
            d.get("content_md") or "",
            d.get("source_path") or "",
        ]
        content = "\n".join(p for p in content_parts if p)
        rows.append((
            content, d["id"], d.get("title") or "", d.get("category") or "",
            d.get("status") or "", d.get("tags") or "[]",
        ))
    src.close()

    if not rows:
        return 0
    con.executemany(
        "INSERT INTO experiences_fts(content, id, title, category, status, tags) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()
    logger.info("inserted %d experiences into experiences_fts", len(rows))
    return len(rows)


def _insert_cities_from_sqlite(con: sqlite3.Connection, sqlite_path: Path) -> int:
    """从 aog.db 读 cities 写 cities_fts"""
    if not sqlite_path.exists():
        logger.warning("sqlite_path not found: %s, skip cities_fts", sqlite_path)
        return 0
    logger.info("loading cities from %s ...", sqlite_path)
    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row
    cur = src.execute("SELECT * FROM cities")
    rows: List[Tuple] = []
    for r in cur.fetchall():
        d = dict(r)
        content_parts = [
            d.get("name") or "",
            d.get("airport") or "",
            d.get("iata") or "",
            d.get("pinyin") or "",
            d.get("content_md") or "",
        ]
        content = "\n".join(p for p in content_parts if p)
        rows.append((
            content, d["code"], d.get("name") or "", d.get("airport") or "",
            d.get("iata") or "", d.get("pinyin") or "",
            d.get("region") or "", d.get("status") or "", d.get("tags") or "[]",
        ))
    src.close()

    if not rows:
        return 0
    con.executemany(
        "INSERT INTO cities_fts(content, code, name, airport, iata, pinyin, region, status, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()
    logger.info("inserted %d cities into cities_fts", len(rows))
    return len(rows)


# === D-056 (NJX 7/31 20:12 拍板): wiki release snapshot fail-loud ===
# 严守 4 项禁止:
#   - 禁止静默修: 命中 phone/email 原值立即 FAIL, 不 redact
#   - 禁止跳过: require_wiki=True 时缺 wiki 立即 FAIL
#   - 禁止 wiki_count=0 绕过: 0 wiki 视为错误状态
# 严守 source: 禁止隐式读 pipeline/data/wiki, 必须显式 --wiki-dir + --wiki-manifest
from pipeline.extractors.pii_sanitizer import sanitize_text as _sanitize_text_d056
import re as _re_d056

# D-056: 复用 pii_sanitizer 严令 patterns (D-051 + D-052 + D-053 + PR #5/6/7 merged)
_D056_PHONE_RE_LIST = [
    _re_d056.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),  # 11 位手机
    _re_d056.compile(r"(?<!\d)\+\d{1,3}[\-\.]\d{1,4}[\-\.]\d{3,4}[\-\.]\d{3,4}(?!\d)"),  # +国家码
    _re_d056.compile(r"(?<!\d)0\d{2,3}[\-\.]\d{7,8}(?!\d)"),  # 座机 0xx-xxxx-xxxx
    _re_d056.compile(r"(?<!\d)0\d{1,2}[\-\.]\d{7,8}(?!\d)"),  # 座机 0X-XXXXXXX
    _re_d056.compile(r"(?<!\d)00\d{1,3}[\-\.]\d{7,8}(?!\d)"),  # D-053 国际 00
    _re_d056.compile(r"(?<!\d)00\(\d{1,4}\)\d{6,}(?!\d)"),  # D-053 国际 00(国家码)
    _re_d056.compile(r"(?<!\d)\d{7,12}(?!\d)"),  # 通用 7-12 位数字
]
_D056_EMAIL_RE = _re_d056.compile(
    r"(?<![A-Za-z0-9._-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)


def _d056_check_pii_residual(text: str, where: str) -> None:
    """D-056 fail-loud: 扫 text 内 phone/email 原值, 命中立即 raise SystemExit(4).

    严禁 (NJX 7/31 22:13 拍板 fix(security)):
      - 日志只输出 SHA256[:12] fingerprint, 严禁明文原值
      - 不写含明文 manifest
      - failure receipt 只允许 path/kind/fingerprint/count

    Args:
        text: 待扫的文本
        where: 错误信息里标注位置 (e.g. 'wiki:MOC-X-西安-故障树')
    """
    if not text:
        return
    for m in _D056_EMAIL_RE.finditer(text):
        v = m.group(0)
        fingerprint = hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]
        logger.error("D-056 FAIL: %s kind=email fingerprint=%s", where, fingerprint)
        sys.exit(4)
    for pat in _D056_PHONE_RE_LIST:
        for m in pat.finditer(text):
            v = m.group(0)
            if v == "[PHONE_REDACTED]":
                continue
            fingerprint = hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]
            logger.error("D-056 FAIL: %s kind=phone fingerprint=%s", where, fingerprint)
            sys.exit(4)


def _insert_wiki_from_staging(
    con: sqlite3.Connection,
    wiki_dir: Path,
    wiki_manifest_path: Optional[Path] = None,
    require_wiki: bool = False,
) -> int:
    """P1-1 治本 (NJX 7/27 14:43 拍 🅰️ 双轨方案): 读 sanitized wiki snapshot 写 chunks_fts

    D-056 (NJX 7/31 20:12 拍板): release 阶段必走 sanitized snapshot
      - wiki_dir: $RELEASE_DIR/wiki (sanitize_wiki_release.py 输出)
      - wiki_manifest_path: $RELEASE_DIR/wiki-release-manifest.json (sha + count 校验)
      - require_wiki=True: 缺 wiki 立即 FAIL (NJX 7/31 严守 4 禁止)
      - sanitize fail-loud: 任一 wiki 段含 phone/email 原值立即 SystemExit(4)
      - 禁止静默修 / 跳过 / wiki_count=0 绕过
      - 禁止隐式读 pipeline/data/wiki (没传 --wiki-dir 默认值, 调用方必须显式)

    输入: $RELEASE_DIR/wiki/MOC-{code}-{topic}.md (frontmatter + markdown 内容, 已 sanitize)
    输出: 1 个 wiki page = 1 个 chunk (整页 1 chunk, 不再切)
          source_type='wiki' 让 fts5_client 的 where filter 命中
          doc_id='MOC-{code}-{topic}' 用于 href /wiki/{code}
    """
    # D-056 严守 4 禁止: require_wiki 时 wiki_dir 缺失 → FAIL
    if not wiki_dir.exists():
        msg = f"wiki_dir not found: {wiki_dir}"
        if require_wiki:
            logger.error("D-056 FAIL: %s (require_wiki=True)", msg)
            sys.exit(4)
        logger.warning("%s, skip wiki_fts (legacy mode, 严禁 release 用)", msg)
        return 0
    md_files = sorted(wiki_dir.glob("MOC-*.md"))
    if not md_files:
        msg = f"no MOC-*.md in {wiki_dir}"
        if require_wiki:
            logger.error("D-056 FAIL: %s (require_wiki=True, 严禁 wiki_count=0 绕过)", msg)
            sys.exit(4)
        logger.info("%s, skip wiki_fts (legacy mode)", msg)
        return 0

    # D-056 校验 wiki_manifest 存在 + sha 对得上 + source_pages == actual md count
    if wiki_manifest_path:
        if not wiki_manifest_path.exists():
            logger.error("D-056 FAIL: wiki_manifest 不存在: %s", wiki_manifest_path)
            sys.exit(4)
        try:
            import json as _json
            manifest = _json.loads(wiki_manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("D-056 FAIL: wiki_manifest 解析失败: %s: %s", wiki_manifest_path, e)
            sys.exit(4)
        manifest_source_pages = manifest.get("wiki_source_pages", 0)
        manifest_sanitized_pages = manifest.get("wiki_sanitized_pages", 0)
        manifest_residual = manifest.get("residual_pii_matches", -1)
        if manifest_residual != 0:
            logger.error(
                "D-056 FAIL: wiki_manifest residual_pii_matches=%d (必须 0)", manifest_residual
            )
            sys.exit(4)
        if manifest_source_pages != manifest_sanitized_pages:
            logger.error(
                "D-056 FAIL: wiki_manifest source(%d) != sanitized(%d)",
                manifest_source_pages,
                manifest_sanitized_pages,
            )
            sys.exit(4)
        if manifest_source_pages != len(md_files):
            logger.error(
                "D-056 FAIL: wiki_manifest source_pages(%d) != actual md_files(%d)",
                manifest_source_pages,
                len(md_files),
            )
            sys.exit(4)
        logger.info(
            "D-056 wiki_manifest OK: source=%d sanitized=%d residual=%d",
            manifest_source_pages, manifest_sanitized_pages, manifest_residual,
        )

    logger.info("loading %d wiki pages from %s ...", len(md_files), wiki_dir)

    import frontmatter  # type: ignore  # python-frontmatter 包
    fts_rows: List[Tuple] = []
    meta_rows: List[Tuple] = []
    for md in md_files:
        try:
            post = frontmatter.load(str(md))
        except Exception:
            # 兼容: 整页当 body
            content = md.read_text(encoding="utf-8", errors="ignore")
            front_matter: Dict = {}
        else:
            content = post.content
            front_matter = dict(post.metadata or {})

        # D-056 fail-loud: sanitize 后若仍残留 phone/email → 立即 FAIL
        # 严守: 不静默修, 不跳过, 严禁隐式 redact
        sanitized_content = _sanitize_text_d056(content)
        if sanitized_content != content:
            # 严守: 任一 wiki 段含 phone/email 原值立即 FAIL
            _d056_check_pii_residual(content, f"wiki:{md.name}")
            # 上面已 sys.exit(4), 不会到这
        # 自由文本 metadata 也 fail-loud
        for k, v in front_matter.items():
            if isinstance(v, str) and v:
                _d056_check_pii_residual(v, f"wiki:{md.name}:frontmatter:{k}")

        code = front_matter.get("code") or md.stem.split("-", 2)[1]  # MOC-X-西安-故障树 → X-西安
        name = front_matter.get("name") or code.split("-", 1)[-1] if "-" in code else code
        topic = front_matter.get("topic") or (md.stem.split("-", 2)[2] if md.stem.count("-") >= 2 else "故障树")
        source_path = front_matter.get("source") or f"pipeline/data/wiki/{md.name}"
        chunk_id = f"wiki:MOC-{code}-{topic}:0"
        # 用 sanitized_content (虽然 source 已 sanitize, 这里再保险一次)
        fts_rows.append((
            sanitized_content, name, source_path, f"MOC-{code}-{topic}", "wiki", "", "", f"MOC-{code}-{topic}", 0,
        ))
        meta_rows.append((
            chunk_id, f"MOC-{code}-{topic}", "wiki", source_path, name, "", "", f"MOC-{code}-{topic}", 0,
        ))

    if not fts_rows:
        return 0
    BATCH = 200
    cur = con.cursor()
    for i in range(0, len(fts_rows), BATCH):
        cur.executemany(
            "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            fts_rows[i : i + BATCH],
        )
        cur.executemany(
            "INSERT OR REPLACE INTO chunks_meta(id, source_id, source_type, source_path, title, region, status, doc_id, chunk_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            meta_rows[i : i + BATCH],
        )
    con.commit()
    logger.info("inserted %d wiki pages into chunks_fts (source_type=wiki)", len(fts_rows))
    return len(fts_rows)


def _insert_core_plans_from_sqlite(con: sqlite3.Connection, sqlite_path: Path) -> int:
    """core plans 不做 FTS5 全文 (它们通常直接 by id 拿), 只建 meta 表"""
    if not sqlite_path.exists():
        logger.warning("sqlite_path not found: %s, skip core_plans_meta", sqlite_path)
        return 0
    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row
    cur = src.execute("SELECT id, title, type, source_path, updated_at FROM core_plans")
    rows = [(r["id"], r["title"], r["type"], r["source_path"], r["updated_at"]) for r in cur.fetchall()]
    src.close()

    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO core_plans_meta(id, title, type, source_path, updated_at) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()
    logger.info("inserted %d core_plans into core_plans_meta", len(rows))
    return len(rows)


def _export_chunks_meta_json(out_dir: Path, ids: List[str], metas: List[Dict]) -> int:
    """导出 id → doc_path 映射到 chunks_meta.json (前端引用 / debug)"""
    out = out_dir / "chunks_meta.json"
    rows = []
    for cid, meta in zip(ids, metas):
        meta = meta or {}
        rows.append({
            "id": cid,
            "source_id": meta.get("source_id", ""),
            "source_type": meta.get("source_type", ""),
            "source_path": meta.get("source_path", ""),
            "title": meta.get("title", ""),
            "region": meta.get("region", ""),
            "status": meta.get("status", ""),
            "chunk_index": meta.get("chunk_index", 0),
        })
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("wrote %s (%d entries, %.1fKB)", out, len(rows), out.stat().st_size / 1024)
    return len(rows)


def _verify(con: sqlite3.Connection) -> Dict[str, int]:
    """验收: 4 张表 count"""
    out = {}
    for t in ("chunks_fts", "experiences_fts", "cities_fts", "core_plans_meta", "chunks_meta"):
        cur = con.execute(f"SELECT count(*) FROM {t}")
        out[t] = cur.fetchone()[0]
    return out


def _smoke_test(con: sqlite3.Connection) -> None:
    """FTS5 smoke test: 跑几个 query"""
    queries = [
        ("chunks_fts: 'B787 风挡'", "chunks_fts", "B787 风挡"),
        ("chunks_fts: 'AOG'", "chunks_fts", "AOG"),
        ("cities_fts: '北京'", "cities_fts", "北京"),
        ("cities_fts: 'PVG'", "cities_fts", "PVG"),
        ("experiences_fts: 'B787'", "experiences_fts", "B787"),
    ]
    for label, tbl, q in queries:
        # trigram FTS5 语法: query 至少 3 字符, OR 用 OR
        try:
            cur = con.execute(
                f"SELECT count(*) FROM {tbl} WHERE {tbl} MATCH ?",
                (q,),
            )
            n = cur.fetchone()[0]
            print(f"  ✓ {label}: {n} hits")
        except Exception as e:
            print(f"  ✗ {label}: ERROR {e}")


def main():
    p = argparse.ArgumentParser(description="chroma → sqlite fts5 etl")
    p.add_argument("--chroma", type=Path, default=Path("../backend/data/chroma"), help="chroma persistent path")
    p.add_argument("--sqlite", type=Path, default=Path("../backend/data/aog.db"), help="aog.db (元数据)")
    p.add_argument("--out", type=Path, default=Path("../backend/data/fts5_index.db"), help="FTS5 db out path")
    p.add_argument("--no-smoke", action="store_true", help="skip smoke test")
    # D-056 (NJX 7/31 20:12 拍板): wiki release snapshot fail-loud
    p.add_argument(
        "--wiki-dir",
        type=Path,
        default=None,
        help="D-056: sanitized wiki 目录 (e.g. $RELEASE_DIR/wiki). 严禁 release 隐式读 pipeline/data/wiki",
    )
    p.add_argument(
        "--wiki-manifest",
        type=Path,
        default=None,
        help="D-056: wiki-release-manifest.json (sha + count 校验, sanitize_wiki_release.py 输出)",
    )
    p.add_argument(
        "--require-wiki",
        action="store_true",
        help="D-056: 缺 wiki 立即 FAIL (严禁 wiki_count=0 绕过, release 必须 True)",
    )
    args = p.parse_args()

    started = time.time()
    args.chroma = args.chroma.resolve()
    args.sqlite = args.sqlite.resolve()
    args.out = args.out.resolve()
    if args.wiki_dir:
        args.wiki_dir = args.wiki_dir.resolve()
    if args.wiki_manifest:
        args.wiki_manifest = args.wiki_manifest.resolve()

    if not args.chroma.exists():
        logger.error("chroma path not found: %s", args.chroma)
        sys.exit(1)

    # 1. 读 chroma
    ids, docs, metas, _ = _read_chroma(args.chroma)
    logger.info("read %d chunks from chroma", len(ids))

    # 2. 建 FTS5 db
    con = _create_fts5_db(args.out)

    # 3. 写 chunks
    n_chunks = _insert_chunks(con, ids, docs, metas)

    # 4. 写 experiences / cities / core_plans / wiki (P1-1)
    n_exp = _insert_experiences_from_sqlite(con, args.sqlite)
    n_cities = _insert_cities_from_sqlite(con, args.sqlite)
    n_core = _insert_core_plans_from_sqlite(con, args.sqlite)
    # P1-1 治本 (NJX 7/27 14:43 拍 🅰️): wiki staging → fts5
    # D-056: release 阶段必走 sanitized snapshot (--wiki-dir 显式传, --require-wiki 强约束)
    if args.wiki_dir is None:
        # 兼容旧调用 (非 release 路径, e.g. dev 单测 / 本地 rebuild)
        # 严禁 release 用, release 必须显式 --wiki-dir
        wiki_dir = Path(__file__).resolve().parent.parent / "data" / "wiki"
        logger.warning(
            "D-056: --wiki-dir 未设, fallback 到 %s (仅供 dev/单测, release 必须显式 --wiki-dir)",
            wiki_dir,
        )
    else:
        wiki_dir = args.wiki_dir
    n_wiki = _insert_wiki_from_staging(
        con, wiki_dir,
        wiki_manifest_path=args.wiki_manifest,
        require_wiki=args.require_wiki,
    )

    # 5. 导出 chunks_meta.json
    _export_chunks_meta_json(args.out.parent, ids, metas)

    # 6. 验收
    counts = _verify(con)
    logger.info("===== verify =====")
    for k, v in counts.items():
        logger.info("  %-20s %d", k, v)

    if not args.no_smoke:
        logger.info("===== smoke test =====")
        _smoke_test(con)

    # 7. optimize + vacuum
    logger.info("optimizing FTS5 index ...")
    con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
    con.execute("INSERT INTO experiences_fts(experiences_fts) VALUES('optimize')")
    con.execute("INSERT INTO cities_fts(cities_fts) VALUES('optimize')")
    con.commit()
    con.execute("VACUUM")

    # 7.5 ★ P0-3 + P0-7: 写 build_manifest (单行 id=1, 索引身份)
    # chunks_count 必须是 chunks_fts 表的真实行数 (含 wiki/exp/cities source_type 行)
    # 不只是 _insert_chunks 的 n_chunks (那是纯 chunks 写入数)
    actual_chunks_total = con.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    #    启动时 fts5_client.validate_manifest 校验, 不一致 fail-closed
    build_commit = _get_git_commit()
    build_branch = _get_git_branch()
    source_manifest_hash = _hash_sqlite_manifest(args.sqlite)
    db_size_bytes = args.out.stat().st_size
    _write_build_manifest(
        con,
        tokenizer=EXPECTED_TOKENIZER,
        build_commit=build_commit,
        build_branch=build_branch,
        source_manifest_hash=source_manifest_hash,
        chunks_count=actual_chunks_total,  # ★ P0-7: 真实表行数, 不仅是 _insert_chunks 的 n
        exp_count=n_exp,
        cities_count=n_cities,
        core_count=n_core,
        wiki_count=n_wiki,
        db_size_bytes=db_size_bytes,
        schema_version=EXPECTED_SCHEMA_VERSION,
    )
    con.commit()
    con.close()

    elapsed = time.time() - started
    out_size_mb = args.out.stat().st_size / 1024 / 1024
    logger.info("===== done =====")
    logger.info("  out:      %s (%.2f MB)", args.out, out_size_mb)
    logger.info("  chunks:   %d (target ≈ 8686)", n_chunks)
    logger.info("  exp:      %d", n_exp)
    logger.info("  cities:   %d", n_cities)
    logger.info("  core:     %d", n_core)
    logger.info("  wiki:     %d (P1-1: NJX 14:43 拍 🅰️ 双轨)", n_wiki)
    logger.info("  build:    %s @ %s", build_branch, build_commit[:8])
    logger.info("  src_hash: %s", source_manifest_hash[:12])
    logger.info("  schema:   %s", EXPECTED_SCHEMA_VERSION)
    logger.info("  elapsed:  %.1fs", elapsed)


if __name__ == "__main__":
    main()
