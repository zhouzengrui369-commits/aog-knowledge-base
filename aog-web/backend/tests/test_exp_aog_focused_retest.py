"""Focused regression tests for Issue #12 EXP-AOG-20260803-001/002/004."""
from __future__ import annotations

import pytest

from aog_web.api import chat_safe
from aog_web.api.chat_safe import _build_context_block, _reference_from_hit
from aog_web.services.verification_policy import (
    RetrievalPolicyResult,
    apply_retrieval_policy,
    blocked_city_answer,
    reference_route,
)


def _city(code: str, name: str, iata: str, review_status: str) -> dict:
    return {
        "code": code,
        "name": name,
        "iata": iata,
        "pinyin": name,
        "trust": {"review_status": review_status},
    }


def _hit(source_type: str, source_id: str, text: str = "fixture") -> dict:
    return {
        "id": f"{source_type}:{source_id}:0",
        "text": text,
        "metadata": {
            "source_type": source_type,
            "source_id": source_id,
            "title": f"{source_id} source",
            "status": "现行",
        },
        "score": 0.8,
    }


def test_unverified_target_blocks_generation_before_context() -> None:
    cities = [
        _city("B-测试甲", "测试甲", "TAA", "UNVERIFIED"),
        _city("V-测试乙", "测试乙", "TBB", "VERIFIED"),
    ]
    sensitive = "139" + "0000" + "1111"
    hits = [
        _hit("city", "B-测试甲", f"未核验预案 {sensitive}"),
        _hit("city_contacts", "B-测试甲", f"未核验联系人 {sensitive}"),
        _hit("city", "V-测试乙", "已核验对照资料"),
    ]

    result = apply_retrieval_policy(
        hits,
        cities=cities,
        question="测试甲 AOG 如何处理",
    )

    assert result.blocked is True
    assert result.hits == []
    assert [item.review_status for item in result.blocked_targets] == ["UNVERIFIED"]
    answer = blocked_city_answer(result.blocked_targets)
    assert "UNVERIFIED / 不可用于操作" in answer
    assert sensitive not in answer
    assert "联系人、联系方式、库存、物流和预案正文" in answer


def test_verified_target_keeps_only_matching_verified_city_sources() -> None:
    cities = [
        _city("V-测试乙", "测试乙", "TBB", "VERIFIED"),
        _city("U-测试丙", "测试丙", "TCC", "UNVERIFIED"),
    ]
    result = apply_retrieval_policy(
        [
            _hit("city", "V-测试乙", "verified city"),
            _hit("city_contacts", "V-测试乙", "verified contacts"),
            _hit("city", "U-测试丙", "unverified city"),
            _hit("unknown_kind", "raw-document", "unknown"),
        ],
        cities=cities,
        question="TBB 已核验保障资源",
    )

    assert result.blocked is False
    assert {item["metadata"]["source_type"] for item in result.hits} == {
        "city",
        "city_contacts",
    }
    assert all(
        item["metadata"]["verification_status"] == "VERIFIED"
        for item in result.hits
    )


def test_city_contacts_route_is_explicit_and_unknown_kind_fails_closed() -> None:
    cities = [_city("V-测试乙", "测试乙", "TBB", "VERIFIED")]
    policy = apply_retrieval_policy(
        [_hit("city_contacts", "V-测试乙", "contact source")],
        cities=cities,
        question="测试乙联系人",
    )
    reference = _reference_from_hit(policy.hits[0])
    assert reference.available is True
    assert reference.href == "/city/V-%E6%B5%8B%E8%AF%95%E4%B9%99?tab=contacts"
    assert reference.verification_status == "VERIFIED"
    assert not reference.href.startswith("/city_contacts:")

    unknown = reference_route(_hit("unknown_kind", "raw-doc-id"))
    assert unknown.available is False
    assert unknown.href is None
    assert "伪链接" in (unknown.reason or "")


def test_city_linked_wiki_inherits_city_status() -> None:
    cities = [
        _city("U-测试丙", "测试丙", "TCC", "UNVERIFIED"),
        _city("V-测试乙", "测试乙", "TBB", "VERIFIED"),
    ]
    result = apply_retrieval_policy(
        [
            _hit("wiki", "MOC-U-测试丙-故障树", "unverified wiki"),
            _hit("wiki", "MOC-V-测试乙-故障树", "verified wiki"),
        ],
        cities=cities,
        question="一般故障树",
    )
    assert len(result.hits) == 1
    assert result.hits[0]["metadata"]["city_code"] == "V-测试乙"
    assert result.hits[0]["metadata"]["verification_status"] == "VERIFIED"


def test_context_includes_code_assigned_verification_status() -> None:
    hit = _hit("experience", "exp-test", "现行经验正文")
    hit["metadata"]["verification_status"] = "VERIFIED"
    block = _build_context_block([hit])
    assert "verification_status=VERIFIED" in block
    assert "source_type=experience" in block


@pytest.mark.asyncio
async def test_unverified_stream_keeps_refs_intermediate_until_done(client, seeded_sqlite) -> None:
    # NJX 8/4 12:02 拍板 "修报错": UNVERIFIED 城市不再 return early 阻断 grounded,
    # fall through 到 grounded FTS5 retrieval (跟 b390629d chat.py 行为一致).
    # 严守 PII 风险: LLM context 只含 VERIFIED eligible hits (annotation_hit 强制 verification_status=VERIFIED).
    # Test 仍验证: phase 顺序 queued → retrieving → refs → generating → token → done, 没 error.
    response = await client.post(
        "/api/chat/stream",
        json={"q": "上海浦东 AOG 如何处置"},
    )
    assert response.status_code == 200
    stream = response.text
    markers = [
        '"phase": "queued"',
        '"phase": "retrieving"',
        "event: refs",
        '"phase": "generating"',
        "event: token",
        '"phase": "done"',
        "event: done",
    ]
    positions = [stream.find(marker) for marker in markers]
    assert all(position >= 0 for position in positions), stream[:1000]
    assert positions == sorted(positions)
    # R3 commit 3 (NJX 12:02 拍板) 后: UNVERIFIED 走 grounded, 不再返 "UNVERIFIED / 不可用于操作" 边界答案
    # 仍验证 grounded 流完整性: phase 顺序 + token 事件 + 没 error
    assert "event: error" not in stream


@pytest.mark.asyncio
async def test_stream_error_is_terminal_and_never_followed_by_done(
    client, monkeypatch
) -> None:
    verified_hit = _hit("experience", "exp-test", "verified fixture")
    verified_hit["metadata"]["verification_status"] = "VERIFIED"

    async def fake_policy(request, body):
        return RetrievalPolicyResult(
            hits=[verified_hit],
            blocked_targets=[],
            target_codes=[],
            quarantined_count=0,
        )

    class FailingLLM:
        model = "fixture-live-provider"

        async def stream_chat(self, messages, **kwargs):
            if False:
                yield ""
            raise RuntimeError("fixture provider failure")

        async def close(self):
            return None

    monkeypatch.setattr(chat_safe, "_retrieve_with_policy", fake_policy)
    monkeypatch.setattr(chat_safe, "get_llm", lambda settings: FailingLLM())

    response = await client.post("/api/chat/stream", json={"q": "fixture question"})
    assert response.status_code == 200
    stream = response.text
    assert '"phase": "error"' in stream
    assert "event: error" in stream
    assert '"phase": "done"' not in stream
    assert "event: done" not in stream
