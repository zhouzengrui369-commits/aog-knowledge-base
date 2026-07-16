"""CloudBase COS 持久化层 - chroma.sqlite3 + aog.db 上云.

设计:
- 容器冷启动时, 如果本地 ./data/ 空的 (或标记为 "first boot"),
  从 CloudBase COS 下载 chroma/ 整个目录 + aog.db + sync_state.db + index_stats.json
- 本地已有则 skip, 启动加速 (~ 0s)
- 所有凭证 (SecretId/Key/Bucket/Region) 都从环境变量读, 永不 commit
- 上传用 tools/sync_to_cos.py (本地 NJX 跑 build_index 后触发)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ===== COS 凭证 (从 env 读, 默认值仅 dev 用) =====
def _cos_secret_id() -> Optional[str]:
    return os.environ.get("COS_SECRET_ID") or os.environ.get("TENCENTCLOUD_SECRETID")


def _cos_secret_key() -> Optional[str]:
    return os.environ.get("COS_SECRET_KEY") or os.environ.get("TENCENTCLOUD_SECRETKEY")


def _cos_bucket() -> Optional[str]:
    return os.environ.get("COS_BUCKET")


def _cos_region() -> str:
    return os.environ.get("COS_REGION", "ap-shanghai")


# ===== 路径 (相对 backend/ 启动目录的 ./data/) =====
# 注意: 用 anchor_path 参数 (migrate_and_start.py 注入) 兼容
# 本地跑 (./data) / 容器内 (/app/aog-web/backend/data) 两种场景
def _local_data_dir(anchor: Path | None = None) -> Path:
    if anchor is not None:
        return anchor
    # 默认: backend/ 目录下的 data/
    return Path(__file__).resolve().parent.parent.parent / "data"


# ===== 主流程: 下载 =====
def download_data_from_cos(anchor: Path | None = None, force: bool = False) -> bool:
    """从 COS 下载 chroma/ + aog.db + sync_state.db + index_stats.json 到本地 data/.

    Args:
        anchor: 本地 data/ 目录 (None = 自动用 backend/data)
        force: True = 强制重新下载 (即使本地已有)

    Returns:
        True  = 下载了 (或尝试下载)
        False = 本地已有完整数据, skip
    """
    data_dir = _local_data_dir(anchor)
    chroma_dir = data_dir / "chroma"
    chroma_db = chroma_dir / "chroma.sqlite3"
    aog_db = data_dir / "aog.db"

    # 已有数据 (除非 force) → skip
    if not force and chroma_db.exists() and aog_db.exists():
        logger.info("[storage_cos] local data already exists, skip COS download (chroma=%d bytes, aog.db=%d bytes)",
                    chroma_db.stat().st_size, aog_db.stat().st_size)
        return False

    bucket = _cos_bucket()
    secret_id = _cos_secret_id()
    secret_key = _cos_secret_key()
    if not all([bucket, secret_id, secret_key]):
        logger.warning(
            "[storage_cos] COS env not fully set (bucket=%s, id=%s, key=%s); "
            "skip download — assume local has data or dev mode",
            bool(bucket), bool(secret_id), bool(secret_key),
        )
        return False

    # 延迟 import: 避免本地 dev (无 cos sdk 时) 启动失败
    try:
        from qcloud_cos import CosConfig, CosS3Client  # type: ignore
    except ImportError as e:
        import sys
        logger.error("[storage_cos] cos-python-sdk-v5 not installed: %s; sys.path=%s", e, sys.path[:5])
        return False

    region = _cos_region()
    logger.info("[storage_cos] downloading from COS bucket=%s region=%s ...", bucket, region)
    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Scheme="https")
    client = CosS3Client(config)

    # 1) chroma/ 整个目录
    chroma_dir.mkdir(parents=True, exist_ok=True)
    _download_prefix(client, bucket, "chroma/", data_dir)

    # 2) 顶层文件 (aog.db / sync_state.db / index_stats.json)
    for key in ("aog.db", "sync_state.db", "index_stats.json"):
        target = data_dir / key
        if target.exists() and not force:
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            logger.info("[storage_cos] download s3://%s/%s -> %s", bucket, key, target)
            client.download_file(Bucket=bucket, Key=key, DestFilePath=str(target))
        except Exception as e:
            # index_stats.json / sync_state.db 是 optional, 不报错
            logger.info("[storage_cos] skip optional file %s: %s", key, e)

    # 3) FTS5 index (Wave 3 SCF 部署用, 替代 chroma)
    for key in ("fts5_index.db", "chunks_meta.json"):
        target = data_dir / key
        if target.exists() and not force:
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            logger.info("[storage_cos] download s3://%s/%s -> %s", bucket, key, target)
            client.download_file(Bucket=bucket, Key=key, DestFilePath=str(target))
        except Exception as e:
            logger.warning("[storage_cos] skip FTS5 file %s: %s", key, e)

    logger.info("[storage_cos] COS download done (data_dir=%s)", data_dir)
    return True


def _download_prefix(client, bucket: str, prefix: str, data_dir: Path) -> None:
    """下载 COS prefix 下所有对象到 data_dir."""
    marker = ""
    downloaded = 0
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if marker:
            kwargs["Marker"] = marker
        resp = client.list_objects(**kwargs)
        contents = resp.get("Contents", []) or []
        for obj in contents:
            key = obj["Key"]
            # skip directory placeholder (key ends with /)
            if key.endswith("/"):
                continue
            local_path = data_dir / key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                client.download_file(Bucket=bucket, Key=key, DestFilePath=str(local_path))
                downloaded += 1
            except Exception as e:
                logger.warning("[storage_cos] failed to download %s: %s", key, e)
        # 分页
        if resp.get("IsTruncated") == "true":
            marker = resp.get("NextMarker", "")
        else:
            break
    logger.info("[storage_cos] downloaded %d files under %s/", downloaded, prefix)


# ===== 诊断: 检查 COS 是否配齐 =====
def is_cos_configured() -> bool:
    """用于 health 端点 / 启动日志, 标记当前是否启用 COS 持久化."""
    return all([_cos_bucket(), _cos_secret_id(), _cos_secret_key()])


def describe_cos_config() -> dict:
    """返回当前 COS 配置的脱敏描述 (用于 /api/health 暴露)."""
    return {
        "configured": is_cos_configured(),
        "bucket": _cos_bucket(),
        "region": _cos_region(),
        "has_secret_id": bool(_cos_secret_id()),
        "has_secret_key": bool(_cos_secret_key()),
    }
