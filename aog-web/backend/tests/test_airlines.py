"""GET /api/airlines + /api/airlines/{iata} + /api/airlines/search - Sprint C

3 个核心场景:
1. /api/airlines 返 list (>= 20 航司, 字段完整)
2. /api/airlines/{iata} 返单航司详情
3. /api/airlines/search?q=... 模糊搜索

数据源: tests 使用 tmp_path 写入一份精简 airlines.json (3 航司),
保证测试独立 / 可重复 / 不依赖真实文件
"""
import json
from pathlib import Path

import pytest


# ===== Test fixtures =====

@pytest.fixture
def airlines_test_data(tmp_path: Path) -> Path:
    """写一份 3 航司的测试数据, 返回路径"""
    data = [
        {
            "iata": "CA",
            "icao": "CCA",
            "name_cn": "中国国际航空",
            "name_short": "国航",
            "name_en": "Air China",
            "hubs": [
                {"city_code": "B-北京大兴", "iata": "PKX", "type": "hub", "note": "主基地"},
                {"city_code": "B-北京首都（暂停）", "iata": "PEK", "type": "hub", "note": "原基地"},
            ],
            "fleet_size": 491,
            "alliance": "星空联盟",
            "headquarters": "北京",
            "website": "www.airchina.com.cn",
            "aog_contact": {"phone": "010-64537139", "email": "aogoffice@airchina.com"},
            "data_source": "test",
            "verified": True,
            "verified_at": "2026-07-22",
        },
        {
            "iata": "MU",
            "icao": "CES",
            "name_cn": "中国东方航空",
            "name_short": "东航",
            "name_en": "China Eastern Airlines",
            "hubs": [
                {"city_code": "S-上海浦东", "iata": "PVG", "type": "hub", "note": "主基地"},
                {"city_code": "B-北京大兴", "iata": "PKX", "type": "focus", "note": "东航北京基地"},
            ],
            "fleet_size": 595,
            "alliance": "天合联盟",
            "headquarters": "上海",
            "website": "www.ceair.com",
            "aog_contact": {"phone": "021-22379771", "email": "aog-desk@ceair.com"},
            "data_source": "test",
            "verified": True,
            "verified_at": "2026-07-22",
        },
        {
            "iata": "9C",
            "icao": "CQH",
            "name_cn": "春秋航空",
            "name_short": "春秋",
            "name_en": "Spring Airlines",
            "hubs": [
                {"city_code": "S-上海浦东", "iata": "SHA", "type": "hub", "note": "主基地"},
            ],
            "fleet_size": 130,
            "alliance": "无（低成本）",
            "headquarters": "上海",
            "website": "www.ch.com",
            "aog_contact": {"phone": "021-22352781", "email": "aog@ch.com"},
            "data_source": "test",
            "verified": True,
            "verified_at": "2026-07-22",
        },
    ]
    p = tmp_path / "airlines.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def airlines_client_with_test_data(airlines_test_data: Path):
    """Reset + 注入 test path + 重新 load + yield + cleanup"""
    import os
    os.environ["AIRLINES_DATA_PATH"] = str(airlines_test_data)

    from aog_web.config import reset_settings_cache
    from aog_web.services.airlines_client import (
        get_airlines_client,
        reset_airlines_client,
    )

    reset_settings_cache()
    reset_airlines_client()
    client = get_airlines_client()
    yield client

    # cleanup
    os.environ.pop("AIRLINES_DATA_PATH", None)
    reset_settings_cache()
    reset_airlines_client()


# ===== Scenario 1: list =====

@pytest.mark.asyncio
async def test_list_airlines_ok(client, airlines_client_with_test_data):
    """GET /api/airlines → 3 航司, 字段完整"""
    r = await client.get("/api/airlines")
    assert r.status_code == 200
    airlines = r.json()
    assert len(airlines) == 3
    # IATA 字母序
    assert [a["iata"] for a in airlines] == ["9C", "CA", "MU"]
    # 字段 1:1 对齐 data/airlines.json schema
    c = airlines[1]  # CA
    for key in [
        "iata", "icao", "name_cn", "name_en", "hubs",
        "fleet_size", "alliance", "headquarters", "website",
        "aog_contact", "data_source", "verified", "verified_at",
    ]:
        assert key in c, f"missing field: {key}"
    assert c["iata"] == "CA"
    assert c["name_cn"] == "中国国际航空"
    assert isinstance(c["hubs"], list) and len(c["hubs"]) >= 1


