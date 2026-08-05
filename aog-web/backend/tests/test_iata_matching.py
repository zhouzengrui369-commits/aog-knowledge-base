"""Unit tests for IATA matching in detect_target_cities (R3 fix).

The cda4547 / R1-era implementation used a direct substring / regex match
on `record.iata` inside the question, which caused false positives for
aviation acronyms:

  - 鞍山 iata=AOG collides with "Aircraft on Ground"
  - 墨尔本 iata=MEL collides with "Minimum Equipment List"
  - 阿姆斯特丹 iata=AMS collides with city name "Amsterdam"
  - 包头 iata=BAV collides with "Bavaria" / "BAVARIAN"
  - etc.

R3 introduces a two-step guard:

  1. Strict code/name match and pinyin match are unaffected (they cannot
     collide with English aviation acronyms).
  2. IATA fallback only fires when the question contains at least one
     explicit city/flight context verb (飞/到/在/去/从/备降/落地/机场/...).

These tests pin the new behaviour so future refactors cannot regress.
"""
from __future__ import annotations

import pytest

from aog_web.services.verification_policy import (
    CityTrustRecord,
    _has_city_intent,
    detect_target_cities,
)


# A representative subset of the 223 owner cities.  Each row deliberately
# mirrors a real city IATA from the seeded SQLite so the tests exercise the
# exact collisions the user observed in production (鞍山/AOG, 墨尔本/MEL,
# 哈巴罗夫斯克/MEL, 阿姆斯特丹/AMS, 包头/BAV, 北京首都/PEK, 曼谷素万那普/BKK,
# 洛杉矶/LAX, 东京羽田/HND, 罗马/FCO).
SEED_RECORDS = [
    CityTrustRecord(code="A-鞍山（暂停）", name="鞍山", iata="AOG", pinyin="anshan", review_status="UNVERIFIED"),
    CityTrustRecord(code="M-墨尔本", name="墨尔本", iata="MEL", pinyin="moerben", review_status="UNVERIFIED"),
    CityTrustRecord(code="（待开航）H-哈巴罗夫斯克（待开航）", name="（待开航）哈巴罗夫斯克", iata="MEL", pinyin="habaluofusike", review_status="UNVERIFIED"),
    CityTrustRecord(code="A-阿姆斯特丹（暂停）", name="阿姆斯特丹", iata="AMS", pinyin="amusitedan", review_status="UNVERIFIED"),
    CityTrustRecord(code="B-包头", name="包头", iata="BAV", pinyin="baotou", review_status="UNVERIFIED"),
    CityTrustRecord(code="B-北京首都（暂停）", name="北京首都", iata="PEK", pinyin="beijingshoudu", review_status="UNVERIFIED"),
    CityTrustRecord(code="B-北京大兴", name="北京大兴", iata="PKX", pinyin="beijingdaxing", review_status="VERIFIED"),
    CityTrustRecord(code="M-曼谷素万那普", name="曼谷素万那普", iata="BKK", pinyin="mangusuwannapu", review_status="UNVERIFIED"),
    CityTrustRecord(code="L-洛杉矶（暂停）", name="洛杉矶", iata="LAX", pinyin="luoshanji", review_status="UNVERIFIED"),
    CityTrustRecord(code="D-东京羽田", name="东京羽田", iata="HND", pinyin="dongjingyutian", review_status="UNVERIFIED"),
    CityTrustRecord(code="R-罗马（暂停）", name="罗马", iata="FCO", pinyin="luoma", review_status="UNVERIFIED"),
]


def _codes(records):
    return sorted(r.code for r in records)


# ---------------------------------------------------------------------------
# 1.  Negative regression: aviation acronym questions must NOT match cities.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question",
    [
        # The exact user question from NJX 8/4 11:07.
        "B787 风挡 AOG 怎么处理？",
        # Variant from NJX 8/3 acceptance.
        "B787 1号风挡 AOG 应如何处置？",
        # Control group: no AOG, different acronym.
        "B787 1号风挡裂纹 MEL 放行标准是什么？",
        # PEK in a non-city context.
        "PEK 文件传输协议",
        # MEL in a non-city context.
        "B787 MEL 放行 章节 4",
        # AMS in a non-city context.
        "AMS 协议栈 实现",
    ],
)
def test_aviation_acronym_does_not_match_iata_when_no_intent(question):
    """A bare acronym must not select a city when the question is about
    an aviation domain concept, not a specific city."""
    selected = detect_target_cities(question, context_codes=None, records=SEED_RECORDS)
    # No city code should be selected from the IATA fallback path alone.
    # The only way a city could be selected is via a code/name/pinyin hit
    # that we know is not present in any of these acronym-only questions.
    assert _codes(selected) == [], (
        f"aviation acronym in question should not match any city; "
        f"got {selected!r} for question={question!r}"
    )


