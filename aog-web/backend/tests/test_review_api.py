"""R5 review-plane regression tests."""
from __future__ import annotations

import pytest


async def _login(client) -> None:
    response = await client.post("/api/auth/login", json={"password": "13456789"})
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_review_api_requires_authenticated_session(client, seeded_sqlite) -> None:
    response = await client.get("/api/review/cities")
    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "review_auth_required"

    response = await client.get("/api/review/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_pending_review_list_is_browsable_but_not_operational(client, seeded_sqlite) -> None:
    await _login(client)
    response = await client.get("/api/review/cities")
    assert response.status_code == 200, response.text
    rows = response.json()
    by_code = {item["code"]: item for item in rows}

    assert "H-赫尔辛基" in by_code
    hel = by_code["H-赫尔辛基"]
    assert hel["review_status"] == "UNVERIFIED"
    assert hel["review_visible"] is True
    assert hel["operational_eligible"] is False
    assert hel["ai_eligible"] is False
    assert hel["read_only"] is True
    assert hel["has_candidate_content"] is True
    assert hel["review_id"].startswith("review-city-")

    # VERIFIED records are not backlog items unless explicitly requested.
    assert "B-北京大兴" not in by_code


@pytest.mark.asyncio
async def test_pending_review_detail_keeps_candidate_content_with_pii_redaction(client, seeded_sqlite) -> None:
    await _login(client)
    response = await client.get("/api/review/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA")
    assert response.status_code == 200, response.text
    city = response.json()

    assert city["review_mode"] is True
    assert city["review"]["review_status"] == "UNVERIFIED"
    assert city["review"]["operational_eligible"] is False
    assert city["review"]["ai_eligible"] is False
    assert city["review"]["read_only"] is True
    assert "国际外站" in city["content_md"]
    assert city["fleet"]
    assert city["parts"]
    assert city["logistics"]["air"] == "6h"
    assert "仅用于审核阅读" in city["operational_notice"]

    contacts = {item["org"]: item for item in city["contacts"]}
    assert contacts["Satair Finland"]["phone"] == ["REDACTED"]
    assert contacts["Satair Finland"]["role"] == "[已脱敏/受限]"
    assert contacts["库房供应商"]["phone"] == ["REDACTED"]


@pytest.mark.asyncio
async def test_operational_endpoint_still_hides_same_unverified_candidate(client, seeded_sqlite) -> None:
    # The new review plane must not weaken the existing public/operational plane.
    response = await client.get("/api/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA")
    assert response.status_code == 200, response.text
    city = response.json()
    assert city["data_available"] is False
    assert city["content_md"] == ""
    assert city["fleet"] == []
    assert city["parts"] == []
    assert city["contacts"] == []
    assert "禁止用于实际 AOG 处置" in city["operational_notice"]


@pytest.mark.asyncio
async def test_review_api_is_read_only_and_does_not_promote_status(client, seeded_sqlite) -> None:
    await _login(client)
    before = (await client.get("/api/review/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA")).json()
    assert before["review"]["review_status"] == "UNVERIFIED"

    response = await client.post(
        "/api/review/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA",
        json={"review_status": "VERIFIED"},
    )
    assert response.status_code == 405

    after = (await client.get("/api/review/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA")).json()
    assert after["review"]["review_status"] == "UNVERIFIED"
