"""Authenticated read-only knowledge review API.

R5 separates review visibility from operational eligibility. Candidate city
content may be inspected by an authenticated reviewer without changing its
verification status. Normal operational APIs and AI generation remain
VERIFIED-only/fail-closed.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request

from aog_web.api import auth
from aog_web.services.sqlite_client import get_sqlite_client
from aog_web.services.verification_policy import VERIFIED, normalize_review_status

router = APIRouter(prefix="/api/review", tags=["review"])


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


def _review_meta(city: Dict[str, Any]) -> Dict[str, Any]:
    trust = city.get("trust") or {}
    status = normalize_review_status(trust.get("review_status"))
    eligible = status == VERIFIED
    return {
        "review_id": _review_id(city),
        "review_status": status,
        "review_visible": True,
        "operational_eligible": eligible,
        "ai_eligible": eligible,
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


def _has_candidate_content(city: Dict[str, Any]) -> bool:
    return bool(
        str(city.get("content_md") or "").strip()
        or city.get("fleet")
        or city.get("parts")
        or city.get("contacts")
        or any(str(value or "").strip() for value in (city.get("logistics") or {}).values())
        or str((city.get("warehouse") or {}).get("location") or "").strip()
    )


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
        "source_document": review["source_document"],
        "source_location": review["source_location"],
        "source_version": review["source_version"],
        "updated_at": review["updated_at"],
        "reviewed_at": review["reviewed_at"],
        "reviewed_by": review["reviewed_by"],
        "pii_classification": review["pii_classification"],
        "review_visible": True,
        "operational_eligible": review["operational_eligible"],
        "ai_eligible": review["ai_eligible"],
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

    # sqlite_client already redacts non-public contact values. Unlike the
    # operational release policy, review mode deliberately keeps candidate
    # body/fleet/parts/logistics visible for human inspection.
    result = dict(city)
    review = _review_meta(city)
    result.update(
        {
            "review": review,
            "review_mode": True,
            "data_available": review["operational_eligible"],
            "operational_notice": None
            if review["operational_eligible"]
            else "候选内容仅用于审核阅读；未核验前禁止用于实际 AOG 处置或 AI 生成。",
        }
    )
    return result
