#!/usr/bin/env bash
# prepare-scf.sh - SCF 部署准备统一入口 (Owner 7/29 严令 P0-7)
#
# 流程:
#   1. 跑 functions/aog-api/build.sh (copy + compileall + manifest)
#   2. 校验 backend/aog_web vs functions/aog-api/aog_web 一致性
#   3. 输出 SCF 部署命令 (含 APP_COMMIT_SHA)
#
# 不允许直接 tcb fn deploy (Owner 7/29 严令)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== prepare-scf.sh ==="
echo "PROJECT_ROOT=$PROJECT_ROOT"
echo ""

# 1. 跑 build.sh
echo "[1/3] 跑 build.sh ..."
bash "$PROJECT_ROOT/functions/aog-api/build.sh"
echo ""

# 2. 校验一致性 (排除 allowlist)
echo "[2/3] 校验 backend/aog_web vs functions/aog-api/aog_web ..."
python3 - <<PYEOF
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path("$PROJECT_ROOT")
SRC = PROJECT_ROOT / "backend" / "aog_web"
DST = PROJECT_ROOT / "functions" / "aog-api" / "aog_web"
ALLOWLIST_FILE = PROJECT_ROOT / "functions" / "aog-api" / "SCF_ALLOWLIST.txt"

ALLOWLIST = set()
if ALLOWLIST_FILE.exists():
    for line in ALLOWLIST_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ALLOWLIST.add(line)

def _hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def _walk(base: Path):
    out = {}
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(base))
        if "__pycache__" in rel or rel.endswith((".pyc", ".pyo")):
            continue
        if any(rel == a or rel.startswith(a + "/") for a in ALLOWLIST):
            continue
        out[rel] = _hash(p)
    return out

src_hashes = _walk(SRC)
dst_hashes = _walk(DST)

src_only = set(src_hashes) - set(dst_hashes)
dst_only = set(dst_hashes) - set(src_hashes)
diff = [k for k in src_hashes if k in dst_hashes and src_hashes[k] != dst_hashes[k]]

errors = []
if src_only:
    errors.append(f"src-only (missing in dst): {len(src_only)} files, e.g. {list(src_only)[:3]}")
if dst_only:
    errors.append(f"dst-only (extra in dst, not in allowlist): {len(dst_only)} files, e.g. {list(dst_only)[:3]}")
if diff:
    errors.append(f"drift (same path, different hash): {len(diff)} files, e.g. {diff[:3]}")

if errors:
    print("✗ backend/aog_web vs functions/aog-api/aog_web DRIFT:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print(f"✓ {len(src_hashes)} files 一致 (allowlist: {len(ALLOWLIST)} files)")
PYEOF
echo ""

# 3. 输出 SCF 部署命令 (含 APP_COMMIT_SHA)
echo "[3/3] SCF 部署命令 (含 APP_COMMIT_SHA):"
SOURCE_COMMIT="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "  cd $PROJECT_ROOT"
echo "  tcb fn deploy -e APP_COMMIT_SHA=$SOURCE_COMMIT"
echo ""
echo "=== prepare-scf.sh done ==="
