"""SCF API Gateway event → ASGI scope 适配器

实现: 把 API Gateway v2 (HTTP) event 翻译成 ASGI 3.0 scope,
然后调 FastAPI app, 把 response 再翻回 API Gateway response.

支持: API Gateway v2 (默认), 也兼容 v1 event
"""
from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ===== API Gateway v2 (HTTP) event → ASGI scope =====
def _apigw_v2_to_scope(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """API Gateway v2 (HTTP) 格式

    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/api/health",
        "rawQueryString": "q=hello",
        "headers": {"host": "...", "content-type": "application/json"},
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/api/health",
                "protocol": "HTTP/1.1",
                "sourceIp": "1.2.3.4",
                "userAgent": "..."
            },
            "stage": "$default"
        },
        "body": "...",  # base64 if isBase64Encoded
        "isBase64Encoded": False
    }
    """
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    # API Gateway 已 strip /api 前缀 (--path /api 配的), 补回 /api
    # 因为 FastAPI 路由是 /api/health, /api/cities, /api/chat 等
    if not path.startswith("/api") and path != "/api":
        path = "/api" + path if path != "/" else "/api"
    raw_qs = event.get("rawQueryString", "")
    headers_raw = event.get("headers", {}) or {}
    body_str = event.get("body", "") or ""
    is_b64 = event.get("isBase64Encoded", False)

    # headers → list of tuples (lowercase key, value)
    headers: List[Tuple[bytes, bytes]] = []
    for k, v in headers_raw.items():
        if v is None:
            continue
        try:
            headers.append((k.lower().encode("latin-1"), str(v).encode("latin-1")))
        except Exception:
            pass

    # query string
    query_string = raw_qs.encode("latin-1") if raw_qs else b""

    # body
    if body_str:
        if is_b64:
            try:
                body = base64.b64decode(body_str)
            except Exception:
                body = body_str.encode("utf-8", errors="replace")
        else:
            body = body_str.encode("utf-8", errors="replace")
    else:
        body = b""

    # server name from host header
    server_name = headers_raw.get("host", "scf.tencentcloud.com").split(":")[0]
    if "," in server_name:
        server_name = server_name.split(",")[0].strip()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("utf-8"),  # v8: 兼容中文 city code (X-西安 等)
        "query_string": query_string,
        "headers": headers,
        "server": (server_name, 443),
        "client": ("0.0.0.0", 0),
        "root_path": "",
        "extensions": {
            "http": {
                "request": {},
            },
        },
    }
    return scope, body


def _apigw_v1_to_scope(event: Dict[str, Any], context: Any) -> Tuple[Dict[str, Any], bytes]:
    """API Gateway v1 (REST) 格式 (兼容)

    event = {
        "httpMethod": "POST",
        "path": "/api/chat",
        "queryStringParameters": {"q": "..."},
        "headers": {...},
        "body": "...",
        "isBase64Encoded": False
    }
    """
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    # API Gateway 已 strip /api 前缀, 补回
    if not path.startswith("/api") and path != "/api":
        path = "/api" + path if path != "/" else "/api"
    qs_params = event.get("queryStringParameters") or {}
    raw_qs = "&".join(f"{k}={v}" for k, v in qs_params.items())
    headers_raw = event.get("headers", {}) or {}
    body_str = event.get("body", "") or ""
    is_b64 = event.get("isBase64Encoded", False)

    # 兼容 multiValueHeaders
    mv_headers = event.get("multiValueHeaders") or {}
    for k, vs in mv_headers.items():
        if k not in headers_raw and vs:
            headers_raw[k] = vs[0]

    headers: List[Tuple[bytes, bytes]] = []
    for k, v in headers_raw.items():
        if v is None:
            continue
        try:
            headers.append((k.lower().encode("latin-1"), str(v).encode("latin-1")))
        except Exception:
            pass

    query_string = raw_qs.encode("latin-1") if raw_qs else b""

    if body_str:
        if is_b64:
            try:
                body = base64.b64decode(body_str)
            except Exception:
                body = body_str.encode("utf-8", errors="replace")
        else:
            body = body_str.encode("utf-8", errors="replace")
    else:
        body = b""

    server_name = headers_raw.get("Host", headers_raw.get("host", "scf.tencentcloud.com")).split(":")[0]
    if "," in server_name:
        server_name = server_name.split(",")[0].strip()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("utf-8"),  # v8: 兼容中文 city code (X-西安 等)
        "query_string": query_string,
        "headers": headers,
        "server": (server_name, 443),
        "client": ("0.0.0.0", 0),
        "root_path": "",
        "extensions": {"http": {"request": {}}},
    }
    return scope, body


