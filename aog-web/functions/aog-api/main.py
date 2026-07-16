"""AOG API - SCF Web Function 入口 (内联 ASGI handler + lazy lifespan)

简化版: 第一次 main_handler 调用时同步跑 lifespan (包括 COS 下载)
后续调用直接走 FastAPI.

vendor/ 在 zip 根目录手动加到 sys.path.
"""
import json
import logging
import os
import sys
import threading
from pathlib import Path

# 1) vendor path
_FN_ROOT = Path(__file__).resolve().parent
_VENDOR = _FN_ROOT / "vendor"
if _VENDOR.exists():
    sys.path.insert(0, str(_VENDOR))
sys.path.insert(0, str(_FN_ROOT))

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("aog_api_scf_main")
logger.info("main.py loaded, sys.path[:5]=%s", sys.path[:5])

# 2) import FastAPI app
try:
    from aog_web.main import app as fastapi_app
    from scf_adapter import handle_apigw
    logger.info("aog_web.main + scf_adapter import OK")
except Exception as e:
    logger.exception("import FAILED: %s", e)
    raise


# 3) 同步跑 lifespan (一次), 用 lock + flag 防止并发
_lifespan_lock = threading.Lock()
_lifespan_done = False


def _ensure_lifespan():
    """同步跑 FastAPI lifespan startup (app.state.* init + COS download)"""
    global _lifespan_done
    if _lifespan_done:
        return
    with _lifespan_lock:
        if _lifespan_done:
            return
        logger.info("running FastAPI lifespan startup (first call) ...")
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            cm = fastapi_app.router.lifespan_context(fastapi_app)
            loop.run_until_complete(cm.__aenter__())
            logger.info("lifespan startup done")
            # 把 loop 留着 (close 会在 process exit 时自动)
            _lifespan_loop = loop
            _lifespan_done = True
        except Exception as e:
            logger.exception("lifespan startup FAILED: %s", e)
            try:
                loop.close()
            except Exception:
                pass
            raise


# 4) main_handler
def main_handler(event, context):
    """SCF API Gateway event handler."""
    path_keys = ['path', 'rawPath', 'httpMethod', 'version', 'routeKey']
    dbg = {k: event.get(k) for k in path_keys if k in event}
    logger.info("event: %s", dbg)

    # 首次调用跑 lifespan
    try:
        _ensure_lifespan()
    except Exception as e:
        return {
            "statusCode": 503,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "lifespan failed", "message": str(e)[:200]}),
            "isBase64Encoded": False,
        }

    try:
        return handle_apigw(fastapi_app, event, context)
    except Exception as e:
        logger.exception("handle_apigw failed: %s", e)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": f'{{"error":"{e}"}}',
            "isBase64Encoded": False,
        }
