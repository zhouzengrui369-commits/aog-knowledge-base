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


def _insert_wiki_from_staging(con: sqlite3.Connection, wiki_dir: Path) -> int:
    """P1-1 治本 (NJX 7/27 14:43 拍 🅰️ 双轨方案): 读 pipeline/data/wiki/*.md 写 chunks_fts

    目的: 让 RAG chat 5 段式 query 召到 wiki 页面 (P1-1 优先)
    输入: pipeline/data/wiki/MOC-{code}-{topic}.md (frontmatter + markdown 内容)
    输出: 1 个 wiki page = 1 个 chunk (整页 1 chunk, 不再切)
          source_type='wiki' 让 fts5_client 的 where filter 命中
          doc_id='MOC-{code}-{topic}' 用于 href /wiki/{code}
    """
    if not wiki_dir.exists():
        logger.warning("wiki_dir not found: %s, skip wiki_fts", wiki_dir)
        return 0
    md_files = sorted(wiki_dir.glob("MOC-*.md"))
    if not md_files:
        logger.info("no wiki files in %s, skip wiki_fts", wiki_dir)
        return 0
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

        code = front_matter.get("code") or md.stem.split("-", 2)[1]  # MOC-X-西安-故障树 → X-西安
        name = front_matter.get("name") or code.split("-", 1)[-1] if "-" in code else code
        topic = front_matter.get("topic") or (md.stem.split("-", 2)[2] if md.stem.count("-") >= 2 else "故障树")
        source_path = front_matter.get("source") or f"pipeline/data/wiki/{md.name}"
        chunk_id = f"wiki:MOC-{code}-{topic}:0"
        fts_rows.append((
            content, name, source_path, f"MOC-{code}-{topic}", "wiki", "", "", f"MOC-{code}-{topic}", 0,
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
    args = p.parse_args()

    started = time.time()
    args.chroma = args.chroma.resolve()
    args.sqlite = args.sqlite.resolve()
    args.out = args.out.resolve()

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
    wiki_dir = Path(__file__).resolve().parent.parent / "data" / "wiki"
    n_wiki = _insert_wiki_from_staging(con, wiki_dir)

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
    logger.info("  elapsed:  %.1fs", elapsed)


if __name__ == "__main__":
    main()
