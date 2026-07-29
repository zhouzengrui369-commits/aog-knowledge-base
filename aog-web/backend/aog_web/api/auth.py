"""Auth endpoints - Sprint A 本地优先 (sprint-a-auth)

设计: MVP 简化方案, 密码明文比对 + PyJWT 签 24h token.

- POST /api/auth/login: 接受 {password}, 校验后返 JWT (sub=viewer, 24h)
- GET  /api/auth/verify: 校验 Authorization: Bearer <token>, 返 valid true/false

密码与 secret 都从环境变量读 (AOG_VIEW_PASSWORD / JWT_SECRET),
fallback 默认值仅供本地 dev / Sprint A 内部使用, **生产前必须改**.

注意: token payload 用 viewer 单一角色, 不区分 admin/user (MVP).
后续要 enforce 时, 把 verify 改成 FastAPI Depends 即可, 不影响 login.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import jwt  # PyJWT
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# === 常量 ===
# 默认密码仅用于本地 dev; SCF 部署必须设置 AOG_VIEW_PASSWORD 环境变量
DEFAULT_VIEW_PASSWORD = "13456789"
# 默认 secret 仅用于本地 dev; SCF 部署必须设置 JWT_SECRET 环境变量
# (标 REPLACE IN PRODUCTION 让 grep 时能定位)
DEFAULT_JWT_SECRET = "aog-dev-jwt-secret-REPLACE_IN_PRODUCTION"
TOKEN_TTL_S = 24 * 60 * 60  # 24h


# === Pydantic schema ===
class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    ok: bool = True
    token: str
    expires_in: int  # seconds


class VerifyResponse(BaseModel):
    ok: bool = True
    valid: bool
    reason: Optional[str] = None  # valid=False 时填, e.g. "expired" / "bad_signature" / "missing"


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str


# === helpers ===
def _get_password(request: Request) -> str:
    """从 settings 取 view password; fallback 默认值"""
    settings = getattr(request.app.state, "settings", None)
    if settings is not None and getattr(settings, "AOG_VIEW_PASSWORD", ""):
        return settings.AOG_VIEW_PASSWORD
    return DEFAULT_VIEW_PASSWORD


def _get_jwt_secret(request: Request) -> str:
    """从 settings 取 JWT secret; fallback 默认值"""
    settings = getattr(request.app.state, "settings", None)
    if settings is not None and getattr(settings, "JWT_SECRET", ""):
        return settings.JWT_SECRET
    return DEFAULT_JWT_SECRET


def _make_token(secret: str, ttl_s: int = TOKEN_TTL_S) -> Dict[str, Any]:
    """签发 24h JWT, payload: sub/iat/exp"""
    now = int(time.time())
    payload = {
        "sub": "viewer",
        "iat": now,
        "exp": now + ttl_s,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {"token": token, "expires_in": ttl_s, "iat": now, "exp": payload["exp"]}


def _decode_token(token: str, secret: str) -> Dict[str, Any]:
    """校验 JWT, 抛 jwt.* 异常让上层捕获"""
    return jwt.decode(token, secret, algorithms=["HS256"])


# === routes ===
@router.post("/login", response_model=LoginResponse, responses={401: {"model": ErrorResponse}})
async def login(req: LoginRequest, request: Request) -> LoginResponse:
    """POST /api/auth/login - 校验密码, 返 JWT

    Body: {"password": "13456789"}
    成功: {"ok": true, "token": "...", "expires_in": 86400}
    失败: 401 {"ok": false, "error": "invalid_password"}
    """
    expected = _get_password(request)
    # 用 hmac.compare_password 防 timing attack (虽然 MVP 是 4 字节 short string, 防御写上)
    if not _safe_equal(req.password, expected):
        # 不要泄漏密码长度/用户存在与否
        logger.info("auth.login: invalid password (expected_len=%d, got_len=%d)",
                    len(expected), len(req.password))
        raise HTTPException(status_code=401, detail={"ok": False, "error": "invalid_password"})

    secret = _get_jwt_secret(request)
    issued = _make_token(secret)
    logger.info("auth.login: success, token exp in %ds", issued["expires_in"])
    return LoginResponse(
        ok=True,
        token=issued["token"],
        expires_in=issued["expires_in"],
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> VerifyResponse:
    """GET /api/auth/verify - 校验 Authorization: Bearer <token>

    无 header → valid=False, reason=missing
    token 错/过期 → valid=False, reason=expired|bad_signature|invalid
    OK → valid=True
    """
    if not authorization:
        return VerifyResponse(ok=True, valid=False, reason="missing")

    # 拆 "Bearer xxx"
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return VerifyResponse(ok=True, valid=False, reason="malformed")

    token = parts[1].strip()
    if not token:
        return VerifyResponse(ok=True, valid=False, reason="malformed")

    secret = _get_jwt_secret(request)
    try:
        payload = _decode_token(token, secret)
    except jwt.ExpiredSignatureError:
        return VerifyResponse(ok=True, valid=False, reason="expired")
    except jwt.InvalidSignatureError:
        return VerifyResponse(ok=True, valid=False, reason="bad_signature")
    except jwt.InvalidTokenError as e:
        return VerifyResponse(ok=True, valid=False, reason="invalid")
    except Exception as e:
        # 兜底 (e.g. base64 decode error)
        logger.warning("auth.verify unexpected error: %s", e)
        return VerifyResponse(ok=True, valid=False, reason="invalid")

    # OK
    return VerifyResponse(ok=True, valid=True)


# === 内部 helper (test 复用) ===
def _safe_equal(a: str, b: str) -> bool:
    """constant-time string compare (避免 timing attack)"""
    import hmac
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
