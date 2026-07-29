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
  J8: restricted contact 未授权时原始联系方式不可见 (赫尔辛基 contact 验证 phone=["REDACTED"])
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
    # 基础字段
    assert body["code"] == "B-北京大兴"
    assert body["name"] == "北京大兴"
    assert body["iata"] == "PKX"
    # P0-5 trust 10 字段
    trust = body.get("trust", {})
    for k in ["source_document", "source_location", "source_version", "updated_at",
              "reviewed_at", "reviewed_by", "review_status", "confidence",
              "environment", "pii_classification"]:
        assert k in trust, f"J2 FAIL: trust.{k} 缺失"
    assert trust["review_status"] == "VERIFIED", f"J2 FAIL: review_status={trust['review_status']}"
    assert trust["confidence"] == 0.95
    # P0-6: public contact 保留 phone
    contacts = body.get("contacts", [])
    assert len(contacts) >= 1
    public_contact = next((c for c in contacts if c.get("permission") == "public"), None)
    assert public_contact is not None, f"J2 FAIL: no public contact"
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
    # P0-5: review_status=MISSING 显式标记
    trust = body.get("trust", {})
    assert trust.get("review_status") == "MISSING", \
        f"J3 FAIL: review_status 应为 MISSING, got {trust.get('review_status')}"
    # content_md 为空 (无真实数据)
    assert not body.get("content_md"), \
        f"J3 FAIL: MISSING city content_md 应为空, got {body.get('content_md')[:50]}"
    # contacts 为空 (没 mock 假联系人)
    assert body.get("contacts") == [], \
        f"J3 FAIL: MISSING city contacts 应为 [], got {body.get('contacts')}"
    print(f"\n✅ J3 PASS: S-上海浦东 status=200 review_status=MISSING (明确 MISSING, 不 404, 不 mock)")


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
    print(f"\n✅ J4 PASS: S-上海虹桥 status=200 review_status=MISSING (主基地不消失, 状态明确)")


# ============== J5: Provider 正常时真实回答 ==============

@pytest.mark.asyncio
async def test_J5_chat_real_answer_with_references(client, seeded_sqlite):
    """J5: POST /api/chat → answer 非空 + references ≥ 1 (NSM-2 红线)"""
    r = await client.post("/api/chat", json={"q": "北京大兴有哪些备件?"})
    assert r.status_code == 200, f"J5 FAIL: status={r.status_code} body={r.text}"
    body = r.json()
    # NSM-2: references 强制 ≥ 1
    refs = body.get("references", [])
    assert len(refs) >= 1, f"J5 FAIL: references 不足 1, got {len(refs)}"
    # answer 非空
    assert body.get("answer"), f"J5 FAIL: answer 为空"
    # model 字段存在 (mock-llm or minimax-m3)
    assert body.get("model"), f"J5 FAIL: model 字段缺失"
    # latency_ms 字段存在
    assert "latency_ms" in body, f"J5 FAIL: latency_ms 字段缺失"
    print(f"\n✅ J5 PASS: chat → answer={len(body['answer'])}字, "
          f"references={len(refs)} ({[r['id'] for r in refs[:3]]}), "
          f"model={body.get('model')}")


# ============== J6: ALLOW_MOCK=false + 无 KEY → fail-closed ==============

@pytest.mark.asyncio
async def test_J6_production_fail_closed_on_startup(monkeypatch):
    """J6: ALLOW_MOCK=false + MINIMAX_API_KEY 空 → startup RuntimeError (P0-4 fail-closed)"""
    # 重置 settings 缓存, 改 env 后重启
    from aog_web.config import reset_settings_cache, get_settings
    reset_settings_cache()

    monkeypatch.setenv("ALLOW_MOCK", "false")
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.setenv("STRICT_LLM", "true")

    # 设置其他必要 env (避免其它校验失败)
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", os.environ.get("KNOWLEDGE_BASE_PATH", "/tmp"))
    monkeypatch.setenv("RAW_PATH", os.environ.get("RAW_PATH", "/tmp"))
    monkeypatch.setenv("RAG_BACKEND", "chroma")  # 避免 fts5 校验

    # ★ P0-4: 验证 lifespan startup 抛 RuntimeError
    from aog_web.main import app
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            async with app.router.lifespan_context(app):
                # 不应该进入 yield
                pytest.fail("J6 FAIL: ALLOW_MOCK=false + 无 KEY 应该 fail-closed, 但 lifespan 进入了 yield")
        except RuntimeError as e:
            # ★ 期望: RuntimeError 含 "fail-closed" 或 "ALLOW_MOCK"
            msg = str(e)
            assert "fail-closed" in msg or "ALLOW_MOCK" in msg, \
                f"J6 FAIL: RuntimeError message 异常: {msg}"
            print(f"\n✅ J6 PASS: P0-4 fail-closed 触发, RuntimeError = {msg[:80]}")
        except Exception as e:
            pytest.fail(f"J6 FAIL: 期望 RuntimeError, 实际 {type(e).__name__}: {e}")

    # 清理
    reset_settings_cache()


# ============== J7: ALLOW_MOCK=false 时 chat 不返 mock fallback ==============

