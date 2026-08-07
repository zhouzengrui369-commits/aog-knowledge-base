"""Authenticated read-only knowledge review API.

R5 separates knowledge visibility/retrieval from operational verification.
Candidate city content may be inspected by an authenticated reviewer and may be
retrieved by authenticated AI after PII sanitization without changing its
verification status. Only VERIFIED material is operationally authoritative.
"""
from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request

from aog_web.api import auth
from aog_web.services.sqlite_client import get_sqlite_client
from aog_web.services.verification_policy import VERIFIED, normalize_review_status

router = APIRouter(prefix="/api/review", tags=["review"])

# Structured contacts are permission-aware and already redacted by sqlite_client.
# Candidate documents also contain free-text phone/email values in fields such as
# warehouse, logistics and content_md. Those fields have no permission metadata,
# so the review plane must fail closed rather than infer that a contact is public.
_CN_MOBILE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_GENERIC_PHONE_REDACTION = "[联系方式已脱敏]"
_GENERIC_EMAIL_REDACTION = "[邮箱已脱敏]"
_WAREHOUSE_PHONE_REDACTION = "[联系方式已脱敏: 仓储联系人]"
_WAREHOUSE_EMAIL_REDACTION = "[邮箱已脱敏: 仓储联系人]"


def _require_authenticated_reviewer(
    request: Request,
    authorization: Optional[str],
    aog_session: Optional[str],
) -> None:
    """Require the existing AOG authenticated session for review surfaces."""
    bearer = auth._bearer_token(authorization)
    if authorization and not bearer and not aog_session:
        raise HTTPException(401, detail={"error": "review_auth_required", "reason": "malformed"})
    token = bearer or aog_session
    if not token:
        raise HTTPException(401, detail={"error": "review_auth_required", "reason": "missing"})
    try:
        auth._decode_token(token, auth._get_jwt_secret(request))
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, detail={"error": "review_auth_required", "reason": "expired"}) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, detail={"error": "review_auth_required", "reason": "invalid"}) from exc
    except Exception as exc:
        raise HTTPException(401, detail={"error": "review_auth_required", "reason": "invalid"}) from exc


def _sanitize_text(
    value: str,
    *,
    phone_replacement: str = _GENERIC_PHONE_REDACTION,
    email_replacement: str = _GENERIC_EMAIL_REDACTION,
) -> str:
    sanitized = _CN_MOBILE_RE.sub(phone_replacement, value)
    return _EMAIL_RE.sub(email_replacement, sanitized)


