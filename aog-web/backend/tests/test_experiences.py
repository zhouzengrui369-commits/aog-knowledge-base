"""GET /api/experiences + /api/experience/{id}"""
import pytest


@pytest.mark.asyncio
async def test_list_experiences_empty(client):
    r = await client.get("/api/experiences")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_experiences_seeded(client, seeded_sqlite):
    r = await client.get("/api/experiences")
    exps = r.json()
    assert len(exps) == 2
    # 字段 1:1
    e = exps[0]
    for key in ["id", "title", "category", "status", "tags", "summary",
                "content_md", "related_pn", "source_path", "updated_at"]:
        assert key in e, f"missing field: {key}"


@pytest.mark.asyncio
async def test_list_experiences_filter_category(client, seeded_sqlite):
    r = await client.get("/api/experiences?category=案例")
    exps = r.json()
    assert all(e["category"] == "案例" for e in exps)
    assert len(exps) == 2


@pytest.mark.asyncio
async def test_list_experiences_fulltext(client, seeded_sqlite):
    r = await client.get("/api/experiences?q=B787")
    exps = r.json()
    assert any("B787" in e["title"] for e in exps)
    assert len(exps) >= 1


@pytest.mark.asyncio
async def test_list_experiences_no_match(client, seeded_sqlite):
    r = await client.get("/api/experiences?q=zzz_no_match_xyz")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_experience_ok(client, seeded_sqlite):
    r = await client.get("/api/experience/exp-001")
    assert r.status_code == 200
    e = r.json()
    assert e["id"] == "exp-001"
    assert e["title"] == "B787 风挡 AOG 处理流程"
    assert e["category"] == "案例"


@pytest.mark.asyncio
async def test_get_experience_404(client, seeded_sqlite):
    r = await client.get("/api/experience/exp-NOT-EXIST")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_core_plans(client, seeded_sqlite):
    r = await client.get("/api/core-plans")
    plans = r.json()
    assert len(plans) == 1
    p = plans[0]
    for key in ["id", "title", "type", "content_md", "source_path", "updated_at"]:
        assert key in p


@pytest.mark.asyncio
async def test_get_core_plan_ok(client, seeded_sqlite):
    r = await client.get("/api/core-plan/core-20260204")
    assert r.status_code == 200
    p = r.json()
    assert p["id"] == "core-20260204"
    assert p["type"] == "master"


@pytest.mark.asyncio
async def test_get_core_plan_404(client, seeded_sqlite):
    r = await client.get("/api/core-plan/core-NOT-EXIST")
    assert r.status_code == 404
