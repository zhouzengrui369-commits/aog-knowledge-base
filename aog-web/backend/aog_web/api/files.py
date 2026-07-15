"""GET /files/{relative_path} - CONTRACT §2.10

代理 RAW/ 和 AOG知识库/ 下的文件下载
- 限缩到允许根目录 (防 path traversal)
- 后端代理, 不暴露绝对路径
"""
from __future__ import annotations

import logging
import urllib.parse
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from aog_web.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


def _resolve_allowed_roots() -> List[Path]:
    """允许的文件根目录 (白名单)"""
    s = get_settings()
    roots: List[Path] = []
    if s.knowledge_base_path.exists():
        roots.append(s.knowledge_base_path.resolve())
    if s.raw_path.exists():
        roots.append(s.raw_path.resolve())
    return roots


@router.get("/{relative_path:path}")
async def get_file(request: Request, relative_path: str) -> FileResponse:
    """下载代理 - 限制在白名单根目录"""
    # URL decode
    try:
        decoded = urllib.parse.unquote(relative_path, encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail={"error": "invalid path encoding"})

    allowed_roots = _resolve_allowed_roots()
    if not allowed_roots:
        raise HTTPException(status_code=503, detail={"error": "no file roots configured"})

    # 遍历每个 root 找文件
    for root in allowed_roots:
        candidate = (root / decoded).resolve()
        # 防 path traversal: 必须以 root 为前缀
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return FileResponse(
                path=str(candidate),
                filename=candidate.name,
                media_type="application/octet-stream",
            )

    raise HTTPException(status_code=404, detail={"error": "file not found", "path": decoded})
