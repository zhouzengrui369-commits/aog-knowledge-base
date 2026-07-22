"""Sprint A · Auth endpoints - 3 场景 pytest

CONTRACT:
- POST /api/auth/login: 接受 {password}, 校验后返 JWT (sub=viewer, 24h)
- GET  /api/auth/verify: 校验 Authorization: Bearer <token>

3 场景:
1. valid password → login 返 200 + JWT (HS256, exp ~24h); verify 同一 token 返 valid=True
2. invalid password → login 返 401 {ok: false, error: invalid_password}
3. expired token → verify 返 valid=False, reason=expired
"""
from __future__ import annotations

import time

import jwt
import pytest


# === fixture: 让 AOG_VIEW_PASSWORD / JWT_SECRET 在 conftest 已经 reset 之后可读 ===
@pytest.fixture
def auth_settings(client):
    """读 settings (AOG_VIEW_PASSWORD 默认 '', 会 fallback 到 "13456789")"""
    from aog_web.api.auth import DEFAULT_JWT_SECRET, DEFAULT_VIEW_PASSWORD

    request_app = client._transport.app  # type: ignore[attr-defined]
    s = request_app.state.settings
    return {
        "password": s.AOG_VIEW_PASSWORD or DEFAULT_VIEW_PASSWORD,
        "secret": s.JWT_SECRET or DEFAULT_JWT_SECRET,
    }


# ===== 场景 1: valid password → 200 + JWT + verify 同一 token valid =====
@pytest.mark.asyncio
async def test_login_valid_returns_jwt_and_verify_accepts(client, auth_settings):
    pw = auth_settings["password"]
    secret = auth_settings["secret"]

    # login
    r = await client.post("/api/auth/login", json={"password": pw})
    assert r.status_code == 200, f"login 200 expected, got {r.status_code}: {r.text}"
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["token"], str) and len(body["token"]) > 20
    assert body["expires_in"] == 86400  # 24h

    # verify 同一 token
    r2 = await client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {body['token']}"},
    )
    assert r2.status_code == 200
    vbody = r2.json()
    assert vbody["ok"] is True
    assert vbody["valid"] is True
    assert vbody.get("reason") is None

    # 解码 payload 确认 sub/exp
    payload = jwt.decode(body["token"], secret, algorithms=["HS256"])
    assert payload["sub"] == "viewer"
    assert "iat" in payload
    assert "exp" in payload
    # exp - iat 应该 = 24h (允许 ±5s 误差)
    assert abs((payload["exp"] - payload["iat"]) - 86400) < 5


# ===== 场景 2: invalid password → 401 =====
@pytest.mark.asyncio
async def test_login_invalid_password_returns_401(client):
    r = await client.post("/api/auth/login", json={"password": "wrong-password-xyz"})
    assert r.status_code == 401, f"401 expected, got {r.status_code}: {r.text}"
    body = r.json()
    # FastAPI HTTPException(detail={...}) 包成 {"detail": {...}}
    detail = body.get("detail", body)
    assert detail.get("ok") is False
    assert detail.get("error") == "invalid_password"

    # verify 没 token 自然 invalid
    r2 = await client.get("/api/auth/verify")
    assert r2.status_code == 200
    assert r2.json() == {"ok": True, "valid": False, "reason": "missing"}


# ===== 场景 3: expired token → verify valid=False, reason=expired =====
@pytest.mark.asyncio
async def test_verify_expired_token(client, auth_settings):
    secret = auth_settings["secret"]

    # 手工造一个 1 秒前过期的 token
    now = int(time.time())
    expired = jwt.encode(
        {"sub": "viewer", "iat": now - 7200, "exp": now - 3600},  # 1h 前过期
        secret,
        algorithm="HS256",
    )

    r = await client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "valid": False, "reason": "expired"}


# ===== bonus 场景 (不计入 3 场景, 但能跑就 bonus) =====
@pytest.mark.asyncio
async def test_verify_bad_signature(client, auth_settings):
    """用错的 secret 签的 token → reason=bad_signature"""
    bogus = jwt.encode(
        {"sub": "viewer", "iat": int(time.time()), "exp": int(time.time()) + 3600},
        "wrong-secret-xxx",
        algorithm="HS256",
    )
    r = await client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {bogus}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["valid"] is False
    assert body["reason"] in {"bad_signature", "invalid"}


@pytest.mark.asyncio
async def test_verify_malformed_authorization(client):
    r = await client.get("/api/auth/verify", headers={"Authorization": "NotBearer xxx"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "valid": False, "reason": "malformed"}
