"""FTS5 全文检索客户端 - 异步 aiosqlite

设计:
- 单文件: FTS5_PATH (默认 ./data/fts5_index.db)
- 与 ChromaClient 同样接口: query(q, n_results, where)
- BM25 score 归一化到 0-1 (FTS5 bm25() 越小越相关, 取负)
- 智能 query 解析: 拆词 + OR + 引号包裹, 处理中文 2-char / 4-char / 英文混排
- SCF 友好: /tmp 路径, 启动时从 COS 下载 (在 main.py lifespan 协调)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from aog_web.config import get_settings

logger = logging.getLogger(__name__)


# ====== Query 智能解析 ======
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-./#]*")


def _split_query(q: str) -> List[str]:
    """拆 query 为 token list
    - 英文/数字 run 保持完整 (含 . - _ / #)
    - 中文连续段: 按 2-3 字拆 (避免 4+ char phrase 不能匹配)
    """
    q = q.strip()
    if not q:
        return []
    tokens: List[str] = []

    # 1) 先把英文/数字 token 拿出来
    cursor = 0
    for m in _ASCII_TOKEN_RE.finditer(q):
        # m 之前的中文段
        cjk_seg = q[cursor : m.start()]
        tokens.extend(_split_cjk(cjk_seg))
        tokens.append(m.group(0))
        cursor = m.end()
    # 尾部中文段
    tokens.extend(_split_cjk(q[cursor:]))

    # 过滤空 + 单字符
    tokens = [t for t in tokens if len(t) >= 2]
    # 去重保序
    seen = set()
    out = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _split_cjk(seg: str) -> List[str]:
    """中文段拆为 2-3 字 overlap chunks
    例: "风挡维修流程" → ["风挡", "挡维", "维修", "理流", "流程"]
    这样 "风挡" 单独命中 + "维修" 单独命中
    """
    if not seg:
        return []
    seg = seg.strip()
    if len(seg) <= 2:
        return [seg] if seg else []
    out = []
    n = len(seg)
    for i in range(n - 1):
        # 2-gram
        out.append(seg[i : i + 2])
    # 末尾的 3-gram (可选, 减少 noise)
    # for i in range(n - 2):
    #     out.append(seg[i : i + 3])
    return out


def _build_fts5_query(q: str) -> str:
    """构造 FTS5 MATCH 表达式
    - 每个 token 用 "..." 包裹 (避免 dash / CJK 解析问题)
    - 多个 token 用 OR 连接 (召回优先, BM25 排序自然过滤)
    """
    tokens = _split_query(q)
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens)


class FTS5Client:
    """异步 FTS5 客户端 - 单例"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            if not self.db_path.exists():
                raise FileNotFoundError(
                    f"FTS5 index not found: {self.db_path}. "
                    "Run pipeline/scripts/export_fts5.py to build it."
                )
            self._db = await aiosqlite.connect(str(self.db_path))
            # 优化: WAL 模式, 减少读锁
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA synchronous=NORMAL")
        return self._db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def count(self) -> int:
        """chunks 数量"""
        try:
            db = await self._get_db()
            async with db.execute("SELECT count(*) FROM chunks_fts") as cur:
                row = await cur.fetchone()
                return int(row[0]) if row else 0
        except Exception as e:
            logger.warning("fts5 count failed: %s", e)
            return 0

    async def query(
        self,
        q: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """BM25 全文检索 - 模拟 chroma 的 query 接口

        Args:
            q: 原始 query string
            n_results: 返回 top-N (1-20, cap)
            where: 可选 filter, 支持:
                - source_type: 'city' | 'experience' | 'core_plan'
                - region: '华北' | '华东' | ...
                - status: '现行' | '暂停' | '已废'

        Returns:
            List[{id, text, metadata, score}] (score 0-1, 越大越相关)
        """
        if not q or not q.strip():
            return []
        n_results = max(1, min(n_results, 20))

        fts_query = _build_fts5_query(q)
        if not fts_query:
            return []

        where = where or {}
        source_type = where.get("source_type") or where.get("kind")
        region = where.get("region")
        status = where.get("status")

        # 构造 WHERE 子句
        # 注意: source_type/region/status 是 UNINDEXED, 只能走 chunks_meta
        # 走 JOIN 拿 id, 简单可靠
        # 一次 query 拿 content (c0) + 其它 metadata, 避免 N+1
        sql = """
            SELECT
                c.rowid AS rowid,
                cc.c0 AS content,
                c.doc_id AS doc_id,
                c.title AS title,
                c.source_path AS source_path,
                c.source_type AS source_type,
                c.region AS region,
                c.status AS status,
                c.chunk_index AS chunk_index,
                bm25(chunks_fts) AS bm25_score
            FROM chunks_fts c
            JOIN chunks_fts_content cc ON cc.id = c.rowid
            WHERE chunks_fts MATCH ?
        """
        params: List[Any] = [fts_query]
        if source_type:
            sql += " AND c.source_type = ?"
            params.append(source_type)
        if region:
            sql += " AND c.region = ?"
            params.append(region)
        if status:
            sql += " AND c.status = ?"
            params.append(status)
        sql += " ORDER BY bm25_score LIMIT ?"
        params.append(n_results)

        try:
            db = await self._get_db()
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
        except Exception as e:
            logger.error("fts5 query failed: q=%r fts_q=%r err=%s", q[:50], fts_query[:80], e)
            return []

        out: List[Dict[str, Any]] = []
        for row in rows:
            rowid, content, doc_id, title, source_path, source_type, region, status, chunk_index, bm25 = row
            # bm25 越小越相关, score = 1 / (1 + |bm25|) → 0-1
            try:
                bm25_f = float(bm25)
            except (TypeError, ValueError):
                bm25_f = 0.0
            score = 1.0 / (1.0 + abs(bm25_f))
            # doc_id: chroma 的 id (e.g. "city:A-澳门:0") 用 doc_id 字段, 但 rowid 不一样
            # 我们要保留 source_id 形式 ("A-澳门") 给前端 / city:xxx 形式
            # FTS5 的 rowid 不是 chunk 业务 id, 用 source_id + chunk_index 拼
            chunk_id = f"{source_type}:{doc_id}:{chunk_index}" if source_type and doc_id else f"chunk:{rowid}"

            out.append({
                "id": chunk_id,
                "text": content or "",
                "metadata": {
                    "title": title or "",
                    "source_path": source_path or "",
                    "source_id": doc_id or "",
                    "source_type": source_type or "",
                    "region": region or "",
                    "status": status or "",
                    "kind": source_type or "",  # 兼容 chroma metadata.kind
                    "chunk_index": chunk_index or 0,
                },
                "score": round(score, 4),
            })
        return out

    async def _get_content_by_rowid(self, db: aiosqlite.Connection, rowid: int) -> str:
        """从 chunks_fts_content 表拿完整 content (snippet 太短)
        FTS5 内部表用 c0, c1, ... 而不是列名
        """
        try:
            async with db.execute(
                "SELECT c0 FROM chunks_fts_content WHERE id = ?", (rowid,)
            ) as cur:
                row = await cur.fetchone()
                return row[0] if row else ""
        except Exception as e:
            logger.warning("fts5 get_content_by_rowid failed: %s", e)
            return ""

    async def search_cities(self, q: str, n: int = 5, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """城市全文检索 (用于 /api/cities?q=... 与 sqlite_client.list_cities 互补)"""
        if not q or not q.strip():
            return []
        fts_query = _build_fts5_query(q)
        if not fts_query:
            return []
        sql = """
            SELECT code, name, airport, iata, pinyin, region, status, bm25(cities_fts) AS bm25_score
            FROM cities_fts
            WHERE cities_fts MATCH ?
        """
        params: List[Any] = [fts_query]
        if region:
            sql += " AND region = ?"
            params.append(region)
        sql += " ORDER BY bm25_score LIMIT ?"
        params.append(n)
        try:
            db = await self._get_db()
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
        except Exception as e:
            logger.error("fts5 cities search failed: q=%r err=%s", q[:50], e)
            return []
        out = []
        for r in rows:
            code, name, airport, iata, pinyin, region, status, bm25 = r
            try:
                bm25_f = float(bm25)
            except (TypeError, ValueError):
                bm25_f = 0.0
            score = 1.0 / (1.0 + abs(bm25_f))
            out.append({
                "id": code,
                "text": f"{name} ({iata}) - {region}",
                "metadata": {
                    "code": code,
                    "name": name,
                    "airport": airport or "",
                    "iata": iata or "",
                    "pinyin": pinyin or "",
                    "region": region or "",
                    "status": status or "",
                    "kind": "city",
                },
                "score": round(score, 4),
            })
        return out

    async def search_experiences(self, q: str, n: int = 5) -> List[Dict[str, Any]]:
        """经验全文检索"""
        if not q or not q.strip():
            return []
        fts_query = _build_fts5_query(q)
        if not fts_query:
            return []
        sql = """
            SELECT id, title, category, status, tags, bm25(experiences_fts) AS bm25_score
            FROM experiences_fts
            WHERE experiences_fts MATCH ?
            ORDER BY bm25_score LIMIT ?
        """
        try:
            db = await self._get_db()
            async with db.execute(sql, (fts_query, n)) as cur:
                rows = await cur.fetchall()
        except Exception as e:
            logger.error("fts5 experiences search failed: q=%r err=%s", q[:50], e)
            return []
        out = []
        for r in rows:
            eid, title, category, status, tags, bm25 = r
            try:
                bm25_f = float(bm25)
            except (TypeError, ValueError):
                bm25_f = 0.0
            score = 1.0 / (1.0 + abs(bm25_f))
            out.append({
                "id": eid,
                "text": f"{title} ({category})",
                "metadata": {
                    "id": eid,
                    "title": title or "",
                    "category": category or "",
                    "status": status or "",
                    "tags": tags or "[]",
                    "kind": "experience",
                },
                "score": round(score, 4),
            })
        return out


_client: Optional[FTS5Client] = None


def get_fts5_client() -> FTS5Client:
    """获取 FTS5 客户端单例"""
    global _client
    if _client is None:
        s = get_settings()
        _client = FTS5Client(s.fts5_path)
    return _client


def reset_fts5_client() -> None:
    """测试 helper"""
    global _client
    _client = None
