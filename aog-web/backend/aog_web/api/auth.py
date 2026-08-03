"""Viewer authentication with a durable httpOnly session cookie."""
from __future__ import annotations

import hmac
import logging
import time
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

DEFAULT_VIEW_PASSWORD = "13456789"
DEFAULT_JWT_SECRET = "aog-dev-jwt-secret-REPLACE_IN_PRODUCTION"
TOKEN_TTL_S = 24 * 60 * 60
COOKIE_NAME = "aog_session"


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    ok: bool = True
    token: str
    expires_in: int


class VerifyResponse(BaseModel):
    ok: bool = True
    valid: bool
    reason: Optional[str] = None


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str


def _get_password(request: Request) -> str:
    settings = getattr(request.app.state, "settings", None)
    value = getattr(settings, "AOG_VIEW_PASSWORD", "") if settings else ""
    return value or DEFAULT_VIEW_PASSWORD


def _get_jwt_secret(request: Request) -> str:
    settings = getattr(request.app.state, "settings", None)
    value = getattr(settings, "JWT_SECRET", "") if settings else ""
    return value or DEFAULT_JWT_SECRET


def _make_token(secret: str, ttl_s: int = TOKEN_TTL_S) -> Dict[str, Any]:
    now = int(time.time())
    payload = {"sub": "viewer", "iat": now, "exp": now + ttl_s}
    return {
        "token": jwt.encode(payload, secret, algorithm="HS256"),
        "expires_in": ttl_s,
        "iat": now,
        "exp": payload["exp"],
    }


def _decode_token(token: str, secret: str) -> Dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])


def _safe_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


@router.post("/login", response_model=LoginResponse, responses={401: {"model": ErrorResponse}})
async def login(req: LoginRequest, request: Request, response: Response) -> LoginResponse:
    expected = _get_password(request)
    if not _safe_equal(req.password, expected):
        logger.info("auth.login rejected")
        raise HTTPException(401, detail={"ok": False, "error": "invalid_password"})

    issued = _make_token(_get_jwt_secret(request))
    response.set_cookie(
        key=COOKIE_NAME,
        value=issued["token"],
        max_age=issued["expires_in"],
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    logger.info("auth.login success; httpOnly cookie issued")
    # token remains in the response for CLI compatibility, but the browser does
    # not persist it in localStorage.
    return LoginResponse(token=issued["token"], expires_in=issued["expires_in"])


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/", samesite="lax")
    return {"ok": True}


@router.get("/verify", response_model=VerifyResponse)
async def verify(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    aog_session: Optional[str] = Cookie(default=None),
) -> VerifyResponse:
    token = _bearer_token(authorization) or aog_session
    if not token:
        return VerifyResponse(valid=False, reason="missing")
    try:
        _decode_token(token, _get_jwt_secret(request))
    except jwt.ExpiredSignatureError:
        return VerifyResponse(valid=False, reason="expired")
    except jwt.InvalidSignatureError:
        return VerifyResponse(valid=False, reason="bad_signature")
    except jwt.InvalidTokenError:
        return VerifyResponse(valid=False, reason="invalid")
    except Exception as exc:
        logger.warning("auth.verify unexpected error: %s", exc)
        return VerifyResponse(valid=False, reason="invalid")
    return VerifyResponse(valid=True)