@pytest.mark.asyncio
async def test_list_airlines_empty(client):
    """没有 test data (default real file 仍存在) — 不报 500"""
    r = await client.get("/api/airlines")
    assert r.status_code == 200
    # 返 list, 不崩 (长度由真实 data 决定)
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_list_airlines_filter_letter(client, airlines_client_with_test_data):
    """letter=C → CA only (9C / MU 过滤掉)"""
    r = await client.get("/api/airlines?letter=C")
    assert r.status_code == 200
    airlines = r.json()
    assert all(a["iata"].startswith("C") or a["name_cn"].startswith("C") for a in airlines)
    assert any(a["iata"] == "CA" for a in airlines)


@pytest.mark.asyncio
async def test_list_airlines_invalid_letter(client, airlines_client_with_test_data):
    r = await client.get("/api/airlines?letter=AB")
    assert r.status_code == 400


# ===== Scenario 2: detail =====

@pytest.mark.asyncio
async def test_get_airline_ok(client, airlines_client_with_test_data):
    """GET /api/airlines/CA → 200 + 完整字段"""
    r = await client.get("/api/airlines/CA")
    assert r.status_code == 200
    a = r.json()
    assert a["iata"] == "CA"
    assert a["icao"] == "CCA"
    assert a["name_cn"] == "中国国际航空"
    assert a["fleet_size"] == 491
    # aog_contact 嵌套
    assert a["aog_contact"]["phone"].startswith("010-")


@pytest.mark.asyncio
async def test_get_airline_lowercase_ok(client, airlines_client_with_test_data):
    """小写 iata 应 work (uppercase 内部归一)"""
    r = await client.get("/api/airlines/ca")
    assert r.status_code == 200
    assert r.json()["iata"] == "CA"


@pytest.mark.asyncio
async def test_get_airline_404(client, airlines_client_with_test_data):
    r = await client.get("/api/airlines/XX")
    assert r.status_code == 404
    body = r.json()
    assert "not found" in body["detail"]["error"]


@pytest.mark.asyncio
async def test_get_airline_invalid_iata(client, airlines_client_with_test_data):
    """非 2 字母 → 400"""
    r = await client.get("/api/airlines/CA1")
    assert r.status_code == 400


# ===== Scenario 3: search =====

@pytest.mark.asyncio
async def test_search_airlines_by_iata(client, airlines_client_with_test_data):
    """搜 IATA 'CA' → CA 命中"""
    r = await client.get("/api/airlines/search?q=CA")
    assert r.status_code == 200
    airlines = r.json()
    assert any(a["iata"] == "CA" for a in airlines)


@pytest.mark.asyncio
async def test_search_airlines_by_cn_name(client, airlines_client_with_test_data):
    """搜中文名 '东航' → MU 命中"""
    r = await client.get("/api/airlines/search?q=东航")
    assert r.status_code == 200
    airlines = r.json()
    assert any(a["iata"] == "MU" for a in airlines)


@pytest.mark.asyncio
async def test_search_airlines_by_en_name(client, airlines_client_with_test_data):
    """搜英文名 'Spring' → 9C 命中"""
    r = await client.get("/api/airlines/search?q=Spring")
    assert r.status_code == 200
    airlines = r.json()
    assert any(a["iata"] == "9C" for a in airlines)


@pytest.mark.asyncio
async def test_search_airlines_no_match(client, airlines_client_with_test_data):
    """搜不到 → 空 list, 不 404"""
    r = await client.get("/api/airlines/search?q=NoSuchAirlineXYZ")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_search_airlines_empty_query(client, airlines_client_with_test_data):
    """q 为空 → 422 (FastAPI min_length=1)"""
    r = await client.get("/api/airlines/search?q=")
    assert r.status_code == 422
