"""GET /api/cities + /api/city/{code} - CONTRACT §2.2 + §2.3"""
import pytest


@pytest.mark.asyncio
async def test_list_cities_empty(client):
    """空 DB → 返回 []"""
    r = await client.get("/api/cities")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_cities_seeded(client, seeded_sqlite):
    r = await client.get("/api/cities")
    assert r.status_code == 200
    cities = r.json()
    assert len(cities) == 3
    # 字段 1:1 对应 CONTRACT §1.1
    c = cities[0]
    for key in ["code", "name", "iata", "pinyin", "region", "status", "tags",
                "fleet", "parts", "contacts", "warehouse", "logistics",
                "content_md", "source_path", "updated_at"]:
        assert key in c, f"missing field: {key}"


@pytest.mark.asyncio
async def test_list_cities_pinyin_sorted(client, seeded_sqlite):
    r = await client.get("/api/cities")
    cities = r.json()
    pinyins = [c["pinyin"] for c in cities]
    assert pinyins == sorted(pinyins)
    # baotou < beijingdaxing < shanghaipudong
    assert pinyins[0] == "baotou"


@pytest.mark.asyncio
async def test_list_cities_filter_region(client, seeded_sqlite):
    r = await client.get("/api/cities?region=华北")
    assert r.status_code == 200
    cities = r.json()
    assert all(c["region"] == "华北" for c in cities)
    assert len(cities) == 2  # 北京大兴 + 包头


@pytest.mark.asyncio
async def test_list_cities_filter_status(client, seeded_sqlite):
    r = await client.get("/api/cities?status=暂停")
    cities = r.json()
    assert len(cities) == 1
    assert cities[0]["code"] == "B-包头"


@pytest.mark.asyncio
async def test_list_cities_filter_letter(client, seeded_sqlite):
    r = await client.get("/api/cities?letter=B")
    cities = r.json()
    # baotou + beijingdaxing 都以 b 开头
    assert all(c["pinyin"].upper().startswith("B") for c in cities)
    assert len(cities) == 2


@pytest.mark.asyncio
async def test_list_cities_invalid_status(client, seeded_sqlite):
    r = await client.get("/api/cities?status=invalid")
    assert r.status_code == 400
    assert "error" in r.json()["detail"]


@pytest.mark.asyncio
async def test_list_cities_invalid_letter(client, seeded_sqlite):
    r = await client.get("/api/cities?letter=AB")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_city_ok(client, seeded_sqlite):
    """URL 编码中文 - 用 quote 编码"""
    from urllib.parse import quote
    code = quote("B-北京大兴")
    r = await client.get(f"/api/city/{code}")
    assert r.status_code == 200
    city = r.json()
    assert city["code"] == "B-北京大兴"
    assert city["region"] == "华北"
    assert city["iata"] == "PKX"
    # 嵌套结构 1:1
    assert isinstance(city["fleet"], list)
    assert city["warehouse"]["location"]


@pytest.mark.asyncio
async def test_get_city_404(client, seeded_sqlite):
    r = await client.get("/api/city/NOT-EXIST")
    assert r.status_code == 404
    body = r.json()
    assert "not found" in body["detail"]["error"]


@pytest.mark.asyncio
async def test_get_city_empty(client):
    """空 DB → 404"""
    r = await client.get("/api/city/anything")
    assert r.status_code == 404
