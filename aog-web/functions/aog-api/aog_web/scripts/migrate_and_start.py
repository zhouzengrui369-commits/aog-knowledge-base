"""CloudBase Run 容器启动入口 - COS 预热 + uvicorn.

启动流程:
1. (可选) COS 预热: 容器冷启动时下载 chroma + sqlite 到本地 data/
   - 本地已有 → skip (热启动快)
   - 本地空 + COS 有 → 下载 ~30s
   - COS 未配 (本地 dev) → 警告后继续 (用本地/空 data)
2. uvicorn 启动 FastAPI app, lifespan 接管 (init SQLite/Chroma/sync)
3. SIGTERM graceful shutdown (CloudBase Run 滚动升级)

入口 (Dockerfile ENTRYPOINT):
    python -m aog_web.scripts.migrate_and_start

环境变量:
    PORT                (default 8000)  监听端口, CloudBase Run 自动注入
    COS_BUCKET / COS_REGION / COS_SECRET_ID / COS_SECRET_KEY
                          (optional)    启用 COS 持久化时必填
    COS_FORCE_DOWNLOAD  (default 0)    1 = 强制重新下载 COS (debug 用)

设计原则:
- 本地 dev 不挂 COS: 跑 `uv run uvicorn aog_web.main:app --reload` 即可, 这个脚本不强制
- 容器 prod 必须用这个脚本作为 entrypoint, 走 COS 预热
"""
from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

from aog_web.services.storage_cos import (
    describe_cos_config,
    download_data_from_cos,
    is_cos_configured,
)


def _setup_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


logger = logging.getLogger("aog_web.scripts.migrate_and_start")


def _resolve_data_dir() -> Path:
    """本地 data/ 路径解析.

    优先级:
    1. $AOG_DATA_DIR 环境变量 (覆盖用)
    2. CHROMA_PATH 的父目录 (来自 .env)
    3. backend/data/ 默认值
    """
    if env_dir := os.environ.get("AOG_DATA_DIR"):
        return Path(env_dir).resolve()
    chroma = os.environ.get("CHROMA_PATH", "./data/chroma")
    p = Path(chroma)
    if not p.is_absolute():
        # 相对于 backend/ (cwd 假设是 backend/)
        return (Path.cwd() / p).parent.resolve()
    return p.parent.resolve()


def _warmup_cos(data_dir: Path) -> None:
    """COS 预热 (cold start)."""
    cos_desc = describe_cos_config()
    logger.info("[boot] COS config: %s", cos_desc)

    if not is_cos_configured():
        logger.info("[boot] COS not configured, assume local dev (no download)")
        return

    force = os.environ.get("COS_FORCE_DOWNLOAD", "0") == "1"
    try:
        downloaded = download_data_from_cos(anchor=data_dir, force=force)
        if downloaded:
            logger.info("[boot] COS warmup done, first-boot data ready")
        else:
            logger.info("[boot] local data present, COS warmup skipped (warm start)")
    except Exception as e:
        # COS 失败不能让容器起不来 — 用本地 (空) data 启动, 后续 warmup 人工触发
        logger.exception("[boot] COS warmup FAILED (will start with local/empty data): %s", e)


def main() -> None:
    _setup_logging()
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info("=" * 60)
    logger.info("AOG Web Backend starting (CloudBase Run entry)")
    logger.info("port=%s host=%s cwd=%s", port, host, Path.cwd())
    logger.info("=" * 60)

    # 1. COS 预热
    data_dir = _resolve_data_dir()
    logger.info("[boot] data dir: %s", data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _warmup_cos(data_dir)

    # 2. 启动 uvicorn (接管 lifespan / 路由 / 中间件)
    import uvicorn
    from aog_web.main import app

    # SIGTERM graceful: uvicorn 默认处理, 这里再打一行 log 方便 CloudBase Run 日志排查
    def _sigterm_handler(signum, frame):  # noqa: ARG001
        logger.info("[boot] received SIGTERM (signal=%s), uvicorn will graceful shutdown", signum)

    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (ValueError, OSError):
        # Windows / 某些子线程里不能注册信号 — ignore
        pass

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        # CloudBase Run 反代会读 X-Forwarded-*; 信任一层 (CloudBase Run 内部)
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
