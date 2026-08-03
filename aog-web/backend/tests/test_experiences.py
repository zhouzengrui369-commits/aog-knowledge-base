"""GET /api/experiences + /api/experience/{id}."""
from __future__ import annotations

import sqlite3
from datetime import datetime

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
    e = exps[0]
    for key in [
        "id",
        "title",
        "category",
        "status",
        "tags",
        "summary",
        "related_pn",
        "source_path",
        "updated_at",
    ]:
        assert key in e, f"missing field: {key}"
    assert "content_md" not in e, "list endpoint 应排除 content_md (避 SCF 6MB)"


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
    assert "流程内容" in e["content_md"]


@pytest.mark.asyncio
async def test_empty_experience_is_flagged_and_hidden(client, seeded_sqlite):
    """P0-1: an empty worksheet record is neither listed nor directly readable."""
    from aog_web.services.sqlite_client import ExperienceRow

    async with seeded_sqlite.session_factory() as session:
        session.add(
            ExperienceRow(
                id="exp-empty-shell",
                title="知识库导出记录",
                category="案例",
                status="现行",
                tags='["导出"]',
                summary="Sheet1",
                content_md="Sheet1",
                related_pn="[]",
                source_path="03_保障经验/export.xlsx",
                updated_at=datetime.utcnow().isoformat(),
            )
        )
        await session.commit()

    listed = await client.get("/api/experiences?limit=15")
    assert listed.status_code == 200
    assert "exp-empty-shell" not in {item["id"] for item in listed.json()}

    direct = await client.get("/api/experience/exp-empty-shell")
    assert direct.status_code == 404
    assert direct.json()["detail"]["error"] == "experience not published"

    with sqlite3.connect(seeded_sqlite.db_path) as con:
        row = con.execute(
            "SELECT has_content FROM experiences WHERE id = ?",
            ("exp-empty-shell",),
        ).fetchone()
    assert row == (0,)


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