@pytest.mark.asyncio
async def test_J7_production_no_mock_fallback():
    """J7: get_llm() 在 ALLOW_MOCK=false + 无 KEY 时不允许返 MockLLM

    NJX 7/29 严令: production (ALLOW_MOCK=false) 无 KEY 必须 fail-closed, 不可用 MockLLM
    验证 services/llm.get_llm 工厂函数在生产配置下不返 MockLLM 实例
    """
    from aog_web.config import Settings, reset_settings_cache
    from aog_web.services.llm import get_llm, MockLLM

    # 模拟 production 配置
    prod_settings = Settings(
        MINIMAX_API_KEY="",
        ALLOW_MOCK=False,
        STRICT_LLM=True,
    )
    # is_mock_llm 应该是 True (无 KEY)
    assert prod_settings.is_mock_llm is True, \
        f"J7 FAIL: production 模拟配置 is_mock_llm 应为 True, got {prod_settings.is_mock_llm}"

    # P0-4 核心断言: production 配置调用 get_llm 必须抛错, 不返 MockLLM
    try:
        llm = get_llm(settings=prod_settings)
        pytest.fail(
            f"J7 FAIL: production (ALLOW_MOCK=false + 无 KEY) get_llm 应抛 RuntimeError, "
            f"但返回了 {type(llm).__name__}"
        )
    except RuntimeError as e:
        msg = str(e)
        assert "ALLOW_MOCK" in msg or "mock" in msg.lower(), \
            f"J7 FAIL: RuntimeError message 异常: {msg}"
        print(f"\n✅ J7 PASS: production get_llm fail-closed, RuntimeError = {msg[:80]}")

    # 对照: dev 配置 (ALLOW_MOCK=true) 允许 MockLLM
    dev_settings = Settings(MINIMAX_API_KEY="", ALLOW_MOCK=True, STRICT_LLM=False)
    llm_dev = get_llm(settings=dev_settings)
    assert isinstance(llm_dev, MockLLM), \
        f"J7 FAIL: dev 配置应返 MockLLM, got {type(llm_dev).__name__}"
    print(f"✅ J7 对照: dev (ALLOW_MOCK=true + 无 KEY) → {type(llm_dev).__name__} (允许 mock)")

    reset_settings_cache()


# ============== J8: restricted contact 未授权时不可见 ==============

@pytest.mark.asyncio
async def test_J8_restricted_contact_redacted(client, seeded_sqlite):
    """J8: GET /api/city/H-赫尔辛基 → restricted contact phone 必须为 ["REDACTED"]"""
    r = await client.get("/api/city/H-赫尔辛基")
    assert r.status_code == 200, f"J8 FAIL: status={r.status_code}"
    body = r.json()
    contacts = body.get("contacts", [])
    assert len(contacts) == 3, f"J8 FAIL: 期望 3 contacts, got {len(contacts)}"
    # 找 restricted contact
    restricted = [c for c in contacts if c.get("permission") == "restricted"]
    assert len(restricted) == 2, f"J8 FAIL: 期望 2 restricted contact, got {len(restricted)}"
    for c in restricted:
        # P0-6: 原始 phone 不可见, 必须为 ["REDACTED"]
        assert c.get("phone") == ["REDACTED"], \
            f"J8 FAIL: restricted contact phone 应为 ['REDACTED'], got {c.get('phone')}"
        # org/role 仍可见 (信息)
        assert c.get("org"), f"J8 FAIL: restricted contact org 缺失"
        assert c.get("role"), f"J8 FAIL: restricted contact role 缺失"
    # public contact 保留原 phone
    public = [c for c in contacts if c.get("permission") == "public"]
    assert len(public) == 1, f"J8 FAIL: 期望 1 public contact, got {len(public)}"
    assert "+358-9-1234567" in public[0].get("phone", []), \
        f"J8 FAIL: public contact phone 应保留, got {public[0].get('phone')}"
    print(f"\n✅ J8 PASS: 赫尔辛基 2 restricted contact phone=REDACTED, 1 public phone 保留")


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
    # source_version 显示旧版
    assert trust.get("source_version") == "2019-Q3", \
        f"J9 FAIL: source_version 应为 2019-Q3, got {trust.get('source_version')}"
    print(f"\n✅ J9 PASS: B-包头 review_status=STALE confidence=0.3 source_version=2019-Q3")


# ============== J10: source_document 可打开或明确不可访问 ==============

@pytest.mark.asyncio
async def test_J10_source_document_accessible(client, seeded_sqlite):
    """J10: GET /files/02_外战预案/B-北京大兴.md → 200 OK (source_document 存在)

    S-上海浦东 没有 source 文档, 验证后端正确处理 (虽 frontend 不调 /files/
    for MISSING city, 但 API 应能区分 200 vs 404)
    """
    # J10a: B-北京大兴 source 存在 → 200
    r = await client.get("/files/02_外战预案/B-北京大兴.md")
    assert r.status_code == 200, \
        f"J10a FAIL: 已有 source 文档应可访问, status={r.status_code} body={r.text}"
    body = r.content
    assert "北京大兴" in body.decode("utf-8"), f"J10a FAIL: 文件内容异常"
    print(f"\n✅ J10a PASS: GET /files/02_外战预案/B-北京大兴.md → 200, "
          f"{len(body)} bytes")

    # J10b: H-赫尔辛基 source 存在 → 200
    r = await client.get("/files/02_外战预案/H-赫尔辛基.md")
    assert r.status_code == 200, f"J10b FAIL: status={r.status_code}"
    print(f"✅ J10b PASS: GET /files/02_外战预案/H-赫尔辛基.md → 200")

    # J10c: S-上海浦东 source 不存在 → 404 + 明确 error (reason)
    r = await client.get("/files/02_外战预案/S-上海浦东.md")
    assert r.status_code == 404, \
        f"J10c FAIL: MISSING source 应返 404, got {r.status_code}"
    detail = r.json().get("detail", {})
    assert detail.get("error") == "file not found", \
        f"J10c FAIL: error 应为 'file not found', got {detail}"
    assert detail.get("path"), f"J10c FAIL: path 应在 detail 中, got {detail}"
    print(f"✅ J10c PASS: GET /files/02_外战预案/S-上海浦东.md → 404 "
          f"detail={detail} (MISSING source 明确不可访问原因)")
