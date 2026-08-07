"""R5 review-plane regression tests."""
from __future__ import annotations

import json
import re

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
async def test_review_detail_redacts_phone_and_email_from_free_text(client, seeded_sqlite) -> None:
    """Codex R5 P0: warehouse/free text must not bypass contact redaction."""
    from aog_web.services.sqlite_client import CityRow

    private_phone = "139" + "00003333"
    private_email = "warehouse" + "@example.test"
    async with seeded_sqlite.session_factory() as session:
        row = await session.get(CityRow, "H-赫尔辛基")
        assert row is not None
        row.warehouse = json.dumps(
            {
                "location": "赫尔辛基机场东航区",
                "main": [
                    f"候选保障：联系方式、{private_phone} 机务经理",
                    f"候选邮箱：{private_email}",
                ],
                "internal_contacts": {
                    "duty": private_phone,
                    "email": private_email,
                },
            },
            ensure_ascii=False,
        )
        row.content_md = (
            "# 赫尔辛基\n\n"
            f"候选正文自由文本联系方式 {private_phone} / {private_email}。"
        )
        await session.commit()

    await _login(client)
    response = await client.get("/api/review/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA")
    assert response.status_code == 200, response.text
    city = response.json()
    serialized = json.dumps(city, ensure_ascii=False)

    assert private_phone not in serialized
    assert private_email not in serialized
    assert re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", serialized) is None
    assert re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", serialized) is None

    warehouse_text = json.dumps(city["warehouse"], ensure_ascii=False)
    assert "[联系方式已脱敏: 仓储联系人]" in warehouse_text
    assert "[邮箱已脱敏: 仓储联系人]" in warehouse_text
    assert "[联系方式已脱敏]" in city["content_md"]
    assert "[邮箱已脱敏]" in city["content_md"]

    # Structured public contacts keep their existing permission-aware behavior.
    contacts = {item["org"]: item for item in city["contacts"]}
    assert contacts["东航赫尔辛基站"]["permission"] == "public"
    assert contacts["东航赫尔辛基站"]["phone"] == ["+358-9-1234567"]


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
