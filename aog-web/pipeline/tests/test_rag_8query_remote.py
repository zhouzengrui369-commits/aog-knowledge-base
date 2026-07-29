"""test_rag_8query_remote.py — 8 RAG 真实远端回归 (Owner 7/29 严令, 4.3)

NJX 严令: "新建 remote RAG regression, 访问真实 staging API"

必须真实远端 staging URL, 不得用 in-process TestClient 替代.

运行:
  export AOG_STAGING_API_BASE=https://aog-api-staging.ap-shanghai.tcloudbase.com/api
  export AOG_STAGING_API_KEY=...   # 可选, 公网 staging 需 token
  aog-web/backend/.venv/bin/python -m pytest tests/test_rag_8query_remote.py -v

如果 AOG_STAGING_API_BASE 未设, 整个文件 skip (CI 不跑本地 staging 不存在时).
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PIPELINE_ROOT.parent / "backend"
for p in (str(BACKEND_ROOT),):
    if p not in sys.path:
        sys.path.insert(0, p)


# 8 RAG 查询 (跟 test_rag_8query_regression.py 同步)
# expected_match_for_remote: 接受 API 返回的 references 列表, 验证是否真实命中
#   - 用 callable 保持硬化版语义 (snippet 真实含件号 + source 限定)
RAG_8_QUERIES_REMOTE = [
    ("赫尔辛基保障", lambda r: "H-赫尔辛基" in r.get("source_id", ""), 1),
    ("北京大兴", lambda r: "B-北京大兴" in r.get("source_id", ""), 1),
    ("西安", lambda r: "X-西安" in r.get("source_id", ""), 1),
    ("三亚", lambda r: "S-三亚" in r.get("source_id", ""), 1),
    ("米兰", lambda r: "M-米兰" in r.get("source_id", ""), 1),
    ("南宁", lambda r: "N-南宁" in r.get("source_id", ""), 1),
    ("雅典", lambda r: "Y-雅典" in r.get("source_id", ""), 1),
    # NJX 4.3 强化: 返回 text/snippet 真实含 3-1531 + source 真实含件号
    ("前轮件号 3-1531", lambda r: (
        r.get("source_id") in {"F-福冈", "H-胡志明（国际）", "H-河内（国际）", "X-新加坡",
                                "core-manual-xlsx", "core-manual-20260205-xlsx", "exp-3a73d6ac"}
        and any(s in (r.get("snippet", "") + r.get("text", "")) for s in ("3-1531", "3-1531-3"))
    ), 3),
]


@pytest.fixture(scope="module")
def staging_base():
    """AOG_STAGING_API_BASE env 必填, 否则 skip 整个 module"""
    base = os.environ.get("AOG_STAGING_API_BASE")
    if not base:
        pytest.skip(
            "AOG_STAGING_API_BASE 未设. 这是真实 staging 远端回归, "
            "需 NJX 提供 staging URL 后才能跑. "
            "Owner 严令: 不得用 in-process TestClient 替代 staging 证据."
        )
    # 去掉尾部 /api 防止拼接重复
    import re as _re
    return _re.sub(r"/api/?$", "", base)


def _post_chat(base: str, q: str, timeout: int = 30) -> dict:
    """POST {base}/api/chat 真实远端, 返 dict {answer, references, model, ...}"""
    url = f"{base}/api/chat"
    body = json.dumps({"q": q}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_http_status": e.code, "_http_error": e.read().decode("utf-8", errors="replace")}
    except urllib.error.URLError as e:
        return {"_url_error": str(e.reason)}


@pytest.mark.parametrize("query,expected_match,top_k", RAG_8_QUERIES_REMOTE)
def test_rag_8_query_remote(staging_base: str, query: str, expected_match, top_k: int):
    """8 RAG 真实远端: POST staging /api/chat, 验 references 命中

    NJX 4.3 严令: 真实远端, 不得 in-process.
    """
    response = _post_chat(staging_base, query)
    # 网络/认证 错
    if "_http_status" in response:
        pytest.fail(
            f"❌ FAIL: query={query!r} HTTP {response['_http_status']}: "
            f"{response.get('_http_error', '')[:200]}"
        )
    if "_url_error" in response:
        pytest.fail(
            f"❌ FAIL: query={query!r} URL error: {response['_url_error']}"
        )
    if "answer" not in response or "references" not in response:
        pytest.fail(
            f"❌ FAIL: query={query!r} response 缺 answer/references: {response}"
        )

    refs = response.get("references", [])
    if not refs:
        pytest.fail(
            f"❌ FAIL: query={query!r} 0 references"
        )

    # 找第一个 matched ref
    matched = next(
        (r for r in refs if expected_match(r)),
        None,
    )
    if not matched:
        actual_top = [(r.get("source_id", "?"), r.get("title", "?")) for r in refs[:3]]
        pytest.fail(
            f"❌ FAIL: query={query!r}\n"
            f"   期望: callable match\n"
            f"   实际 top-3: {actual_top}"
        )

    # 报告
    print(
        f"✅ PASS: query={query!r} "
        f"actual_source_id={matched.get('source_id')!r} "
        f"score={matched.get('score', '?')}"
    )


def test_rag_8_query_remote_summary(staging_base: str):
    """8 RAG 真实远端汇总"""
    results = []
    for query, expected_match, top_k in RAG_8_QUERIES_REMOTE:
        response = _post_chat(staging_base, query)
        refs = response.get("references", []) if "references" in response else []
        matched = next(
            (r for r in refs if expected_match(r)),
            None,
        )
        results.append({
            "query": query,
            "actual_source_id": matched.get("source_id") if matched else f"NOT_FOUND (top: {[r.get('source_id','?') for r in refs[:3]]})",
            "pass": matched is not None,
        })

    print("\n=== 8 RAG 真实远端汇总 (Owner 7/29 严令) ===")
    print("| # | query | actual_source_id | pass |")
    print("|---|-------|-------------------|------|")
    for i, r in enumerate(results, 1):
        mark = "✅" if r["pass"] else "❌"
        print(f"| {i} | {r['query']} | {r['actual_source_id']} | {mark} |")

    pass_count = sum(1 for r in results if r["pass"])
    if pass_count != len(results):
        pytest.fail(
            f"8 RAG 远端回归: {pass_count}/{len(results)} PASS. "
            f"失败:\n" + "\n".join(
                f"  - {r['query']}: {r['actual_source_id']}"
                for r in results if not r["pass"]
            )
        )
