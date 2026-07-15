"""POST /api/chat - RAG + LLM (Mock 模式)

★ NSM-2: references 强制 ≥ 1
"""
import pytest


@pytest.mark.asyncio
async def test_chat_with_seeded_data(client, seeded_sqlite):
    """Mock LLM + 空 Chroma → references 仍 ≥ 1 (SQLite 兜底)"""
    r = await client.post(
        "/api/chat",
        json={"q": "B787 风挡 AOG 怎么处理？"},
    )
    assert r.status_code == 200
    body = r.json()
    # 字段 1:1
    for key in ["answer", "references", "model", "latency_ms"]:
        assert key in body, f"missing field: {key}"
    # ★ NSM-2 红线
    assert len(body["references"]) >= 1, "NSM-2: references must be ≥ 1"
    # references 字段
    ref = body["references"][0]
    for key in ["id", "title", "href", "snippet", "score"]:
        assert key in ref
    # mock 模式标志
    assert "⚠️ Mock 模式" in body["answer"] or "Mock" in body["answer"]
    # model name
    assert "mock" in body["model"].lower() or body["model"] == "minimax-m3"
    # latency
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_chat_empty_q_rejected(client):
    """q 必须非空"""
    r = await client.post("/api/chat", json={"q": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_chat_with_context_codes(client, seeded_sqlite):
    """context_codes 可选参数, 不报错"""
    r = await client.post(
        "/api/chat",
        json={"q": "北京大兴 AOG", "context_codes": ["B-北京大兴"]},
    )
    assert r.status_code == 200
    assert len(r.json()["references"]) >= 1


@pytest.mark.asyncio
async def test_chat_nsm2_no_chroma_match(client, seeded_sqlite):
    """Chroma 空 → SQLite 兜底, 仍满足 NSM-2"""
    r = await client.post("/api/chat", json={"q": "完全不相关的关键词 xyz123"})
    assert r.status_code == 200
    body = r.json()
    # 即使 q 无任何匹配, 也要给 references (空 / 兜底)
    assert len(body["references"]) >= 1


@pytest.mark.asyncio
async def test_chat_general_question_mock_response(client, seeded_sqlite):
    """Mock 模式回答包含 Mock 标志"""
    r = await client.post("/api/chat", json={"q": "B787 风挡"})
    body = r.json()
    assert "⚠️ Mock 模式" in body["answer"]


@pytest.mark.asyncio
async def test_chat_request_validation(client):
    """缺 q 字段 → 422"""
    r = await client.post("/api/chat", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_chat_latency_p95(client, seeded_sqlite):
    """P95 latency ≤ 5s (CONTRACT §2.7)"""
    import time
    samples = []
    for q in ["B787 风挡", "浦东 AOG 联系人", "BMS9-3 玻璃纤维布", "北京大兴", "深圳宝安"]:
        t0 = time.time()
        r = await client.post("/api/chat", json={"q": q})
        elapsed = (time.time() - t0) * 1000
        assert r.status_code == 200
        samples.append(elapsed)
    samples.sort()
    p95 = samples[int(0.95 * len(samples)) - 1] if len(samples) > 1 else samples[0]
    # Mock LLM 模式下 P95 远低于 5s, 但留些余量 (冷启动可能慢)
    assert p95 < 5000, f"P95 latency {p95:.0f}ms exceeds 5s"
