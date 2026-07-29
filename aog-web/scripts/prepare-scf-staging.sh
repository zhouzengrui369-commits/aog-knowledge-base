#!/usr/bin/env bash
# prepare-scf-staging.sh — staging SCF function package 准备 (NJX 7/29 严令)
#
# 跟 prepare-scf.sh 平行, 区别:
#   - 输出到 functions/aog-api-staging/ (独立 staging 函数, 跟 production 函数隔离)
#   - 启动时 denylist check: 脚本自身 + 配置文件不引用 production 4 项
#   - 不执行任何云端写操作 (仅本地 package/compile/drift/manifest/preflight)
#
# NJX 7/29 严令: staging 严禁触碰 production 资源
#   DENYLIST_REGEX: production 4 项从 cloudbaserc.production.json 读, 不在脚本里 hardcode
#   (见 _denylist_4_keys 字段, 严禁脚本自杀)
#
# CI 验证: bash scripts/prepare-scf-staging.sh --preflight 应 exit 0
# 部署验证: ALLOW_STAGING_DEPLOY=1 bash scripts/deploy-staging.sh 应成功

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AOG_WEB="$REPO_ROOT/aog-web"
FUNCTIONS_DIR="$AOG_WEB/functions/aog-api-staging"
SOURCE_COMMIT="$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo unknown)"
SOURCE_BRANCH="$(cd "$REPO_ROOT" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# ====== Denylist: production 4 项从 cloudbaserc.production.json 读, 不在脚本里 hardcode ======
# 用独立 denylist_check.py (从 production rc 读) 严格检查, 避免脚本自杀

# ====== Preflight: 用独立 denylist_check.py 严格检查 ======
# denylist 从 cloudbaserc.production.json 读, 不在脚本里硬编码 (避免自杀)
preflight() {
    local error=0
    echo "[staging-preflight] 检查 staging 脚本 + 配置文件不含 production denylist..."

    local denylist_py="$AOG_WEB/scripts/denylist_check.py"
    if [ ! -f "$denylist_py" ]; then
        echo "  ✗ FAIL: $denylist_py 不存在" >&2
        return 1
    fi

    # 1. 本脚本自身 (denylist_check.py 自动排除 # 注释 + 占位符行)
    if ! python3 "$denylist_py" "$0" >/dev/null 2>&1; then
        echo "  ✗ FAIL: $0 含 production denylist 字符串" >&2
        python3 "$denylist_py" "$0" | head -3 >&2
        error=1
    else
        echo "  ✓ $0 (0 production 命中)"
    fi

    # 2. cloudbaserc.staging.json
    local staging_rc="$REPO_ROOT/cloudbaserc.staging.json"
    if [ -f "$staging_rc" ]; then
        if ! python3 "$denylist_py" "$staging_rc" >/dev/null 2>&1; then
            echo "  ✗ FAIL: $staging_rc 含 production denylist" >&2
            python3 "$denylist_py" "$staging_rc" | head -3 >&2
            error=1
        else
            echo "  ✓ $staging_rc (0 production 命中)"
        fi
    fi

    # 3. .env.staging.example 占位符 (denylist_check.py 自动识别 xxx-STAGING 占位符)
    local env_staging="$REPO_ROOT/.env.staging.example"
    if [ -f "$env_staging" ]; then
        if ! python3 "$denylist_py" "$env_staging" >/dev/null 2>&1; then
            echo "  ✗ FAIL: $env_staging 含 production 凭据 / envId / bucket" >&2
            python3 "$denylist_py" "$env_staging" | head -3 >&2
            error=1
        else
            echo "  ✓ $env_staging (0 真 production 凭据)"
        fi
    fi

    if [ $error -eq 0 ]; then
        echo "  ✓ staging denylist check: 全部 0 命中"
    else
        echo "  ✗ staging denylist check: 有 production 引用, 阻断"
    fi
    return $error
}

# ====== Package: backend → functions/aog-api-staging/aog_web/ ======
package() {
    echo "[staging-package] 复制 backend → $FUNCTIONS_DIR/aog_web/"

    if [ -d "$FUNCTIONS_DIR/aog_web" ]; then
        rm -rf "$FUNCTIONS_DIR/aog_web"
    fi
    mkdir -p "$FUNCTIONS_DIR"

    # 复制 backend/aog_web/ → staging 函数包
    cp -R "$AOG_WEB/backend/aog_web/." "$FUNCTIONS_DIR/aog_web/"
    # 排除 __pycache__
    find "$FUNCTIONS_DIR/aog_web" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

    echo "[staging-package] ✓ aog_web/ copied to $FUNCTIONS_DIR/aog_web"
}

