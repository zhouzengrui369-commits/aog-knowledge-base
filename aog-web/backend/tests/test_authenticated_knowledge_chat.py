"""Owner R5.1: authenticated AI can retrieve pending knowledge with status."""
from __future__ import annotations

import json

import pytest

from aog_web.api import chat_safe
from aog_web.services.verification_policy import CityTrustRecord, RetrievalPolicyResult


def _raw_unverified_hit() -> dict:
    return {
        "id": "city:H-赫尔辛基:0",
        "text": "候选保障预案：B787 航材保障；内部电话 13900003333；邮箱 warehouse@example.test。",
        "metadata": {
            "source_type": "city",
            "source_id": "H-赫尔辛基",
            "title": "赫尔辛基候选保障预案",
            "status": "现行",
        },
        "score": 0.91,
    }


def _blocked_policy() -> RetrievalPolicyResult:
    return RetrievalPolicyResult(
        hits=[],
        blocked_targets=[
            CityTrustRecord(
                code="H-赫尔辛基",
                name="赫尔辛基",
                iata="HEL",
                pinyin="heerxinji",
                review_status="UNVERIFIED",
            )
        ],
        target_codes=["H-赫尔辛基"],
        quarantined_count=1,
    )


async def _login(client) -> None:
    response = await client.post("/api/auth/login", json={"password": "13456789"})
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_authenticated_chat_uses_unverified_knowledge_with_status_and_pii_redaction(
    client, seeded_sqlite, monkeypatch
) -> None:
    raw = _raw_unverified_hit()
    policy = _blocked_policy()
    captured: list[dict] = []

    async def fake_retrieve(request, body):
        return [raw], policy

    class CapturingLLM:
        model = "fixture-live-provider"

        async def chat(self, messages, **kwargs):
            captured.extend(messages)
            return "## 候选知识\n\n待核验资料中记载：B787 航材保障。实际处置前请核验。"

        async def close(self):
            return None

    monkeypatch.setattr(chat_safe, "_retrieve_with_policy", fake_retrieve)
    monkeypatch.setattr(chat_safe, "get_llm", lambda settings: CapturingLLM())

    await _login(client)
    response = await client.post("/api/chat", json={"q": "赫尔辛基 AOG 保障预案写了什么"})
    assert response.status_code == 200, response.text

    sent = "\n".join(str(item.get("content") or "") for item in captured)
    assert "候选保障预案" in sent
    assert "verification_status=UNVERIFIED" in sent
    assert "13900003333" not in sent
    assert "warehouse@example.test" not in sent
    assert "[REDACTED-PHONE]" in sent
    assert "[REDACTED-EMAIL]" in sent

    payload = response.json()
    assert "待核验资料中记载" in payload["answer"]
    assert payload["references"]
    assert payload["references"][0]["verification_status"] == "UNVERIFIED"


@pytest.mark.asyncio
async def test_authenticated_unverified_stream_is_visible_without_private_reasoning(
    client, seeded_sqlite, monkeypatch
) -> None:
    raw = _raw_unverified_hit()
    policy = _blocked_policy()
    captured: list[dict] = []

    async def fake_retrieve(request, body):
        return [raw], policy

    class StreamingLLM:
        model = "fixture-live-provider"

        async def stream_chat(self, messages, **kwargs):
            captured.extend(messages)
            for chunk in (
                "<think>PRIVATE-COT</think>",
                "## 待核验知识\n\n",
                "待核验资料中记载：B787 航材保障。",
            ):
                yield chunk

        async def close(self):
            return None

    monkeypatch.setattr(chat_safe, "_retrieve_with_policy", fake_retrieve)
    monkeypatch.setattr(chat_safe, "get_llm", lambda settings: StreamingLLM())

    await _login(client)
    response = await client.post("/api/chat/stream", json={"q": "赫尔辛基 AOG 保障预案写了什么"})
    assert response.status_code == 200
    stream = response.text

    sent = "\n".join(str(item.get("content") or "") for item in captured)
    assert "verification_status=UNVERIFIED" in sent
    assert "13900003333" not in sent
    assert "warehouse@example.test" not in sent
    assert "PRIVATE-COT" not in stream
    assert "event: think" not in stream
    assert "待核验资料中记载" in stream
    assert "event: done" in stream
    assert '"knowledge_retrievable": true' in stream
    assert '"verified_operational_authority_only": true' in stream


@pytest.mark.asyncio
async def test_unauthenticated_unverified_target_stays_fail_closed(
    client, seeded_sqlite, monkeypatch
) -> None:
    raw = _raw_unverified_hit()
    policy = _blocked_policy()

    async def fake_retrieve(request, body):
        return [raw], policy

    def forbidden_llm(*args, **kwargs):
        raise AssertionError("unauthenticated UNVERIFIED target must not create an LLM")

    monkeypatch.setattr(chat_safe, "_retrieve_with_policy", fake_retrieve)
    monkeypatch.setattr(chat_safe, "get_llm", forbidden_llm)

    response = await client.post("/api/chat", json={"q": "赫尔辛基 AOG 保障预案写了什么"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "verification-policy"
    assert "UNVERIFIED / 不可用于操作" in payload["answer"]
    assert "13900003333" not in json.dumps(payload, ensure_ascii=False)
