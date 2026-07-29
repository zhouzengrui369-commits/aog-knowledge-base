#!/usr/bin/env bash
# build.sh - 把 backend/aog_web/ 子集 copy 到 functions/aog-api/aog_web/
# 用于 SCF 部署: SCF zip 不允许 symlink, 必须物理 copy
# 跑完后再 tcb fn deploy
#
# ★ P0-7 Stabilization (Owner 7/29 严令): 必须 + 跑 compileall + 显 source commit
#   + 写文件 manifest (含 SHA256) 让 CI 可校验 backend/aog_web vs functions/aog-api/aog_web 一致

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC="$PROJECT_ROOT/backend/aog_web"
DST="$SCRIPT_DIR/aog_web"
MANIFEST="$SCRIPT_DIR/MANIFEST.json"
ALLOWLIST="$SCRIPT_DIR/SCF_ALLOWLIST.txt"

# SCF adapter 允许不同的文件 (这些不算 drift)
cat > "$ALLOWLIST" <<'EOF'
# SCF adapter 允许 drift 的文件 (与 backend/aog_web 不同)
scf_adapter.py
scf_cos.py
scf_bootstrap
EOF

echo "[build.sh] src=$SRC"
echo "[build.sh] dst=$DST"

# 1. 清理旧的
rm -rf "$DST"
mkdir -p "$DST"

# 2. 物理 copy (recursive, 不带 __pycache__ / .pyc / .pyo)
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' "$SRC/" "$DST/"

echo "[build.sh] ✓ aog_web/ copied to $DST"

# 3. ★ P0-7: 跑 compileall 验证 (owner 7/29 严令)
echo "[build.sh] running compileall on $DST ..."
python3 -m compileall -q "$DST" 2>&1 | tail -3 || {
  echo "[build.sh] ✗ compileall failed"
  exit 1
}
echo "[build.sh] ✓ compileall OK"

# 4. ★ P0-7: 输出 source commit (用于 CI 比对)
SOURCE_COMMIT="$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
SOURCE_BRANCH="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
echo "[build.sh] source_commit=$SOURCE_COMMIT"
echo "[build.sh] source_branch=$SOURCE_BRANCH"

# 5. ★ P0-7: 输出文件 manifest (含 SHA256, 排除 allowlist)
echo "[build.sh] writing MANIFEST.json ..."
python3 - <<PYEOF
import hashlib
import json
import os
from pathlib import Path

ALLOWLIST = set(Path("$ALLOWLIST").read_text().splitlines() if Path("$ALLOWLIST").exists() else [])
ALLOWLIST = {x.strip() for x in ALLOWLIST if x.strip() and not x.startswith("#")}

DST = Path("$DST")
files = []
for p in sorted(DST.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(DST)
    rel_str = str(rel)
    if any(rel_str == a or rel_str.startswith(a + "/") for a in ALLOWLIST):
        continue
    # 排除 pycache
    if "__pycache__" in rel_str or rel_str.endswith((".pyc", ".pyo")):
        continue
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    files.append({
        "path": rel_str,
        "size": p.stat().st_size,
        "sha256": h.hexdigest(),
    })

manifest = {
    "source_commit": "$SOURCE_COMMIT",
    "source_branch": "$SOURCE_BRANCH",
    "build_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "file_count": len(files),
    "total_size": sum(f["size"] for f in files),
    "allowlist": sorted(ALLOWLIST),
    "files": files,
}
Path("$MANIFEST").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
print(f"[build.sh] MANIFEST.json: {len(files)} files, {sum(f['size'] for f in files)} bytes")
PYEOF

echo "[build.sh] ✓ done. Next: tcb fn deploy (or use prepare:scf wrapper)"
ls -la "$DST" | head -20
