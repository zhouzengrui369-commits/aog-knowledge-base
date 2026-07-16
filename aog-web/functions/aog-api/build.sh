#!/usr/bin/env bash
# build.sh - 把 backend/aog_web/ 子集 copy 到 functions/aog-api/aog_web/
# 用于 SCF 部署: SCF zip 不允许 symlink, 必须物理 copy
# 跑完后再 tcb fn deploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC="$PROJECT_ROOT/backend/aog_web"
DST="$SCRIPT_DIR/aog_web"

echo "[build.sh] src=$SRC"
echo "[build.sh] dst=$DST"

# 清理旧的
rm -rf "$DST"
mkdir -p "$DST"

# 物理 copy (recursive, 不带 __pycache__)
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' "$SRC/" "$DST/"

echo "[build.sh] ✓ aog_web/ copied to $DST"
ls -la "$DST"