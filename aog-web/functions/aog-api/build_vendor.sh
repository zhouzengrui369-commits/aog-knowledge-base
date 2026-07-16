#!/bin/bash
# AOG API - SCF 部署前置: 装 vendor deps (Linux cp311 x86_64) + copy aog_web/
# 必须在 tcb fn deploy 前跑, 跟 build.sh 串行:
#   1. bash build.sh        # copy aog_web/
#   2. bash build_vendor.sh  # 装 Linux deps 到 vendor/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENDOR="$SCRIPT_DIR/vendor"
REQS="$SCRIPT_DIR/requirements.txt"
PYTHON="${PROJECT_ROOT}/backend/.venv/bin/python"
UV="${HOME}/.local/bin/uv"

echo "[build_vendor.sh] project_root=$PROJECT_ROOT"
echo "[build_vendor.sh] target=$VENDOR"
echo "[build_vendor.sh] requirements=$REQS"

# 1) 装 requirements.txt 全部依赖 (Linux cp311 x86_64 wheel)
if [ ! -d "$VENDOR" ] || [ ! -f "$VENDOR/six.py" ]; then
    echo "[build_vendor.sh] installing deps for Linux cp311 x86_64 ..."
    rm -rf "$VENDOR"
    "$UV" pip install --target "$VENDOR" -r "$REQS" \
        --python-version 3.11 --python-platform x86_64-unknown-linux-gnu \
        2>&1 | tail -5
    # 装上 qcloud_cos (cos-python-sdk-v5) - 没 Linux wheel, 直接从本地 venv 复制
    SITE_PACKAGES="$(dirname "$PYTHON")/../lib/python3.12/site-packages"
    for pkg in qcloud_cos cos_python_sdk_v5-1.9.44.dist-info crcmod crcmod-1.7.dist-info \
                requests requests-2.32.4.dist-info urllib3 urllib3-2.5.0.dist-info \
                charset_normalizer charset_normalizer-3.4.2.dist-info \
                idna idna-3.10.dist-info certifi certifi-2025.6.15.dist-info; do
        if [ -d "$SITE_PACKAGES/$pkg" ] && [ ! -d "$VENDOR/$pkg" ]; then
            cp -r "$SITE_PACKAGES/$pkg" "$VENDOR/$pkg"
        fi
    done
    echo "[build_vendor.sh] ✓ vendor installed"
fi

# 2) 装 six (cos sdk 隐式依赖, FTS5 脚本安装会跳)
"$UV" pip install --target "$VENDOR" six \
    --python-version 3.11 --python-platform x86_64-unknown-linux-gnu 2>&1 | tail -2

# 3) 删 .pyc / __pycache__
find "$VENDOR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$VENDOR" -name "*.pyc" -delete 2>/dev/null || true
find "$VENDOR" -name "*.so" -path "*/mypyc/*" -delete 2>/dev/null || true

# 4) 关键 size
echo "[build_vendor.sh] vendor size: $(du -sh "$VENDOR" | cut -f1)"
echo "[build_vendor.sh] qcloud_cos: $(ls "$VENDOR/qcloud_cos" 2>/dev/null | wc -l) files"
echo "[build_vendor.sh] six.py: $(ls -la "$VENDOR/six.py" 2>/dev/null)"
echo "[build_vendor.sh] ✓ done"