# ===== ASGI response 收集 =====
class _ResponseCollector:
    """收集 ASGI app 的 send() 调用, 拼出 API Gateway response"""

    def __init__(self):
        self.status_code: int = 200
        self.headers: List[Tuple[str, str]] = []
        self.body: io.BytesIO = io.BytesIO()

    async def __call__(self, message: Dict[str, Any]) -> None:
        mtype = message["type"]
        if mtype == "http.response.start":
            self.status_code = message["status"]
            for k, v in message.get("headers", []):
                try:
                    self.headers.append((k.decode("latin-1"), v.decode("latin-1")))
                except Exception:
                    pass
        elif mtype == "http.response.body":
            self.body.write(message.get("body", b""))


async def _call_asgi(app, scope: Dict[str, Any], body: bytes) -> _ResponseCollector:
    """调一次 ASGI app"""
    collector = _ResponseCollector()
    receive_q: List[Dict[str, Any]] = [{
        "type": "http.request",
        "body": body,
        "more_body": False,
    }]

    async def receive():
        if receive_q:
            return receive_q.pop(0)
        return {"type": "http.disconnect"}

    await app(scope, receive, collector)
    return collector


# ===== 翻 ASGI response → API Gateway response =====
def _to_apigw_response(collector: _ResponseCollector) -> Dict[str, Any]:
    """ASGI response → API Gateway v2 dict"""
    body_bytes = collector.body.getvalue()
    headers_out: Dict[str, str] = {}
    for k, v in collector.headers:
        # 跳过 hop-by-hop
        if k.lower() in {"content-length", "transfer-encoding", "connection"}:
            continue
        # 取最后一次 (避免重复 key)
        headers_out[k] = v
    if "Content-Type" not in headers_out and "content-type" not in headers_out:
        # 默认
        ct = "text/plain"
        try:
            body_text = body_bytes.decode("utf-8", errors="replace").strip()
            if body_text.startswith("{") or body_text.startswith("["):
                ct = "application/json"
        except Exception:
            pass
        headers_out["Content-Type"] = ct
    return {
        "statusCode": collector.status_code,
        "headers": headers_out,
        "body": body_bytes.decode("utf-8", errors="replace"),
        "isBase64Encoded": False,
    }


# ===== 主入口 =====
def handle_apigw(app, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """SCF API Gateway event → ASGI app → response

    支持 v1 + v2 event 自动检测

    用 main.py 启动的 lifespan event loop 跑 ASGI (共享 app.state.*)
    """
    import asyncio
    import threading

    # 检测 event 版本
    if "httpMethod" in event and "version" not in event:
        scope, body = _apigw_v1_to_scope(event, context)
    elif event.get("version") == "2.0" or "requestContext" in event and "http" in event.get("requestContext", {}):
        scope, body = _apigw_v2_to_scope(event, context)
    else:
        # 兜底当 v1 处理
        scope, body = _apigw_v1_to_scope(event, context)

    logger.info("ASGI: %s %s (body=%d bytes)", scope["method"], scope["path"], len(body))

    # 拿到 main.py 启动的 lifespan event loop (单线程 serverless, 但 lifespan 用独立 thread)
    lifespan_loop = getattr(handle_apigw, "_lifespan_loop", None)
    if lifespan_loop is None or not lifespan_loop.is_running():
        # 没有 lifespan loop → 跑同步 fallback (cold start 竞态或单次调用)
        try:
            new_loop = asyncio.new_event_loop()
            collector = new_loop.run_until_complete(_call_asgi(app, scope, body))
            new_loop.close()
        except Exception as e:
            logger.error("ASGI call failed (no lifespan loop): %s", e)
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "internal", "message": str(e)[:200]}),
                "isBase64Encoded": False,
            }
    else:
        # 用 lifespan 的 event loop (用 run_coroutine_threadsafe 跨线程调度)
        import concurrent.futures
        try:
            future = asyncio.run_coroutine_threadsafe(_call_asgi(app, scope, body), lifespan_loop)
            collector = future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            logger.error("ASGI call timeout (30s)")
            return {
                "statusCode": 504,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "timeout"}),
                "isBase64Encoded": False,
            }
        except Exception as e:
            logger.error("ASGI call failed (via lifespan loop): %s", e)
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "internal", "message": str(e)[:200]}),
                "isBase64Encoded": False,
            }

    resp = _to_apigw_response(collector)
    logger.info("Response: %d (body=%d bytes)", resp["statusCode"], len(resp["body"]))
    return resp


def set_lifespan_loop(loop) -> None:
    """main.py 在启动 lifespan 时注册 loop, scf_adapter 共享"""
    handle_apigw._lifespan_loop = loop  # type: ignore[attr-defined]
