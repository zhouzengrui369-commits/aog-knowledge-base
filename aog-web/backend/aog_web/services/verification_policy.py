"""Verification policy for RAG retrieval, generation and references.

The policy is deliberately code-enforced.  The model never decides whether a
source is VERIFIED and cannot upgrade a source status in prose.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from urllib.parse import quote

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
_ALLOWED_REVIEW_STATUSES = {
    "VERIFIED",
    "UNVERIFIED",
    "STALE",
    "MISSING",
    "FIXTURE",
    "REDACTED",
}
_CITY_LINKED_TYPES = {"city", "city_contacts", "wiki"}
_CURATED_ACTIVE = {"现行", "active", "published", "current", "verified"}


@dataclass(frozen=True)
class CityTrustRecord:
    code: str
    name: str
    iata: str
    pinyin: str
    review_status: str


@dataclass(frozen=True)
class ReferenceRoute:
    href: Optional[str]
    available: bool
    reason: Optional[str] = None


@dataclass
class RetrievalPolicyResult:
    hits: List[Dict[str, Any]]
    blocked_targets: List[CityTrustRecord]
    target_codes: List[str]
    quarantined_count: int

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_targets)


def normalize_review_status(value: Any) -> str:
    status = str(value or UNVERIFIED).strip().upper()
    return status if status in _ALLOWED_REVIEW_STATUSES else UNVERIFIED


def city_trust_records(cities: Iterable[Mapping[str, Any]]) -> List[CityTrustRecord]:
    records: List[CityTrustRecord] = []
    for city in cities:
        trust = city.get("trust") if isinstance(city, Mapping) else None
        records.append(
            CityTrustRecord(
                code=str(city.get("code") or "").strip(),
                name=str(city.get("name") or "").strip(),
                iata=str(city.get("iata") or "").strip().upper(),
                pinyin=str(city.get("pinyin") or "").strip().lower(),
                review_status=normalize_review_status(
                    trust.get("review_status") if isinstance(trust, Mapping) else None
                ),
            )
        )
    return [record for record in records if record.code]


def _metadata(hit: Mapping[str, Any]) -> Dict[str, Any]:
    raw = hit.get("metadata")
    return dict(raw) if isinstance(raw, Mapping) else {}


def source_type_of(hit: Mapping[str, Any]) -> str:
    meta = _metadata(hit)
    return str(
        meta.get("source_type") or meta.get("kind") or meta.get("type") or ""
    ).strip().lower()


def source_id_of(hit: Mapping[str, Any]) -> str:
    meta = _metadata(hit)
    return str(
        meta.get("source_id")
        or meta.get("code")
        or meta.get("city_code")
        or ""
    ).strip()


def infer_city_code(
    hit: Mapping[str, Any], records: Sequence[CityTrustRecord]
) -> Optional[str]:
    meta = _metadata(hit)
    values = [
        source_id_of(hit),
        str(meta.get("code") or ""),
        str(meta.get("city_code") or ""),
        str(hit.get("id") or ""),
        str(meta.get("title") or hit.get("title") or ""),
    ]
    searchable = " | ".join(value for value in values if value).casefold()
    if not searchable:
        return None

    for record in sorted(records, key=lambda item: len(item.code), reverse=True):
        if record.code.casefold() in searchable:
            return record.code
    for record in sorted(records, key=lambda item: len(item.name), reverse=True):
        if record.name and record.name.casefold() in searchable:
            return record.code
    for record in records:
        if record.iata and re.search(rf"(?<![A-Z0-9]){re.escape(record.iata)}(?![A-Z0-9])", searchable.upper()):
            return record.code
    return None


def detect_target_cities(
    question: str,
    context_codes: Optional[Sequence[str]],
    records: Sequence[CityTrustRecord],
) -> List[CityTrustRecord]:
    selected: List[CityTrustRecord] = []
    by_code = {record.code: record for record in records}
    for code in context_codes or []:
        record = by_code.get(str(code))
        if record and record not in selected:
            selected.append(record)

    q = (question or "").strip()
    q_fold = q.casefold()
    for record in sorted(records, key=lambda item: max(len(item.code), len(item.name)), reverse=True):
        matched = bool(record.code and record.code.casefold() in q_fold)
        matched = matched or bool(record.name and record.name.casefold() in q_fold)
        if record.iata:
            matched = matched or bool(
                re.search(rf"(?<![A-Z0-9]){re.escape(record.iata)}(?![A-Z0-9])", q.upper())
            )
        if record.pinyin:
            matched = matched or record.pinyin in q_fold
        if matched and record not in selected:
            selected.append(record)
    return selected


def _explicit_status(meta: Mapping[str, Any]) -> Optional[str]:
    for key in ("verification_status", "review_status"):
        if meta.get(key):
            return normalize_review_status(meta.get(key))
    return None


def annotate_hit(
    hit: Mapping[str, Any], records: Sequence[CityTrustRecord]
) -> Dict[str, Any]:
    annotated = copy.deepcopy(dict(hit))
    meta = _metadata(annotated)
    source_type = source_type_of(annotated)
    city_code = infer_city_code(annotated, records)
    city_by_code = {record.code: record for record in records}

    explicit = _explicit_status(meta)
    if city_code and source_type in _CITY_LINKED_TYPES:
        verification_status = city_by_code[city_code].review_status
        basis = "city_review_status"
    elif explicit:
        verification_status = explicit
        basis = "source_metadata"
    elif source_type == "experience":
        status = str(meta.get("status") or "").strip().casefold()
        verification_status = VERIFIED if status in _CURATED_ACTIVE else UNVERIFIED
        basis = "curated_experience_status"
    elif source_type == "core_plan":
        verification_status = VERIFIED
        basis = "curated_core_plan_release"
    else:
        verification_status = UNVERIFIED
        basis = "missing_verification_metadata"

    meta.update(
        {
            "source_type": source_type,
            "source_id": source_id_of(annotated),
            "city_code": city_code or "",
            "verification_status": verification_status,
            "verification_basis": basis,
            "generation_eligible": verification_status == VERIFIED,
        }
    )
    annotated["metadata"] = meta
    return annotated


def apply_retrieval_policy(
    hits: Sequence[Mapping[str, Any]],
    *,
    cities: Sequence[Mapping[str, Any]],
    question: str,
    context_codes: Optional[Sequence[str]] = None,
) -> RetrievalPolicyResult:
    records = city_trust_records(cities)
    targets = detect_target_cities(question, context_codes, records)
    blocked_targets = [target for target in targets if target.review_status != VERIFIED]
    target_codes = [target.code for target in targets]

    annotated = [annotate_hit(hit, records) for hit in hits]
    eligible: List[Dict[str, Any]] = []
    quarantined = 0
    for hit in annotated:
        meta = _metadata(hit)
        if meta.get("verification_status") != VERIFIED:
            quarantined += 1
            continue
        if target_codes and source_type_of(hit) in _CITY_LINKED_TYPES:
            if meta.get("city_code") not in target_codes:
                quarantined += 1
                continue
        eligible.append(hit)

    if blocked_targets:
        # Strong P0 gate: no protected city-linked material reaches generation.
        eligible = []

    return RetrievalPolicyResult(
        hits=eligible,
        blocked_targets=blocked_targets,
        target_codes=target_codes,
        quarantined_count=quarantined,
    )


def reference_route(hit: Mapping[str, Any]) -> ReferenceRoute:
    meta = _metadata(hit)
    source_type = source_type_of(hit)
    source_id = source_id_of(hit)
    city_code = str(meta.get("city_code") or "").strip()

    if source_type == "city" and city_code:
        return ReferenceRoute(href=f"/city/{quote(city_code, safe='')}", available=True)
    if source_type == "city_contacts" and city_code:
        return ReferenceRoute(
            href=f"/city/{quote(city_code, safe='')}?tab=contacts",
            available=True,
        )
    if source_type == "experience" and source_id:
        return ReferenceRoute(
            href=f"/experience/{quote(source_id, safe='')}", available=True
        )
    if source_type == "wiki" and city_code:
        return ReferenceRoute(href=f"/city/{quote(city_code, safe='')}", available=True)
    if source_type == "core_plan":
        return ReferenceRoute(
            href=None,
            available=False,
            reason="核心预案暂未提供独立可打开页面",
        )
    return ReferenceRoute(
        href=None,
        available=False,
        reason="来源类型不受支持，已禁止生成伪链接",
    )


def blocked_city_answer(targets: Sequence[CityTrustRecord]) -> str:
    labels = "、".join(f"{target.name}（{target.review_status}）" for target in targets)
    return (
        "## 资料核验状态\n\n"
        f"**UNVERIFIED / 不可用于操作：{labels}**\n\n"
        "系统已在检索与生成前阻止该城市的联系人、联系方式、库存、物流和预案正文进入回答。\n\n"
        "请由当班航材 AOG 工程师按数据治理流程完成来源核验；核验完成前，不要据此进行联络、调拨或时效承诺。"
    )
