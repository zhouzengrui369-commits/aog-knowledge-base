"""Cross-cutting production readiness regressions."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest

from aog_web.services.airlines_client import AirlinesClient
from aog_web.services.production_policy import production_stats


@pytest.mark.asyncio
async def test_stats_endpoint_matches_seeded_database(client, seeded_sqlite):
    response = await client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["cities"] == 5
    assert body["experiences"] == 2
    assert body["core_plans"] == 1
    assert body["verified_cities"] == 1
    assert body["source"] == "sqlite"


@pytest.mark.asyncio
async def test_unverified_city_is_fail_closed(client, seeded_sqlite):
    response = await client.get(f"/api/city/{quote('H-赫尔辛基')}")
    assert response.status_code == 200
    city = response.json()
    assert city["trust"]["review_status"] == "UNVERIFIED"
    assert city["data_available"] is False
    assert city["contacts"] == []
    assert city["parts"] == []
    assert city["fleet"] == []
    assert "禁止用于实际" in city["operational_notice"]


@pytest.mark.asyncio
async def test_verified_city_visit_count_is_durable(client, seeded_sqlite):
    path = f"/api/city/{quote('B-北京大兴')}"
    first = (await client.get(path)).json()["view_count"]
    second = (await client.get(path)).json()["view_count"]
    assert first >= 1
    assert second == first + 1
    listed = (await client.get("/api/cities")).json()
    beijing = next(item for item in listed if item["code"] == "B-北京大兴")
    assert beijing["view_count"] == second


def test_production_stats_counts_only_publishable_experiences(seeded_sqlite):
    stats = production_stats(seeded_sqlite.db_path, airline_count=25)
    assert stats["experiences"] == 2
    assert stats["airlines"] == 25


def test_airline_contact_conflict_is_fail_closed(tmp_path: Path):
    rows = [
        {
            "iata": "HU", "icao": "CHH", "name_cn": "错误别名", "name_en": "Hainan Airlines",
            "hubs": [], "fleet_size": 1, "alliance": "无", "verified": True,
            "verified_at": "2026-08-03", "aog_contact": {"phone": "010-11112222", "email": "hu@example.test"},
        },
        {
            "iata": "JD", "icao": "CBJ", "name_cn": "错误别名", "name_en": "Capital Airlines",
            "hubs": [], "fleet_size": 1, "alliance": "无", "verified": True,
            "verified_at": "2026-08-03", "aog_contact": {"phone": "010-11112222", "email": "jd@example.test"},
        },
    ]
    path = tmp_path / "airlines.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    client = AirlinesClient(path)
    hu = client.get("HU")
    jd = client.get("JD")
    assert hu and jd
    assert hu["name_cn"] == "海南航空"
    assert jd["name_cn"] == "首都航空"
    assert hu["verification_status"] == "CONFLICT"
    assert jd["verification_status"] == "CONFLICT"
    assert "phone" not in hu["aog_contact"]
    assert "phone" not in jd["aog_contact"]


def test_juneyao_connecting_partner_label(tmp_path: Path):
    path = tmp_path / "airlines.json"
    path.write_text(json.dumps([{
        "iata": "HO", "icao": "DKH", "name_cn": "吉祥航空", "name_en": "Juneyao Airlines",
        "hubs": [], "fleet_size": 1, "alliance": "过期值", "verified": True,
        "verified_at": "2026-08-03", "aog_contact": {},
    }], ensure_ascii=False), encoding="utf-8")
    row = AirlinesClient(path).get("HO")
    assert row and row["alliance"] == "星空联盟优连伙伴"
