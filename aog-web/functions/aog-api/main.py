"""AOG API - SCF Web Function 入口 (stub)

实际启动由 scf_bootstrap 脚本完成 (uvicorn 监听 9000 端口).
这个 main.py 只为满足 cloudbaserc.json 的 handler 引用.
SCF 平台会先调 scf_bootstrap 启动 uvicorn, 然后 HTTP 请求走 9000 端口.
"""
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("aog_api_scf_main")
logger.info("main.py loaded (uvicorn runs from scf_bootstrap)")


def main_handler(event, context):
    """SCF API Gateway handler - 实际不会被调用
    (HTTP 请求由 scf_bootstrap 启动的 uvicorn 在 9000 端口处理)
    """
    logger.warning("main_handler called but uvicorn should be handling this")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"message":"aog-api is running. Use HTTP via 9000 port."}',
        "isBase64Encoded": False,
    }
