"""本地 build_index 完成后, 上传 chroma + sqlite 到 CloudBase COS.

用法 (NJX 在本地 macOS 跑):
    # 1. 先跑 build_index 重建索引
    cd aog-web
    uv run --project pipeline python -m pipeline.build_index

    # 2. 然后上传到 COS (用 env var 提供凭证, 永远不要 commit 真实 SecretId/Key)
    cd aog-web
    export COS_SECRET_ID="AKIDxxx"
    export COS_SECRET_KEY="xxx"
    export COS_BUCKET="aog-prod-data-7gxxxxxxx"
    export COS_REGION="ap-shanghai"
    uv run --project backend python tools/sync_to_cos.py

    # 可选: 强制重新上传 (即使 mtime/size 一致)
    uv run --project backend python tools/sync_to_cos.py --force

触发效果:
    下次 CloudBase Run 容器冷启动时, migrate_and_start.py 会检测到本地
    data/ 缺失, 自动从 COS 下载最新数据 (约 30s 一次冷启动).

注意:
    - 仅上传 backend/data/ 下的 chroma/, aog.db, sync_state.db, index_stats.json
    - 不会触碰 AOG知识库/ 源数据 (pipeline 只读)
    - 不会触碰 backend 代码 / .env / tests
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


# ===== 路径定位 (相对 tools/ 的位置) =====
TOOLS_DIR = Path(__file__).resolve().parent
AOG_WEB_DIR = TOOLS_DIR.parent
BACKEND_DATA_DIR = AOG_WEB_DIR / "backend" / "data"

# 待上传的关键文件/目录 (相对 backend/data/)
UPLOAD_TARGETS: tuple[str, ...] = (
    "chroma",           # 整个目录 (含 chroma.sqlite3 + sqlite3-wal/-shm)
    "aog.db",           # SQLite 元数据
    "sync_state.db",    # 增量同步状态 (mtime + size hash)
    "index_stats.json", # build_index 统计 (optional, debug 用)
)


# ===== 凭证 (全部从 env 读) =====
def _env_or_die(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: env {name} is required (export {name}=...)", file=sys.stderr)
        sys.exit(2)
    return val


def _cos_client():
    """构造 COS S3 client (凭证全部 env, 永不 hardcode)."""
    try:
        from qcloud_cos import CosConfig, CosS3Client  # type: ignore
    except ImportError:
        print("ERROR: cos-python-sdk-v5 not installed in this env.", file=sys.stderr)
        print("       pip install cos-python-sdk-v5   # 或: uv add --project backend cos-python-sdk-v5", file=sys.stderr)
        sys.exit(3)

    cfg = CosConfig(
        Region=os.environ.get("COS_REGION", "ap-shanghai"),
        SecretId=_env_or_die("COS_SECRET_ID"),
        SecretKey=_env_or_die("COS_SECRET_KEY"),
        Scheme="https",
    )
    return CosS3Client(cfg)


def _upload_file(client, bucket: str, key: str, local: Path, force: bool) -> str:
    """上传单个文件, 简单 size/mtime 对比 (force=True 时跳过)."""
    if not local.exists():
        return f"SKIP (missing): {key}"

    # 简化对比: 如果 COS 上有同名且 size 一致, 跳过 (除非 force)
    if not force:
        try:
            head = client.head_object(Bucket=bucket, Key=key)
            remote_size = int(head.get("Content-Length", -1))
            if remote_size == local.stat().st_size:
                return f"UNCHANGED ({local.stat().st_size} bytes): {key}"
        except Exception:
            # 对象不存在 (head 404) — 走上传
            pass

    client.upload_file(Bucket=bucket, Key=key, LocalFilePath=str(local))
    return f"UPLOADED ({local.stat().st_size} bytes): {key}"


def _upload_dir_recursive(client, bucket: str, prefix: str, local_dir: Path, force: bool) -> list[str]:
    """递归上传目录下所有文件, key 形如 prefix/relpath."""
    out: list[str] = []
    for p in sorted(local_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(local_dir)
        key = f"{prefix.rstrip('/')}/{rel.as_posix()}"
        out.append(_upload_file(client, bucket, key, p, force))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload backend/data/{chroma, aog.db, sync_state.db, index_stats.json} to CloudBase COS",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=BACKEND_DATA_DIR,
        help=f"local backend data dir (default: {BACKEND_DATA_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="force re-upload even when size matches",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be uploaded without actually uploading",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    log = logging.getLogger("sync_to_cos")

    data_dir: Path = args.data_dir.resolve()
    if not data_dir.is_dir():
        log.error("data dir not found: %s", data_dir)
        return 4

    bucket = _env_or_die("COS_BUCKET")
    log.info("data dir: %s", data_dir)
    log.info("target bucket: %s (region=%s)", bucket, os.environ.get("COS_REGION", "ap-shanghai"))

    if args.dry_run:
        log.info("DRY-RUN mode: would upload:")
        for target in UPLOAD_TARGETS:
            local = data_dir / target
            if local.is_dir():
                for p in sorted(local.rglob("*")):
                    if p.is_file():
                        rel = p.relative_to(data_dir).as_posix()
                        log.info("  - s3://%s/%s  (size=%d)", bucket, rel, p.stat().st_size)
            elif local.is_file():
                rel = local.relative_to(data_dir).as_posix()
                log.info("  - s3://%s/%s  (size=%d)", bucket, rel, local.stat().st_size)
            else:
                log.info("  - SKIP (missing): %s", local)
        return 0

    client = _cos_client()
    log.info("uploading ...")
    n_uploaded = n_skipped = 0
    for target in UPLOAD_TARGETS:
        local = data_dir / target
        if local.is_dir():
            results = _upload_dir_recursive(client, bucket, target, local, args.force)
        elif local.is_file():
            results = [_upload_file(client, bucket, target, local, args.force)]
        else:
            log.warning("target missing locally: %s", local)
            continue
        for line in results:
            log.info("  %s", line)
            if line.startswith("UPLOADED"):
                n_uploaded += 1
            else:
                n_skipped += 1

    log.info("done. uploaded=%d, skipped/unchanged=%d", n_uploaded, n_skipped)
    log.info("next step: 重启 CloudBase Run 容器 (或在控制台 '重启实例'), 触发冷启动从 COS 拉数据")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
