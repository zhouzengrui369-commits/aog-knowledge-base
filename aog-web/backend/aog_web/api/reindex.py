"""POST /api/reindex + GET /api/reindex/{job_id} - CONTRACT §2.8

v1: 简化 - 只接 job_id, 状态 in-memory dict
- Wave 1 实际重建由 T3 pipeline 处理, 这个端点只标记 + 状态查询
- 生产环境可接 Celery / Arq
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reindex", tags=["reindex"])


class ReindexRequest(BaseModel):
    paths: list[str] | None = None  # None = 全量


# In-memory job store (Wave 1 简化)
_jobs: Dict[str, Dict[str, Any]] = {}


@router.post("")
async def start_reindex(request: Request, body: ReindexRequest | None = None) -> dict:
    """启动重建任务 - 返回 job_id"""
    body = body or ReindexRequest()
    job_id = f"reidx-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "paths": body.paths,
        "started_at": time.time(),
        "error": None,
    }
    logger.info("reindex job queued: %s (paths=%s)", job_id, body.paths)

    # Wave 1 简化: 立即标记 done (实际 T3 pipeline 跑)
    # 真实生产: 启动后台 task
    _jobs[job_id]["status"] = "done"
    _jobs[job_id]["progress"] = 100

    return {"job_id": job_id, "status": _jobs[job_id]["status"]}


@router.get("/{job_id}")
async def get_reindex_status(request: Request, job_id: str) -> dict:
    """查询 job 状态"""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "reindex job not found", "job_id": job_id})
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job["progress"],
        "error": job.get("error"),
    }