def _sanitize_free_text(
    value: Any,
    *,
    phone_replacement: str = _GENERIC_PHONE_REDACTION,
    email_replacement: str = _GENERIC_EMAIL_REDACTION,
) -> Any:
    """Recursively redact contact-shaped values from untyped candidate fields."""
    if isinstance(value, str):
        return _sanitize_text(
            value,
            phone_replacement=phone_replacement,
            email_replacement=email_replacement,
        )
    if isinstance(value, list):
        return [
            _sanitize_free_text(
                item,
                phone_replacement=phone_replacement,
                email_replacement=email_replacement,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: _sanitize_free_text(
                item,
                phone_replacement=phone_replacement,
                email_replacement=email_replacement,
            )
            for key, item in value.items()
        }
    return value


def _sanitize_review_city(city: Dict[str, Any]) -> Dict[str, Any]:
    """Return a review-safe copy while preserving permission-aware contacts.

    ``contacts`` has explicit permission/redaction metadata and is sanitized by
    ``sqlite_client``. Every other candidate field is untyped free text from the
    knowledge source, so mobile numbers and emails are redacted fail closed.
    Warehouse fields use a specific label so reviewers understand what was
    removed without mistaking the placeholder for missing source content.
    """
    safe = copy.deepcopy(city)
    for key, value in list(safe.items()):
        if key == "contacts":
            continue
        if key == "warehouse":
            safe[key] = _sanitize_free_text(
                value,
                phone_replacement=_WAREHOUSE_PHONE_REDACTION,
                email_replacement=_WAREHOUSE_EMAIL_REDACTION,
            )
        else:
            safe[key] = _sanitize_free_text(value)
    return safe


def _review_id(city: Dict[str, Any]) -> str:
    trust = city.get("trust") or {}
    material = "|".join(
        [
            "city",
            str(city.get("code") or ""),
            normalize_review_status(trust.get("review_status")),
            str(trust.get("source_document") or city.get("source_path") or ""),
        ]
    )
    return "review-city-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _has_candidate_content(city: Dict[str, Any]) -> bool:
    return bool(
        str(city.get("content_md") or "").strip()
        or city.get("fleet")
        or city.get("parts")
        or city.get("contacts")
        or any(str(value or "").strip() for value in (city.get("logistics") or {}).values())
        or str((city.get("warehouse") or {}).get("location") or "").strip()
    )


def _review_meta(city: Dict[str, Any]) -> Dict[str, Any]:
    trust = city.get("trust") or {}
    status = normalize_review_status(trust.get("review_status"))
    operational_eligible = status == VERIFIED
    ai_retrievable = _has_candidate_content(city)
    return {
        "review_id": _review_id(city),
        "review_status": status,
        "review_visible": True,
        "operational_eligible": operational_eligible,
        # Backward-compatible field: in R5.1 this means the knowledge can enter
        # status-aware AI retrieval, not that it is VERIFIED operational truth.
        "ai_eligible": ai_retrievable,
        "ai_retrievable": ai_retrievable,
        "read_only": True,
        "source_document": trust.get("source_document"),
        "source_location": trust.get("source_location"),
        "source_version": trust.get("source_version"),
        "updated_at": trust.get("updated_at") or city.get("updated_at"),
        "reviewed_at": trust.get("reviewed_at"),
        "reviewed_by": trust.get("reviewed_by"),
        "confidence": trust.get("confidence"),
        "environment": trust.get("environment"),
        "pii_classification": trust.get("pii_classification"),
    }


def _summary(city: Dict[str, Any]) -> Dict[str, Any]:
    review = _review_meta(city)
    return {
        "review_id": review["review_id"],
        "code": city.get("code"),
        "name": city.get("name"),
        "iata": city.get("iata"),
        "region": city.get("region"),
        "city_status": city.get("status"),
        "review_status": review["review_status"],
        "confidence": review["confidence"],
        "source_document": _sanitize_free_text(review["source_document"]),
        "source_location": _sanitize_free_text(review["source_location"]),
        "source_version": _sanitize_free_text(review["source_version"]),
        "updated_at": review["updated_at"],
        "reviewed_at": review["reviewed_at"],
        "reviewed_by": _sanitize_free_text(review["reviewed_by"]),
        "pii_classification": review["pii_classification"],
        "review_visible": True,
        "operational_eligible": review["operational_eligible"],
        "ai_eligible": review["ai_eligible"],
        "ai_retrievable": review["ai_retrievable"],
        "read_only": True,
        "has_candidate_content": _has_candidate_content(city),
    }


@router.get("/cities")
async def list_review_cities(
    request: Request,
    review_status: Optional[str] = Query(None),
    include_verified: bool = Query(False),
    authorization: Optional[str] = Header(default=None),
    aog_session: Optional[str] = Cookie(default=None, alias=auth.COOKIE_NAME),
) -> list[dict]:
    _require_authenticated_reviewer(request, authorization, aog_session)
    cities = await get_sqlite_client().list_cities()
    requested = normalize_review_status(review_status) if review_status else None
    result: list[dict] = []
    for city in cities:
        status = normalize_review_status((city.get("trust") or {}).get("review_status"))
        if not include_verified and status == VERIFIED:
            continue
        if requested and status != requested:
            continue
        result.append(_summary(city))
    result.sort(
        key=lambda item: (
            item["review_status"] == "MISSING",
            item["review_status"],
            str(item.get("name") or ""),
        )
    )
    return result


@router.get("/city/{code}")
async def get_review_city(
    request: Request,
    code: str,
    authorization: Optional[str] = Header(default=None),
    aog_session: Optional[str] = Cookie(default=None, alias=auth.COOKIE_NAME),
) -> dict:
    _require_authenticated_reviewer(request, authorization, aog_session)
    city = await get_sqlite_client().get_city(code)
    if city is None:
        raise HTTPException(404, detail={"error": "review city not found", "code": code})

    # Structured contact values are already permission-redacted by sqlite_client.
    # Free-text candidate fields need an additional review-plane PII boundary.
    result = _sanitize_review_city(city)
    review = _review_meta(result)
    result.update(
        {
            "review": review,
            "review_mode": True,
            "data_available": review["operational_eligible"],
            "operational_notice": None
            if review["operational_eligible"]
            else "候选内容可用于浏览和状态感知的 AI 检索；尚未 VERIFIED，实际 AOG 处置前必须核验。",
        }
    )
    return result
