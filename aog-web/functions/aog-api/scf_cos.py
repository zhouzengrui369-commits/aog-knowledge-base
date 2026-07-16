"""SCF inline COS downloader (无 cos sdk 依赖)

用 httpx + COS V4 sha1 签名. 部署时 vendor/ 没 cos sdk (Linux wheel 缺失),
走 inline 实现.

COS V4 算法 (q-sign-algorithm=sha1):
1. KeyTime = StartTimestamp;EndTimestamp
2. SignKey = HMAC-SHA1(SecretKey, KeyTime)
3. HttpString = Method\n + Uri\n + QueryString\n + HeaderList\n
4. StringToSign = sha1\n + KeyTime\n + sha1(HttpString)\n
5. Signature = HMAC-SHA1(SignKey, StringToSign)
6. Authorization header

参考: https://cloud.tencent.com/document/product/436/7778
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _sign_v4_sha1(
    method: str,
    uri_path: str,
    host: str,
    secret_id: str,
    secret_key: str,
) -> str:
    """返回 Authorization header 值"""
    now = int(time.time())
    key_time = f"{now - 60};{now + 600}"

    # 1) SignKey
    sign_key = hmac.new(secret_key.encode("utf-8"), key_time.encode("utf-8"), hashlib.sha1).hexdigest()

    # 2) HttpString (Method, Uri, QueryString, HeaderList)
    # headers 字典: 按 key 升序
    headers_dict = {"host": host}
    header_list = "\n".join(f"{k}={headers_dict[k]}" for k in sorted(headers_dict.keys())) + "\n"
    http_string = f"{method.lower()}\n{uri_path}\n\n{header_list}"

    # 3) StringToSign
    hashed_http = hashlib.sha1(http_string.encode("utf-8")).hexdigest()
    string_to_sign = f"sha1\n{key_time}\n{hashed_http}\n"

    # 4) Signature
    signature = hmac.new(sign_key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).hexdigest()

    # 5) Authorization
    authorization = (
        f"q-sign-algorithm=sha1&q-ak={secret_id}"
        f"&q-sign-time={key_time}"
        f"&q-key-time={key_time}"
        f"&q-header-list=host"
        f"&q-url-param-list="
        f"&q-signature={signature}"
    )
    return authorization


def download_object(
    bucket: str,
    key: str,
    local_path: Path,
    region: str = "ap-shanghai",
    secret_id: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> bool:
    """下载 COS 对象到本地"""
    secret_id = secret_id or os.environ.get("COS_SECRET_ID", "")
    secret_key = secret_key or os.environ.get("COS_SECRET_KEY", "")
    if not secret_id or not secret_key:
        logger.error("[scf_cos] missing COS_SECRET_ID or COS_SECRET_KEY env")
        return False

    host = f"{bucket}.cos.{region}.myqcloud.com"
    uri_path = "/" + urllib.parse.quote(key, safe="/")
    url = f"https://{host}{uri_path}"
    authorization = _sign_v4_sha1("GET", uri_path, host, secret_id, secret_key)

    logger.info("[scf_cos] GET %s -> %s", url, local_path)
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.get(url, headers={"Authorization": authorization, "Host": host})
            if resp.status_code != 200:
                logger.error("[scf_cos] download failed: HTTP %d, body=%s", resp.status_code, resp.text[:300])
                return False
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(resp.content)
            logger.info("[scf_cos] saved %d bytes to %s", len(resp.content), local_path)
            return True
    except Exception as e:
        logger.error("[scf_cos] download exception: %s", e)
        return False


def download_fts5_data(anchor_dir: Path) -> bool:
    """从 COS 下载 fts5_index.db + chunks_meta.json + aog.db 到 anchor_dir

    Returns: True = 至少一个文件下载成功
    """
    bucket = os.environ.get("COS_BUCKET", "")
    region = os.environ.get("COS_REGION", "ap-shanghai")
    if not bucket:
        logger.warning("[scf_cos] COS_BUCKET not set, skip")
        return False

    success = 0
    for key in ("fts5_index.db", "chunks_meta.json", "aog.db"):
        target = anchor_dir / key
        if target.exists() and target.stat().st_size > 1024:
            logger.info("[scf_cos] %s already exists (%d bytes), skip", key, target.stat().st_size)
            success += 1
            continue
        if download_object(bucket=bucket, key=key, local_path=target, region=region):
            success += 1
    return success > 0
