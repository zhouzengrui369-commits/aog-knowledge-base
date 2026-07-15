"""GET /api/health - CONTRACT §2.1"""
import pytest


@pytest.mark.asyncio
async def test_health_ok(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "uptime_s" in body
    assert isinstance(body["uptime_s"], int)
    # mock mode (因为 conftest 设了空 key)
    assert body["llm_mode"] == "mock"


@pytest.mark.asyncio
async def test_health_uptime_monotonic(client):
    r1 = await client.get("/api/health")
    import asyncio
    await asyncio.sleep(1.2)
    r2 = await client.get("/api/health")
    assert r2.json()["uptime_s"] >= r1.json()["uptime_s"]


@pytest.mark.asyncio
async def test_openapi_docs_available(client):
    """CONTRACT §3.5: /docs → 200"""
    r = await client.get("/docs")
    assert r.status_code == 200
    r2 = await client.get("/openapi.json")
    assert r2.status_code == 200
    spec = r2.json()
    assert spec["info"]["title"] == "AOG AI 知识库 API"
    # 验证所有 10 端点都在
    paths = spec["paths"]
    expected = [
        "/api/health",
        "/api/cities",
        "/api/city/{code}",
        "/api/experiences",
        "/api/experience/{exp_id}",
        "/api/core-plans",
        "/api/core-plan/{plan_id}",
        "/api/chat",
        "/api/sync/status",
    ]
    for p in expected:
        assert p in paths, f"missing path: {p}"
