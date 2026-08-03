"""10 旅程本地验收 (Owner 7/29 严令 Stage 9.3)

不依赖公网 SCF, 用 FastAPI TestClient in-process 跑, 复用 conftest 的 seeded_sqlite fixture.

10 旅程 (NJX 7/29 指令 + Stage 9 需求):
  J1: 首页 API 正常 (GET /api/health → 200 + version)
  J2: 北京大兴城市详情 (GET /api/city/B-北京大兴 → 200 + trust 10 字段)
  J3: 上海浦东明确 MISSING (GET /api/city/S-上海浦东 → 200 + review_status=MISSING, 不 404, 不 mock)
  J4: 无数据城市明确 MISSING (GET /api/city/S-上海虹桥 → 200 + review_status=MISSING)
  J5: Provider 正常时真实回答 (POST /api/chat → references ≥ 1)
  J6: Provider key 缺失 + ALLOW_MOCK=false → fail-closed (startup RuntimeError)
  J7: API 失败时不出现 production mock (ALLOW_MOCK=false → chat() 不返 mock fallback)
  J8: UNVERIFIED 航站所有可执行数据 fail-closed (contacts/fleet/parts/content 全隐藏)
  J9: STALE 数据正确显示 (包头 review_status=STALE)
  J10: source_document 可打开或明确不可访问 (B-北京大兴.md 200 OK, S-上海浦东.md 404 + reason)

运行:
  cd aog-web/backend && .venv/bin/python -m pytest tests/test_journey_10_local.py -v --tb=short
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


# ============== J1: 首页 API 正常 ==============

@pytest.mark.asyncio
async def test_J1_health_endpoint(client):
    """J1: GET /api/health → 200, version 非空, llm_mode/rag_backend 字段存在"""
    r = await client.get("/api/health")
    assert r.status_code == 200, f"J1 FAIL: status={r.status_code} body={r.text}"
    body = r.json()
    assert body["status"] == "ok", f"J1 FAIL: status={body['status']}"
    assert "version" in body and body["version"], f"J1 FAIL: no version"
    assert "llm_mode" in body, f"J1 FAIL: no llm_mode"
    assert "rag_backend" in body, f"J1 FAIL: no rag_backend"
    print(f"\n✅ J1 PASS: /api/health → {body}")


# ============== J2: 北京大兴城市详情 ==============

@pytest.mark.asyncio
async def test_J2_beijing_daxing_detail(client, seeded_sqlite):
    """J2: GET /api/city/B-北京大兴 → 200 + trust 10 字段 + contacts 含 public phone"""
    r = await client.get("/api/city/B-北京大兴")
    assert r.status_code == 200, f"J2 FAIL: status={r.status_code}"
    body = r.json()
    assert body["code"] == "B-北京大兴"
    assert body["name"] == "北京大兴"
    assert body["iata"] == "PKX"
    trust = body.get("trust", {})
    for k in ["source_document", "source_location", "source_version", "updated_at",
              "reviewed_at", "reviewed_by", "review_status", "confidence",
              "environment", "pii_classification"]:
        assert k in trust, f"J2 FAIL: trust.{k} 缺失"
    assert trust["review_status"] == "VERIFIED", f"J2 FAIL: review_status={trust['review_status']}"
    assert trust["confidence"] == 0.95
    contacts = body.get("contacts", [])
    assert len(contacts) >= 1
    public_contact = next((c for c in contacts if c.get("permission") == "public"), None)
    assert public_contact is not None, "J2 FAIL: no public contact"
    assert "021-22379771" in public_contact.get("phone", []), \
        f"J2 FAIL: public phone 应保留, got {public_contact.get('phone')}"
    print(f"\n✅ J2 PASS: B-北京大兴 trust.review_status={trust['review_status']} "
          f"public phone 保留: {public_contact['phone']}")


# ============== J3: 上海浦东明确 MISSING (不 404, 不 mock) ==============

@pytest.mark.asyncio
async def test_J3_shanghai_pudong_missing(client, seeded_sqlite):
    """J3: GET /api/city/S-上海浦东 → 200 + review_status=MISSING (NJX 7/29 严令)"""
    r = await client.get("/api/city/S-上海浦东")
    assert r.status_code == 200, \
        f"J3 FAIL: 必须 200 (明确 MISSING), 不 404, status={r.status_code} body={r.text}"
    body = r.json()
    assert body["code"] == "S-上海浦东"
    trust = body.get("trust", {})
    assert trust.get("review_status") == "MISSING", \
        f"J3 FAIL: review_status 应为 MISSING, got {trust.get('review_status')}"
    assert not body.get("content_md"), \
        f"J3 FAIL: MISSING city content_md 应为空, got {body.get('content_md')[:50]}"
    assert body.get("contacts") == [], \
        f"J3 FAIL: MISSING city contacts 应为 [], got {body.get('contacts')}"
    print("\n✅ J3 PASS: S-上海浦东 status=200 review_status=MISSING (明确 MISSING, 不 404, 不 mock)")


# ============== J4: 无数据城市 (上海虹桥) 明确 MISSING ==============

@pytest.mark.asyncio
async def test_J4_shanghai_hongqiao_missing(client, seeded_sqlite):
    """J4: GET /api/city/S-上海虹桥 → 200 + review_status=MISSING (NJX 7/29 严令)"""
    r = await client.get("/api/city/S-上海虹桥")
    assert r.status_code == 200, \
        f"J4 FAIL: 必须 200 (虹桥不消失, 明确 MISSING), status={r.status_code}"
    body = r.json()
    trust = body.get("trust", {})
    assert trust.get("review_status") == "MISSING", \
        f"J4 FAIL: review_status 应为 MISSING, got {trust.get('review_status')}"
    assert not body.get("content_md"), "J4 FAIL: MISSING city content_md 应为空"
    print("\n✅ J4 PASS: S-上海虹桥 status=200 review_status=MISSING (主基地不消失, 状态明确)")


# ============== J5: Provider 正常时真实回答 ==============

@pytest.mark.asyncio
async def test_J5_chat_real_answer_with_references(client, seeded_sqlite):
    """J5: POST /api/chat → answer 非空 + references ≥ 1 (NSM-2 红线)"""
    r = await client.post("/api/chat", json={"q": "北京大兴有哪些备件?"})
    assert r.status_code == 200, f"J5 FAIL: status={r.status_code} body={r.text}"
    body = r.json()
    refs = body.get("references", [])
    assert len(refs) >= 1, f"J5 FAIL: references 不足 1, got {len(refs)}"
    assert body.get("answer"), "J5 FAIL: answer 为空"
    assert body.get("model"), "J5 FAIL: model 字段缺失"
    assert "latency_ms" in body, "J5 FAIL: latency_ms 字段缺失"
    print(f"\n✅ J5 PASS: chat → answer={len(body['answer'])}字, references={len(refs)}, model={body.get('model')}")


# ============== J6: ALLOW_MOCK=false + 无 KEY → fail-closed ==============

@pytest.mark.asyncio
async def test_J6_production_fail_closed_on_startup(monkeypatch):
    """J6: ALLOW_MOCK=false + MINIMAX_API_KEY 空 → startup RuntimeError (P0-4 fail-closed)"""
    from aog_web.config import reset_settings_cache
    reset_settings_cache()
    monkeypatch.setenv("ALLOW_MOCK", "false")
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.setenv("STRICT_LLM", "true")
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", os.environ.get("KNOWLEDGE_BASE_PATH", "/tmp"))
    monkeypatch.setenv("RAW_PATH", os.environ.get("RAW_PATH", "/tmp"))
    monkeypatch.setenv("RAG_BACKEND", "chroma")
    from aog_web.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test"):
        try:
            async with app.router.lifespan_context(app):
                pytest.fail("J6 FAIL: ALLOW_MOCK=false + 无 KEY 应该 fail-closed")
        except RuntimeError as exc:
            assert "fail-closed" in str(exc) or "ALLOW_MOCK" in str(exc)
    reset_settings_cache()


# ============== J7: ALLOW_MOCK=false 时 chat 不返 mock fallback ==============

@pytest.mark.asyncio
async def test_J7_production_no_mock_fallback():
    """J7: get_llm() 在 ALLOW_MOCK=false + 无 KEY 时不允许返 MockLLM"""
    from aog_web.config import Settings, reset_settings_cache
    from aog_web.services.llm import get_llm, MockLLM
    prod_settings = Settings(MINIMAX_API_KEY="", ALLOW_MOCK=False, STRICT_LLM=True)
    assert prod_settings.is_mock_llm is True
    with pytest.raises(RuntimeError):
        get_llm(settings=prod_settings)
    dev_settings = Settings(MINIMAX_API_KEY="", ALLOW_MOCK=True, STRICT_LLM=False)
    assert isinstance(get_llm(settings=dev_settings), MockLLM)
    reset_settings_cache()


# ============== J8: UNVERIFIED 航站可执行数据 fail-closed ==============

@pytest.mark.asyncio
async def test_J8_unverified_city_fail_closed(client, seeded_sqlite):
    """J8: UNVERIFIED city 保留身份/来源，但不返回任何可执行保障数据。"""
    r = await client.get("/api/city/H-赫尔辛基")
    assert r.status_code == 200, f"J8 FAIL: status={r.status_code}"
    body = r.json()
    assert body.get("trust", {}).get("review_status") == "UNVERIFIED"
    assert body.get("data_available") is False
    assert body.get("contacts") == []
    assert body.get("fleet") == []
    assert body.get("parts") == []
    assert not body.get("content_md")
    assert "禁止用于实际" in (body.get("operational_notice") or "")
    print("\n✅ J8 PASS: UNVERIFIED 航站 contacts/fleet/parts/content 全部 fail-closed")


# ============== J9: STALE 数据正确显示 ==============

@pytest.mark.asyncio
async def test_J9_stale_data_displays_status(client, seeded_sqlite):
    """J9: GET /api/city/B-包头 → trust.review_status=STALE + confidence=0.3"""
    r = await client.get("/api/city/B-包头")
    assert r.status_code == 200, f"J9 FAIL: status={r.status_code}"
    body = r.json()
    trust = body.get("trust", {})
    assert trust.get("review_status") == "STALE", \
        f"J9 FAIL: review_status 应为 STALE, got {trust.get('review_status')}"
    assert trust.get("confidence") == 0.3, \
        f"J9 FAIL: confidence 应为 0.3, got {trust.get('confidence')}"
    assert trust.get("source_version") == "2019-Q3", \
        f"J9 FAIL: source_version 应为 2019-Q3, got {trust.get('source_version')}"
    print("\n✅ J9 PASS: B-包头 review_status=STALE confidence=0.3 source_version=2019-Q3")


# ============== J10: source_document 可打开或明确不可访问 ==============

@pytest.mark.asyncio
async def test_J10_source_document_accessible(client, seeded_sqlite):
    """J10: source document exists or returns an explicit 404 reason."""
    r = await client.get("/files/02_外战预案/B-北京大兴.md")
    assert r.status_code == 200
    assert "北京大兴" in r.content.decode("utf-8")

    r = await client.get("/files/02_外战预案/H-赫尔辛基.md")
    assert r.status_code == 200

    r = await client.get("/files/02_外战预案/S-上海浦东.md")
    assert r.status_code == 404
    detail = r.json().get("detail", {})
    assert detail.get("error") == "file not found"
    assert detail.get("path")