# ====== Compile: compileall 验证 ======
compile() {
    echo "[staging-compile] running compileall on $FUNCTIONS_DIR/aog_web"
    python -m compileall -q "$FUNCTIONS_DIR/aog_web" 2>&1 | tail -5 || {
        echo "  ✗ compileall FAIL" >&2
        return 1
    }
    echo "[staging-compile] ✓ compileall OK"
}

# ====== Drift: backend vs staging 函数包一致 (排除 __pycache__ 跨 python 版本) ======
drift() {
    echo "[staging-drift] 校验 backend/aog_web vs $FUNCTIONS_DIR/aog_web 一致"
    # 排除 __pycache__ (.pyc 跨 python 版本不一致, e.g. cpython-312 vs cpython-314)
    if ! diff -r --brief --exclude='__pycache__' "$AOG_WEB/backend/aog_web" "$FUNCTIONS_DIR/aog_web" > /tmp/staging-drift.log 2>&1; then
        echo "  ✗ drift 不一致:" >&2
        cat /tmp/staging-drift.log >&2
        return 1
    fi
    echo "[staging-drift] ✓ 0 drift (排除 __pycache__)"
}

# ====== Manifest: 写 staging MANIFEST.json ======
manifest() {
    echo "[staging-manifest] 写 $FUNCTIONS_DIR/MANIFEST.json"
    python -c "
import hashlib, json, os
from pathlib import Path
root = Path('$FUNCTIONS_DIR')
files = sorted([p for p in root.rglob('*') if p.is_file() and '__pycache__' not in str(p)])
total_size = sum(p.stat().st_size for p in files)
# 从 ops/production-resource-denylist.json 读 production 4 项 (denylist reference)
prod_rc = Path('$REPO_ROOT/ops/production-resource-denylist.json')
prod = json.loads(prod_rc.read_text()) if prod_rc.exists() else {}
denied = {
    'envId': prod.get('envId', ''),
    'function_name': prod.get('function', {}).get('name', ''),
    'bucket': prod.get('storage', {}).get('bucket', ''),
    'domain': prod.get('hosting', {}).get('domain', ''),
}
m = {
    'environment': 'staging',
    'source_commit': '$SOURCE_COMMIT',
    'source_branch': '$SOURCE_BRANCH',
    'build_time': '$TIMESTAMP',
    'file_count': len(files),
    'total_size': total_size,
    'isolated_from_production': True,
    'denylist_checked': True,
    'function_name': 'aog-api-staging',
    'production_resources_denied': denied,  # 仅作 reference, 部署到 staging 时 verify
}
(Path('$FUNCTIONS_DIR') / 'MANIFEST.json').write_text(json.dumps(m, indent=2, ensure_ascii=False))
print(f\"  ✓ MANIFEST.json: {m['file_count']} files, {m['total_size']} bytes\")
print(f\"  ✓ environment=staging, isolated_from_production=True\")
print(f\"  ✓ production_resources_denied (4 keys): 部署时 verify 不引用\")
"
}

# ====== Main ======
mode="${1:-all}"

if [ "$mode" = "--preflight" ]; then
    preflight
    exit $?
fi

if [ "$mode" = "--help" ] || [ "$mode" = "-h" ]; then
    cat <<'EOF'
用法:
  bash scripts/prepare-scf-staging.sh           # full package + compile + drift + manifest
  bash scripts/prepare-scf-staging.sh --preflight   # 仅 denylist check

严禁引用 production 资源 (denylist 从 cloudbaserc.production.json 读)
EOF
    exit 0
fi

echo "=== prepare-scf-staging.sh (NJX 7/29 严令) ==="
echo "source_commit=$SOURCE_COMMIT"
echo "source_branch=$SOURCE_BRANCH"
echo "staging_dir=$FUNCTIONS_DIR"
echo

echo "[1/4] denylist preflight..."
preflight
echo
echo "[2/4] package..."
package
echo
echo "[3/4] compile..."
compile
echo
echo "[4/4] drift check..."
drift
echo
echo "MANIFEST:"
manifest
echo
echo "=== done. Next: NJX 设 ALLOW_STAGING_DEPLOY=1 bash scripts/deploy-staging.sh ==="
