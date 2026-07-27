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
_CJK_CHAR = "\u4e00-\u9fff"


def _split_query(q: str) -> Dict[str, List[str]]:
    """拆 query 为 tokens + short_cjk 短 CJK 段

    D-038 治本 (NJX 7/27 19:55 反馈"未找到赫尔辛基预案"):
      unicode61 tokenizer 不切 CJK, 整 db 643 个 term 全 ASCII
      trigram tokenizer 3-char substring, 召回 CJK 正常
      短 CJK (2 char, e.g. 西安/三亚/广州) trigram 拆不出 → fallback 走 LIKE 全文扫

    Returns:
        {
            "tokens": List[str]   # 走 FTS5 trigram 的 3-gram
            "short_cjk": List[str]  # 2 char CJK 段, 走 LIKE 全文扫 fallback
        }
    """
    q = q.strip()
    if not q:
        return {"tokens": [], "short_cjk": []}

    trigram_tokens: List[str] = []
    short_cjk_tokens: List[str] = []
    cursor = 0

    for m in _ASCII_TOKEN_RE.finditer(q):
        cjk_seg = q[cursor : m.start()]
        _split_cjk_segment(cjk_seg, trigram_tokens, short_cjk_tokens)
        trigram_tokens.append(m.group(0))
        cursor = m.end()
    _split_cjk_segment(q[cursor:], trigram_tokens, short_cjk_tokens)

    trigram_tokens = [t for t in trigram_tokens if len(t) >= 3]
    short_cjk_tokens = [t for t in short_cjk_tokens if 2 <= len(t) <= 2]
    trigram_tokens = _dedup(trigram_tokens)
    short_cjk_tokens = _dedup(short_cjk_tokens)
    return {"tokens": trigram_tokens, "short_cjk": short_cjk_tokens}


def _split_cjk_segment(seg: str, trigram_out: List[str], short_out: List[str]) -> None:
    """中文段拆 3-gram (走 FTS5) + 2 char (走 LIKE fallback)"""
    if not seg:
        return
    seg = seg.strip()
    n = len(seg)
    if n == 0:
        return
    if n <= 2:
        # 1-2 char CJK: 短 token, 走 LIKE fallback
        if all("\u4e00" <= c <= "\u9fff" for c in seg):
            short_out.append(seg)
        return
    # 3+ char: 拆 3-gram overlap
    for i in range(n - 2):
        gram = seg[i : i + 3]
        if all("\u4e00" <= c <= "\u9fff" for c in gram):
            trigram_out.append(gram)
    # 2-gram 也加入 short_cjk (作为 LIKE fallback 冗余, 防 trigram 漏召)
    for i in range(n - 1):
        gram = seg[i : i + 2]
        if all("\u4e00" <= c <= "\u9fff" for c in gram):
            short_out.append(gram)


