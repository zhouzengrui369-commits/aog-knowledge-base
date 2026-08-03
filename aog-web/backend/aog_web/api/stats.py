"""Public production statistics sourced from SQLite, never frontend mocks."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from aog_web.services.airlines_client import get_airlines_client
from aog_web.services.production_policy import production_stats
from aog_web.services.sqlite_client import get_sqlite_client

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def get_stats(request: Request) -> dict:
    sqlite = get_sqlite_client()
    airlines = get_airlines_client()
    return await asyncio.to_thread(
        production_stats,
        sqlite.db_path,
        airline_count=airlines.count(),
    )
