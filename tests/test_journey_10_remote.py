"""10 旅程真实远端验收 (NJX 7/30 严令 PR #3 frontend and remote validation)

跟 test_journey_10_local.py 平行, 区别:
  - 用真实 HTTP (httpx.AsyncClient) 跑远程 staging URL
  - base URL 从 AOG_STAGING_API_BASE env var 读
  - 缺 URL 时 pytest.skip (普通 CI 可 skip)
  - staging-validation workflow 中缺 URL 必须 FAIL (staging-validation.yml 加 step 强制)

NJX 7/30 严令:
  - 新增 deploy-frontend-staging.sh (部署 frontend 到 CloudBase 静态托管)
  - 新增 test_journey_10_remote.py (本文件)
  - 继续使用 test_rag_8query_remote.py (NJX 7/29 23f8604, 已存在)

10 旅程 (跟 local 版平行, 8 项可远程验证, J6/J7 跳过 - mock 行为):
  J1: GET /api/health → 200 + version + llm_mode + rag_backend
  J2: GET /api/city/B-北京大兴 → 200 + trust 10 字段
  J3: GET /api/city/S-上海浦东 → 200 + review_status=MISSING (明确无数据, 不 404)
  J4: GET /api/city/S-上海虹桥 → 200 + review_status=MISSING
  J5: POST /api/chat → references ≥ 1 (RAG 真实回答)
  J8: GET /api/city/H-赫尔辛基 → contacts 2 restricted, phone=["REDACTED"] (PII redaction)
  J9: GET /api/city/B-包头 → review_status=STALE
  J10: GET /files/B-北京大兴.md → 200; GET /files/S-上海浦东.md → 404

运行:
  AOG_STAGING_API_BASE=https://xxx.service.tcloudbase.com python -m pytest tests/test_journey_10_remote.py -v --tb=short
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 缺 staging URL 跳过 (NJX 7/30 严令: 普通 CI 可 skip)
# staging-validation workflow 强制 URL 存在 (在 workflow step 检查, 不在本 test)
AOG_STAGING_API_BASE = os.environ.get("AOG_STAGING_API_BASE", "").rstrip("/")
pytestmark = pytest.mark.skipif(
    not AOG_STAGING_API_BASE,
    reason="AOG_STAGING_API_BASE 未设, 跳过 remote 10 旅程 (NJX 7/30: 普通 CI 可 skip, staging-validation workflow 强制 URL 存在)"
)


@pytest.fixture(scope="module")
def api():
    """真实 staging URL httpx client"""
    import httpx
    return httpx.AsyncClient(
        base_url=AOG_STAGING_API_BASE,
        timeout=30.0,
        headers={"User-Agent": "test_journey_10_remote/1.0"},
    )


# ============== J1: 首页 API 正常 ==============

@pytest.mark.asyncio
async def test_J1_health_endpoint_remote(api):
    """J1 remote: GET /api/health → 200, version + llm_mode + rag_backend"""
    r = await api.get("/api/health")
    assert r.status_code == 200, f"J1 FAIL: status={r.status_code} body={r.text}"
    body = r.json()
    assert body.get("status") == "ok", f"J1 FAIL: status={body.get('status')!r}"
    assert "version" in body and body["version"], f"J1 FAIL: no version"
    assert "llm_mode" in body, f"J1 FAIL: no llm_mode"
    assert "rag_backend" in body, f"J1 FAIL: no rag_backend"
    print(f"\n✅ J1 PASS remote: /api/health → {body}")


# ============== J2: 北京大兴城市详情 ==============

@pytest.mark.asyncio
async def test_J2_beijing_daxing_detail_remote(api):
    """J2 remote: GET /api/city/B-北京大兴 → 200 + trust 10 字段"""
    r = await api.get("/api/city/B-北京大兴")
    assert r.status_code == 200, f"J2 FAIL: status={r.status_code} body={r.text}"
    body = r.json()
    assert "city" in body, f"J2 FAIL: no city field"
    city = body["city"]
    assert "trust" in city, f"J2 FAIL: no trust field"
    trust = city["trust"]
    # trust 必含 10 字段 (NJX 7/29 拍板)
    expected_trust_keys = {
        "verifiability", "transparency", "accuracy", "freshness",
        "completeness", "consistency", "risk", "scope", "source", "stakeholder",
    }
    actual_trust_keys = set(trust.keys()) if isinstance(trust, dict) else set()
    missing = expected_trust_keys - actual_trust_keys
    assert not missing, f"J2 FAIL: trust 缺字段: {missing} (实际 keys: {actual_trust_keys})"
    print(f"\n✅ J2 PASS remote: B-北京大兴 trust 10 字段完整 ({len(actual_trust_keys)} keys)")


# ============== J3: 上海浦东明确 MISSING (NJX 7/29 严令: 200 + MISSING, 不 404) ==============

@pytest.mark.asyncio
async def test_J3_shanghai_pudong_missing_remote(api):
    """J3 remote: GET /api/city/S-上海浦东 → 200 + review_status=MISSING"""
    r = await api.get("/api/city/S-上海浦东")
    assert r.status_code == 200, f"J3 FAIL: status={r.status_code} (NJX 7/29 严令: 必须 200 不 404)"
    body = r.json()
    assert body.get("review_status") == "MISSING", f"J3 FAIL: review_status 应 MISSING, 实际 {body.get('review_status')!r}"
    print(f"\n✅ J3 PASS remote: S-上海浦东 明确 MISSING (200 + review_status=MISSING)")


# ============== J4: 无数据城市明确 MISSING ==============

@pytest.mark.asyncio
async def test_J4_shanghai_hongqiao_missing_remote(api):
    """J4 remote: GET /api/city/S-上海虹桥 → 200 + review_status=MISSING"""
    r = await api.get("/api/city/S-上海虹桥")
    assert r.status_code == 200, f"J4 FAIL: status={r.status_code}"
    body = r.json()
    assert body.get("review_status") == "MISSING", f"J4 FAIL: review_status 应 MISSING, 实际 {body.get('review_status')!r}"
    print(f"\n✅ J4 PASS remote: S-上海虹桥 明确 MISSING")


# ============== J5: Provider 正常时真实回答 ==============

@pytest.mark.asyncio
async def test_J5_chat_real_answer_remote(api):
    """J5 remote: POST /api/chat → 200 + references ≥ 1 (RAG 真实回答)"""
    r = await api.post("/api/chat", json={
        "query": "赫尔辛基机场保障经验",
        "city_code": "H-赫尔辛基",
    })
    assert r.status_code == 200, f"J5 FAIL: status={r.status_code} body={r.text}"
    body = r.json()
    references = body.get("references", [])
    assert len(references) >= 1, f"J5 FAIL: references 应 ≥ 1, 实际 {len(references)}"
    print(f"\n✅ J5 PASS remote: /api/chat references={len(references)} (RAG 真实回答)")


# ============== J8: PII redaction (NJX 7/30 严令: raw phone 不能泄漏) ==============

@pytest.mark.asyncio
async def test_J8_helsinki_phone_redacted_remote(api):
    """J8 remote: H-赫尔辛基 2 restricted contact, phone=["REDACTED"] (PII fail-closed)"""
    r = await api.get("/api/city/H-赫尔辛基")
    assert r.status_code == 200, f"J8 FAIL: status={r.status_code}"
    body = r.json()
    city = body.get("city", body)
    contacts = city.get("contacts", [])
    assert len(contacts) >= 1, f"J8 FAIL: H-赫尔辛基 应有 contact, 实际 {len(contacts)}"

    # 找 restricted contact, phone 必为 ["REDACTED"]
    restricted_phones = []
    for c in contacts:
        if c.get("access_level") == "restricted":
            phones = c.get("phone", [])
            if phones and phones != ["REDACTED"]:
                # raw phone 泄漏, fail
                raise AssertionError(
                    f"J8 FAIL: restricted contact 含 raw phone (NJX 7/30 严令 PII redaction): {phones}"
                )
            restricted_phones.append(phones)
    assert len(restricted_phones) >= 1, f"J8 FAIL: H-赫尔辛基 期望 ≥ 1 restricted contact"
    print(f"\n✅ J8 PASS remote: H-赫尔辛基 {len(restricted_phones)} restricted contact phone 全 REDACTED")


# ============== J9: STALE 数据正确显示 ==============

@pytest.mark.asyncio
async def test_J9_baotou_stale_remote(api):
    """J9 remote: GET /api/city/B-包头 → review_status=STALE"""
    r = await api.get("/api/city/B-包头")
    assert r.status_code == 200, f"J9 FAIL: status={r.status_code}"
    body = r.json()
    assert body.get("review_status") == "STALE", f"J9 FAIL: review_status 应 STALE, 实际 {body.get('review_status')!r}"
    print(f"\n✅ J9 PASS remote: B-包头 review_status=STALE")


# ============== J10: source_document 可打开或明确不可访问 ==============

@pytest.mark.asyncio
async def test_J10_source_documents_remote(api):
    """J10 remote: /files/B-北京大兴.md 200, /files/S-上海浦东.md 404 + reason"""
    r1 = await api.get("/files/B-北京大兴.md")
    assert r1.status_code == 200, f"J10 FAIL: B-北京大兴.md 应 200, 实际 {r1.status_code}"

    r2 = await api.get("/files/S-上海浦东.md")
    assert r2.status_code == 404, f"J10 FAIL: S-上海浦东.md 应 404, 实际 {r2.status_code} body={r2.text}"
    body = r2.json() if r2.headers.get("content-type", "").startswith("application/json") else {}
    assert "reason" in body, f"J10 FAIL: 404 response 应含 reason 字段, body={body}"
    print(f"\n✅ J10 PASS remote: B-北京大兴.md 200 + S-上海浦东.md 404 reason='{body.get('reason')}'")


# 测试 runner 入口
if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