def _dedup(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _build_fts5_query(q: str) -> str:
    """构造 FTS5 MATCH 表达式 (D-038 治本 trigram)
    - 3-gram 3+ char CJK token + 英文/数字 run
    - 多个 token 用 OR 连接 (召回优先, BM25 排序自然过滤)
    - 2 char CJK 段走 LIKE fallback (fts5_client.query 中处理)
    """
    parsed = _split_query(q)
    tokens = parsed["tokens"]
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

        parsed = _split_query(q)
        fts_tokens = parsed["tokens"]
        short_cjk = parsed["short_cjk"]
        fts_query = _build_fts5_query(q) if fts_tokens else ""

        where = where or {}
        source_type = where.get("source_type") or where.get("kind")
        region = where.get("region")
        status = where.get("status")

        # 1) 主路径: FTS5 trigram MATCH (3+ char CJK / 英文)
        fts_rows: List[Tuple] = []
        if fts_query:
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
            # trigram OR 召回较松, 多取一些 (2x n_results), 后面用 LIKE 合并去重
            sql += " ORDER BY bm25_score LIMIT ?"
            params.append(n_results * 2)
            try:
                db = await self._get_db()
                async with db.execute(sql, params) as cur:
                    fts_rows = await cur.fetchall()
            except Exception as e:
                logger.error("fts5 query failed: q=%r fts_q=%r err=%s", q[:50], fts_query[:80], e)
                fts_rows = []

        # 2) 短 CJK LIKE fallback (2 char, e.g. 西安/三亚/广州)
        #    trigram 拆不出 2 char, 必须走 LIKE 全文扫
        like_rows: List[Tuple] = []
        if short_cjk:
            # 构造 LIKE: 多个 short_cjk OR
            like_clauses = " OR ".join(["cc.c0 LIKE ?"] * len(short_cjk))
            sql2 = f"""
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
                    0.0 AS bm25_score
                FROM chunks_fts c
                JOIN chunks_fts_content cc ON cc.id = c.rowid
                WHERE {like_clauses}
            """
            params2: List[Any] = [f"%{t}%" for t in short_cjk]
            if source_type:
                sql2 += " AND c.source_type = ?"
                params2.append(source_type)
            if region:
                sql2 += " AND c.region = ?"
                params2.append(region)
            if status:
                sql2 += " AND c.status = ?"
                params2.append(status)
            sql2 += " LIMIT ?"
            params2.append(n_results * 2)
            try:
                db = await self._get_db()
                async with db.execute(sql2, params2) as cur:
                    like_rows = await cur.fetchall()
            except Exception as e:
                logger.warning("fts5 LIKE fallback failed: q=%r err=%s", q[:50], e)
                like_rows = []

        # 3) 合并去重 (按 rowid), 优先 FTS5 结果 (有 bm25 score)
        seen_rowids: set = set()
        merged: List[Tuple] = []
        for row in fts_rows:
            if row[0] not in seen_rowids:
                seen_rowids.add(row[0])
                merged.append(row)
        for row in like_rows:
            if row[0] not in seen_rowids:
                seen_rowids.add(row[0])
                merged.append(row)

        out: List[Dict[str, Any]] = []
        for row in merged[:n_results]:
            rowid, content, doc_id, title, source_path, source_type, region, status, chunk_index, bm25 = row
            try:
                bm25_f = float(bm25)
            except (TypeError, ValueError):
                bm25_f = 0.0
            if bm25_f == 0.0 and short_cjk:
                # LIKE fallback 命中: 给一个合理的 score (0.5-0.8 区间)
                bm25_f = -1.0  # 视为较弱相关
            score = 1.0 / (1.0 + abs(bm25_f))
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
                    "kind": source_type or "",
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
        """城市全文检索 (用于 /api/cities?q=... 与 sqlite_client.list_cities 互补)
        D-038: 加 short_cjk LIKE fallback (2 char 城市名 e.g. 西安/三亚/广州)
        """
        if not q or not q.strip():
            return []
        parsed = _split_query(q)
        fts_tokens = parsed["tokens"]
        short_cjk = parsed["short_cjk"]
        fts_query = _build_fts5_query(q) if fts_tokens else ""

        fts_rows: List[Tuple] = []
        if fts_query:
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
            params.append(n * 2)
            try:
                db = await self._get_db()
                async with db.execute(sql, params) as cur:
                    fts_rows = await cur.fetchall()
            except Exception as e:
                logger.error("fts5 cities search failed: q=%r err=%s", q[:50], e)
                fts_rows = []

        # 短 CJK LIKE fallback (e.g. "西安" 查 cities.name)
        like_rows: List[Tuple] = []
        if short_cjk:
            like_clauses = " OR ".join(["name LIKE ? OR pinyin LIKE ?"] * len(short_cjk))
            sql2 = f"""
                SELECT code, name, airport, iata, pinyin, region, status, 0.0 AS bm25_score
                FROM cities_fts
                WHERE {like_clauses}
            """
            params2: List[Any] = []
            for t in short_cjk:
                params2.extend([f"%{t}%", f"%{t}%"])
            if region:
                sql2 += " AND region = ?"
                params2.append(region)
            sql2 += " LIMIT ?"
            params2.append(n * 2)
            try:
                db = await self._get_db()
                async with db.execute(sql2, params2) as cur:
                    like_rows = await cur.fetchall()
            except Exception as e:
                logger.warning("fts5 cities LIKE fallback failed: q=%r err=%s", q[:50], e)
                like_rows = []

        # 合并去重
        seen_codes: set = set()
        merged: List[Tuple] = []
        for r in fts_rows:
            if r[0] not in seen_codes:
                seen_codes.add(r[0])
                merged.append(r)
        for r in like_rows:
            if r[0] not in seen_codes:
                seen_codes.add(r[0])
                merged.append(r)

        out = []
        for r in merged[:n]:
            code, name, airport, iata, pinyin, region, status, bm25 = r
            try:
                bm25_f = float(bm25)
            except (TypeError, ValueError):
                bm25_f = 0.0
            if bm25_f == 0.0 and short_cjk:
                bm25_f = -1.0
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
        """经验全文检索
        D-038: trigram 主路径, 短 CJK LIKE fallback
        """
        if not q or not q.strip():
            return []
        parsed = _split_query(q)
        fts_tokens = parsed["tokens"]
        short_cjk = parsed["short_cjk"]
        fts_query = _build_fts5_query(q) if fts_tokens else ""

        fts_rows: List[Tuple] = []
        if fts_query:
            sql = """
                SELECT id, title, category, status, tags, bm25(experiences_fts) AS bm25_score
                FROM experiences_fts
                WHERE experiences_fts MATCH ?
                ORDER BY bm25_score LIMIT ?
            """
            try:
                db = await self._get_db()
                async with db.execute(sql, (fts_query, n * 2)) as cur:
                    fts_rows = await cur.fetchall()
            except Exception as e:
                logger.error("fts5 experiences search failed: q=%r err=%s", q[:50], e)
                fts_rows = []

        # 短 CJK LIKE fallback
        like_rows: List[Tuple] = []
        if short_cjk:
            like_clauses = " OR ".join(["title LIKE ?"] * len(short_cjk))
            sql2 = f"""
                SELECT id, title, category, status, tags, 0.0 AS bm25_score
                FROM experiences_fts
                WHERE {like_clauses}
                LIMIT ?
            """
            params2: List[Any] = [f"%{t}%" for t in short_cjk] + [n * 2]
            try:
                db = await self._get_db()
                async with db.execute(sql2, params2) as cur:
                    like_rows = await cur.fetchall()
            except Exception as e:
                logger.warning("fts5 experiences LIKE fallback failed: q=%r err=%s", q[:50], e)
                like_rows = []

        seen_ids: set = set()
        merged: List[Tuple] = []
        for r in fts_rows:
            if r[0] not in seen_ids:
                seen_ids.add(r[0])
                merged.append(r)
        for r in like_rows:
            if r[0] not in seen_ids:
                seen_ids.add(r[0])
                merged.append(r)

        out = []
        for r in merged[:n]:
            eid, title, category, status, tags, bm25 = r
            try:
                bm25_f = float(bm25)
            except (TypeError, ValueError):
                bm25_f = 0.0
            if bm25_f == 0.0 and short_cjk:
                bm25_f = -1.0
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