# ---------------------------------------------------------------------------
# 2.  Positive regression: explicit city/flight context must still match.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question, expected_code",
    [
        # 飞 + AOG + anshan should pick Anshan (real airport, paused).
        ("B787 飞 AOG 准备", "A-鞍山（暂停）"),
        # 备降 + AOG should pick Anshan.
        ("B787 备降 AOG 怎么准备？", "A-鞍山（暂停）"),
        # 落地 + MEL should pick Melbourne.
        ("B787 落地 MEL 准备", "M-墨尔本"),
        # 飞 + 鞍山 name should pick Anshan (strict name match).
        ("B787 飞鞍山准备", "A-鞍山（暂停）"),
        # 飞 + 北京大兴 should pick Beijing Daxing (VERIFIED).
        ("B787 飞北京大兴 准备", "B-北京大兴"),
        # 备降 + 东京羽田 should pick Tokyo Haneda.
        ("B787 备降东京羽田", "D-东京羽田"),
        # 机场 + 北京大兴 (intent) + name strict.
        ("北京大兴机场怎么走？", "B-北京大兴"),
        # 飞 + AMS should pick Amsterdam.
        ("B787 飞 AMS 准备", "A-阿姆斯特丹（暂停）"),
    ],
)
def test_city_intent_still_selects_expected_city(question, expected_code):
    selected = detect_target_cities(question, context_codes=None, records=SEED_RECORDS)
    codes = _codes(selected)
    assert expected_code in codes, (
        f"expected {expected_code!r} for question={question!r}, got {codes!r}"
    )


# ---------------------------------------------------------------------------
# 3.  Negative intent guard: bare acronym without city/flight verb.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question",
    [
        "AOG 风挡怎么换？",
        "MEL 放行标准",
        "AMS 协议栈",
        "PEK 文件格式",
        "BAV 数据导出",
    ],
)
def test_bare_acronym_without_intent_never_selects(question):
    """A bare acronym with no city/flight context verb must never pick a
    city via IATA fallback.  The user is asking about the concept, not
    the city."""
    selected = detect_target_cities(question, context_codes=None, records=SEED_RECORDS)
    assert _codes(selected) == [], (
        f"bare acronym without intent should select 0 cities; "
        f"got {selected!r} for question={question!r}"
    )


@pytest.mark.parametrize(
    "question, expected_code",
    [
        # 含 "机场" 是 intent-positive: 真的指该 city airport
        ("AMS 机场 ILS 进近程序", "A-阿姆斯特丹（暂停）"),
        ("AOG 是哪个机场？", "A-鞍山（暂停）"),
        ("BAV 机场 备降 准备", "B-包头"),
    ],
)
def test_acronym_with_机场_intent_selects_expected_city(question, expected_code):
    """A city-intent verb like 机场 makes the IATA fallback legitimate."""
    selected = detect_target_cities(question, context_codes=None, records=SEED_RECORDS)
    codes = _codes(selected)
    assert expected_code in codes, (
        f"expected {expected_code!r} for question={question!r}, got {codes!r}"
    )


# ---------------------------------------------------------------------------
# 4.  Strict match: Chinese name and code still work without intent.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question, expected_code",
    [
        ("北京大兴有什么航材？", "B-北京大兴"),
        ("墨尔本机场怎么走？", "M-墨尔本"),
        ("包头机场 备降 准备", "B-包头"),
    ],
)
def test_strict_name_match_unaffected(question, expected_code):
    """Chinese name / code matching must still work even in pure knowledge
    questions, because it cannot collide with aviation acronyms."""
    selected = detect_target_cities(question, context_codes=None, records=SEED_RECORDS)
    codes = _codes(selected)
    assert expected_code in codes, (
        f"strict name match should still pick {expected_code!r}, got {codes!r}"
    )


# ---------------------------------------------------------------------------
# 5.  context_codes still have absolute priority.
# ---------------------------------------------------------------------------

def test_context_codes_take_priority():
    """A context_codes entry (e.g. user's pinned city) must always be
    selected, even if the question text contradicts it.  This preserves
    the R1-era contract for the chat widget's pinned-city UX."""
    selected = detect_target_cities(
        "B787 风挡 AOG 怎么处理？",
        context_codes=["B-北京大兴"],
        records=SEED_RECORDS,
    )
    codes = _codes(selected)
    assert "B-北京大兴" in codes
    # AOG (鞍山) is NOT in the selected set because the question has no
    # city/flight intent verb and 鞍山 is not in context_codes.
    assert "A-鞍山（暂停）" not in codes


# ---------------------------------------------------------------------------
# 6.  _has_city_intent unit tests.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question, expected",
    [
        # Positive intent — Chinese flight/aviation verbs.
        ("B787 飞 AOG 准备", True),
        ("B787 备降 AOG", True),
        ("B787 落地 MEL", True),
        ("北京大兴机场怎么走？", True),
        ("B787 经停 PKX", True),
        ("B787 在 PEK 起降", True),
        ("B787 去 LAX 出差", True),
        ("B787 从 HND 起飞", True),
        ("开通 PEK 航线", True),
        ("B787 航材保障", True),
        # Negative intent — pure domain questions with no city/flight verb.
        ("B787 风挡 AOG 怎么处理？", False),
        ("B787 1号风挡 AOG 应如何处置？", False),
        ("B787 1号风挡裂纹 MEL 放行标准是什么？", False),
        ("AOG 风挡怎么换？", False),
        ("MEL 放行标准", False),
        ("AMS 协议栈", False),
        ("PEK 文件格式", False),
        # Edge: question must not be empty.
        ("", False),
    ],
)
def test_has_city_intent(question, expected):
    assert _has_city_intent(question) is expected, (
        f"_has_city_intent({question!r}) returned not {expected}"
    )


# ---------------------------------------------------------------------------
# 7.  Sorted by length (longest first) preserved — R1 contract regression.
# ---------------------------------------------------------------------------

def test_strict_match_prefers_longest_code_first():
    """The R1 contract sorted records by max(code, name) length descending
    so the longest match wins.  R3 keeps the same ordering for strict
    matching."""
    selected = detect_target_cities(
        "B-北京大兴有什么航材？",
        context_codes=None,
        records=SEED_RECORDS,
    )
    codes = _codes(selected)
    assert "B-北京大兴" in codes
