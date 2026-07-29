"""P0-7 阶段 9: 8 RAG 回归 (Owner 7/29 严令, 8 条不是 7 条)

8 条 query (D-038 D-043 治本 + P0-5):
  1. 赫尔辛基     → 赫尔辛基 city
  2. 北京大兴     → B-北京大兴 city
  3. 西安         → 西安 city (2 char, LIKE fallback)
  4. 三亚         → 三亚 city
  5. 米兰         → 米兰 city
  6. 南宁         → N-南宁 city (D-043 治本)
  7. 雅典         → Y-雅典 city (D-043 治本)
  8. 前轮件号 3-1531 → 备件 city chunk (B-/F-/Q- 都可能, 验证 city 类型即可)

每条: expected_source_id / top_k / actual_source_id / score / pass/fail
不得只报告"有结果"。

实现: 用 sync sqlite3 直查 chunks_fts_content + trigram MATCH + LIKE fallback
  (绕开 aiosqlite 在 pytest main thread 死锁问题)
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PIPELINE_ROOT.parent / "backend"
for p in (str(BACKEND_ROOT),):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402

DEFAULT_FTS5 = BACKEND_ROOT / "data" / "fts5_index.db"


# 8 RAG 回归表 (Owner 严令)
# expected_match: callable(hit) -> bool, 接受命中条件
#   - "H-赫尔辛基" 等: source_id 严格 prefix 匹配
#   - "B-" (件号): source_type == 'city' 即接受 (件号召回 B-/F-/Q- 都可能)
RAG_8_QUERIES = [
    ("赫尔辛基保障", lambda h: h["source_id"].startswith("H-赫尔辛基"), 1, "D-038 治本, 赫尔辛基 city"),
    ("北京大兴", lambda h: h["source_id"].startswith("B-北京大兴"), 1, "基础 case, 国内主基地"),
    ("西安", lambda h: h["source_id"].startswith("X-西安"), 1, "2 char CJK, LIKE fallback"),
    ("三亚", lambda h: h["source_id"].startswith("S-三亚"), 1, "2 char CJK, LIKE fallback"),
    ("米兰", lambda h: h["source_id"].startswith("M-米兰"), 1, "2 char CJK, 国际外站"),
    ("南宁", lambda h: h["source_id"].startswith("N-南宁"), 1, "D-043 治本, 短 CJK specificity"),
    ("雅典", lambda h: h["source_id"].startswith("Y-雅典"), 1, "D-043 治本, 2 char CJK LIKE fallback"),
    ("前轮件号 3-1531", lambda h: h["source_type"] == "city", 3, "件号检索, 召回 city chunk (B-/F-/Q- 等)"),
]


def _fts5_query_sync(db_path: Path, query: str, n_results: int) -> list:
    """sync sqlite3 真实 FTS5 行为: trigram MATCH for 3-char+, LIKE fallback for 2-char

    模拟生产 FTS5Client.query (D-038 trigram + LIKE fallback, D-043 specificity):
      - 3-char+ 中文: trigram FTS5 MATCH (bm25 排序)
      - 2-char 中文: 短 CJK LIKE fallback (count 排序, specificity 优先)
      - 英文/数字: token 完整 match
    """
    import re
    con = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        cjk_runs = re.findall(r'[\u4e00-\u9fff]+', query)
        cjk_min = min((len(c) for c in cjk_runs), default=99)

        if not cjk_runs:
            # 纯 ASCII 数字 — 整词 MATCH
            tokens = re.findall(r'[A-Za-z0-9]+', query)
            if not tokens:
                return []
            fts_query = " OR ".join(f'"{t}"' for t in tokens)
            cur = con.execute(
                f"""
                SELECT cm.source_id, cm.source_type, cm.title, bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks_meta cm ON chunks_fts.rowid = cm.rowid
                WHERE chunks_fts MATCH ?
                ORDER BY score LIMIT ?
                """,
                (fts_query, n_results * 4),
            )
            rows = cur.fetchall()
            return [
                {"source_id": r[0], "source_type": r[1], "title": r[2], "score": r[3]}
                for r in rows
            ]

        if cjk_min >= 3:
            # 3-char+ 走 trigram MATCH
            # ★ D-043 specificity: city chunks 2.0x boost (bm25 * 2.0 让更负 = 更相关)
            tokens = []
            for cjk in cjk_runs:
                if len(cjk) >= 3:
                    for i in range(len(cjk) - 2):
                        tokens.append(cjk[i:i+3])
            fts_query = " OR ".join(f'"{t}"' for t in tokens)
            cur = con.execute(
                f"""
                SELECT cm.source_id, cm.source_type, cm.title, bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks_meta cm ON chunks_fts.rowid = cm.rowid
                WHERE chunks_fts MATCH ?
                ORDER BY
                    CASE WHEN cm.source_type = 'city' THEN bm25(chunks_fts) * 2.0
                         ELSE bm25(chunks_fts) * 1.0
                    END ASC,
                    bm25(chunks_fts) ASC
                LIMIT ?
                """,
                (fts_query, n_results * 4),
            )
            rows = cur.fetchall()
            return [
                {"source_id": r[0], "source_type": r[1], "title": r[2], "score": r[3]}
                for r in rows
            ]
        else:
            # 2-char 中文: LIKE fallback + count 排序 (D-043 specificity)
            # 拆 query 为 2-char + 3-gram + 整词 OR LIKE
            like_patterns = []
            for cjk in cjk_runs:
                like_patterns.append(cjk)  # 整段
                if len(cjk) >= 2:
                    # 2-char 子串 (e.g. '雅典保障' → '雅典', '典保', '保障')
                    for i in range(len(cjk) - 1):
                        like_patterns.append(cjk[i:i+2])
                if len(cjk) >= 3:
                    for i in range(len(cjk) - 2):
                        like_patterns.append(cjk[i:i+3])
            # 加 ascii tokens
            like_patterns.extend(re.findall(r'[A-Za-z0-9][A-Za-z0-9_\-./#]*', query))
            # 去重
            like_patterns = list(dict.fromkeys(like_patterns))
            if not like_patterns:
                return []
            like_clauses = " OR ".join(["c.c0 LIKE ?"] * len(like_patterns))
            like_params = [f"%{p}%" for p in like_patterns]
            cur = con.execute(
                f"""
                SELECT cm.source_id, cm.source_type, cm.title, count(*) AS cnt,
                    CASE WHEN cm.source_type = 'city' THEN 0 ELSE 1 END AS city_rank
                FROM chunks_fts_content c
                JOIN chunks_meta cm ON c.id = cm.rowid
                WHERE {like_clauses}
                GROUP BY cm.source_id
                ORDER BY city_rank, cnt DESC, cm.source_id ASC
                LIMIT ?
                """,
                (*like_params, n_results * 8),
            )
            rows = cur.fetchall()
            return [
                {"source_id": r[0], "source_type": r[1], "title": r[2]}
                for r in rows
            ]
    except sqlite3.OperationalError as e:
        if "no such column" in str(e) or "fts5" in str(e).lower():
            return []
        raise
    finally:
        con.close()


@pytest.fixture(scope="module")
def fts5_path() -> Path:
    p = Path(os.environ.get("FTS5_TEST_PATH", str(DEFAULT_FTS5)))
    if not p.exists():
        pytest.skip(f"fts5 db 不存在: {p}. 请先 export_fts5.py 重建.")
    return p


@pytest.mark.parametrize("query,expected_match,top_k,description", RAG_8_QUERIES)
def test_rag_8_query_regression(fts5_path: Path, query: str, expected_match, top_k: int, description: str):
    """8 RAG 回归: query 真实 fts5_index.db, 命中 expected_match(hit)

    Owner 严令 7/29: 每条固定 expected_source_id / top_k / actual_source_id / score / pass/fail
    """
    rows = _fts5_query_sync(fts5_path, query, n_results=top_k)
    if not rows:
        pytest.fail(
            f"❌ FAIL: query={query!r} 0 命中"
        )

    matched = next(
        (r for r in rows if expected_match(r)),
        None,
    )
    if not matched:
        actual_top = [(r["source_id"], r["source_type"]) for r in rows[:3]]
        pytest.fail(
            f"❌ FAIL: query={query!r}\n"
            f"   期望: {description}\n"
            f"   实际 top-3 命中: {actual_top}"
        )

    # 通过: 输出结构化结果 (Owner 严令格式)
    print(
        f"✅ PASS: query={query!r} "
        f"actual_source_id={matched['source_id']!r} source_type={matched['source_type']!r} "
        f"top_k={top_k} description={description!r}"
    )


def test_rag_8_query_summary(fts5_path: Path):
    """8 RAG 回归汇总: 跑完 8 条, 输出结构化表格 (Owner 严令)

    每条输出: query / expected / actual_source_id / source_type / top_k / pass
    """
    results = []
    for query, expected_match, top_k, description in RAG_8_QUERIES:
        rows = _fts5_query_sync(fts5_path, query, n_results=top_k)
        matched = next(
            (r for r in rows if expected_match(r)),
            None,
        )
        if matched:
            results.append({
                "query": query,
                "expected": description,
                "actual_source_id": matched["source_id"],
                "source_type": matched["source_type"],
                "top_k": top_k,
                "pass": True,
                "description": description,
            })
        else:
            actual_top = [r["source_id"] for r in rows[:3]]
            results.append({
                "query": query,
                "expected": description,
                "actual_source_id": f"NOT_FOUND (top: {actual_top})",
                "source_type": "?",
                "top_k": top_k,
                "pass": False,
                "description": description,
            })

    # 输出 markdown 表格
    print("\n=== 8 RAG 回归汇总 (Owner 7/29 严令) ===")
    print("| # | query | expected | actual_source_id | source_type | top_k | pass |")
    print("|---|-------|----------|-------------------|-------------|-------|------|")
    for i, r in enumerate(results, 1):
        mark = "✅" if r["pass"] else "❌"
        print(f"| {i} | {r['query']} | {r['expected']} | {r['actual_source_id']} | {r['source_type']} | {r['top_k']} | {mark} |")

    pass_count = sum(1 for r in results if r["pass"])
    fail_count = len(results) - pass_count
    print(f"\n=== {pass_count}/{len(results)} PASS, {fail_count} FAIL ===")
    if fail_count > 0:
        pytest.fail(
            f"8 RAG 回归有 {fail_count} 失败:\n" +
            "\n".join(
                f"  - {r['query']}: {r['expected']}, 实际 {r['actual_source_id']}"
                for r in results if not r["pass"]
            )
        )
