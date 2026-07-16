"""AOG API - SCF Web Function 入口

冷启动流程:
1. 读 env (COS_BUCKET / COS_SECRET_*)
2. 从 COS 下载 fts5_index.db 到 /tmp/aog_fts5.db (按需, 启动 fts5 client 时)
3. 手动跑 FastAPI lifespan (建 SQLite / 初始化 FTS5) - 用后台 task
4. 每个 HTTP request → ASGI app 处理 (复用同一 lifespan state)

设计: 单实例常驻 + cold start 接受 30-60s
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 把当前函数根目录加到 sys.path (放第一位, 优先 import 本包的 aog_web)
_FN_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_FN_ROOT))

# 关键: 把 fts5 db 路径指向 /tmp (SCF 只读 /tmp 可写, 个人版 512MB 限制)
os.environ.setdefault("RAG_BACKEND", "fts5")
os.environ.setdefault("FTS5_PATH", "/tmp/aog_fts5.db")
os.environ.setdefault("CHROMA_PATH", "/tmp/chroma")  # 不存在也行
os.environ.setdefault("SQLITE_PATH", "/tmp/aog.db")  # 元数据也放到 /tmp
# 关闭 sync (SCF 是 serverless, 没有持续后台)
os.environ.setdefault("SYNC_ENABLED", "false")

# 日志
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("aog_api_scf")


# FastAPI app (全局单例, 启动时 import)
try:
    from aog_web.main import app as fastapi_app
    logger.info("AOG FastAPI app imported (RAG backend: %s)", os.environ.get("RAG_BACKEND"))
except Exception as e:
    logger.error("Failed to import aog_web.main: %s", e)
    raise


# ===== SCF 冷启动 lifespan 触发 =====
_LIFESPAN_TASK: "asyncio.Task | None" = None
_LIFESPAN_READY = False


async def _run_lifespan_forever():
    """在后台 task 里跑 FastAPI lifespan (启动 → 一直 hold → 退出时 shutdown)
    这样所有 ASGI request 都能访问 app.state.* (settings, sqlite, sync, fts5)
    """
    global _LIFESPAN_READY
    async with fastapi_app.router.lifespan_context(fastapi_app):
        _LIFESPAN_READY = True
        logger.info("FastAPI lifespan started; app.state ready.")
        # 一直 hold, 直到 task 被 cancel
        try:
            await asyncio.Event().wait()  # 永久 sleep
        except asyncio.CancelledError:
            logger.info("FastAPI lifespan shutting down ...")
            raise


def _cold_start_warmup() -> None:
    """SCF 冷启动: 触发 lifespan (下载 fts5 + 建 SQLite/初始化 FTS5)

    启动一个后台 asyncio task 跑 lifespan, 一直 hold 到 SCF 实例被回收.
    """
    global _LIFESPAN_TASK

    if _LIFESPAN_TASK is not None:
        return  # 已经启动

    # 1. 下载 fts5_index.db (在 lifespan 之前, sync)
    if not Path("/tmp/aog_fts5.db").exists():
        try:
            from aog_web.services.storage_cos import download_data_from_cos, is_cos_configured
            if is_cos_configured():
                logger.info("Cold start: downloading fts5_index.db from COS ...")
                download_data_from_cos(anchor=Path("/tmp"), force=False)
                logger.info("Cold start: download done.")
        except Exception as e:
            logger.warning("Cold start download failed: %s (will continue, may be empty)", e)

    # 2. 启动 lifespan 在后台 event loop 里
    # SCF 是单线程, 用一个 daemon thread 跑 asyncio loop
    def _run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # 把 loop 注册到 scf_adapter, 让 ASGI request 能跨线程调用
        try:
            from scf_adapter import set_lifespan_loop
            set_lifespan_loop(loop)
        except Exception:
            pass
        try:
            loop.run_until_complete(_run_lifespan_forever())
        finally:
            loop.close()

    import threading
    t = threading.Thread(target=_run_loop, daemon=True, name="aog-lifespan")
    t.start()
    logger.info("Lifespan thread started.")

    # 等到 _LIFESPAN_READY (最多 60s)
    started = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
    import time
    t0 = time.time()
    while not _LIFESPAN_READY and (time.time() - t0) < 60:
        time.sleep(0.1)
    if _LIFESPAN_READY:
        logger.info("Lifespan ready (took %.1fs)", time.time() - t0)
    else:
        logger.warning("Lifespan not ready after 60s")


# ===== SCF API Gateway handler =====
def main_handler(event, context):
    """SCF HTTP function entry (API Gateway 触发)

    Args:
        event: API Gateway event dict
        context: SCF Context

    Returns:
        API Gateway response dict
    """
    # 冷启动 warmup (下载 + lifespan, 只跑一次)
    _cold_start_warmup()

    # 翻译 API Gateway event → ASGI scope
    from scf_adapter import handle_apigw
    return handle_apigw(fastapi_app, event, context)
