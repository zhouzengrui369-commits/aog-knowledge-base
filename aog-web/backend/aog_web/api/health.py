"""GET /api/health - CONTRACT §2.1"""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from aog_web import __version__

router = APIRouter(tags=["health"])

_START_TIME = time.time()


@router.get("/api/health")
async def health(request: Request) -> dict:
    """健康检查: 返回 status / version / uptime_s"""
    settings = request.app.state.settings
    return {
        "status": "ok",
        "version": __version__,
        "uptime_s": int(time.time() - _START_TIME),
        "llm_mode": "mock" if settings.is_mock_llm else "live",
        "rag_backend": settings.rag_backend,
    }
