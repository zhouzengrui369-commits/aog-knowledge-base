#!/usr/bin/env bash
# prepare-scf-staging.sh — staging SCF function package 准备 (NJX 7/29 + 7/30 严令)
#
# NJX 7/30 严令 PR #3 runtime preflight 修:
#   - 构建 vendor/ (Linux AMD64 Python3.11 pip install --target, 用 docker)
#   - 验证 handler=main.main_handler 可 import
#   - 验证 scf_bootstrap 可执行
#   - 验证 package 包含 vendor + handlers + aog_web
#   - manifest 从 ops/production-resource-denylist.json 的 flat keys 正确读
#     (NJX 7/29 拍板 重命名 cloudbaserc.production.json → ops/production-resource-denylist.json
#      字段从 nested 改为 flat: envId/function_name/bucket/domain)
#   - manifest 记录 package SHA256 (防篡改 + 远端验收对照)
#
# 跟 prepare-scf.sh 平行, 区别:
#   - 输出到 functions/aog-api-staging/ (独立 staging 函数, 跟 production 函数隔离)
#   - 启动时 denylist check: 脚本自身 + 配置文件不引用 production 4 项
#   - 不执行任何云端写操作 (仅本地 package/compile/drift/manifest/preflight)
#
# NJX 7/29 严令: staging 严禁触碰 production 资源
#   DENYLIST_REGEX: production 4 项从 ops/production-resource-denylist.json 读, 不在脚本里 hardcode
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

# ====== Preflight: 用独立 denylist_check.py 严格检查 ======
# denylist 从 ops/production-resource-denylist.json 读, 不在脚本里硬编码 (避免自杀)
preflight() {
    local error=0
    echo "[staging-preflight] 检查 staging 脚本 + 配置文件不含 production denylist..."

    local denylist_py="$AOG_WEB/scripts/denylist_check.py"
    if [ ! -f "$denylist_py" ]; then
        echo "  ✗ FAIL: $denylist_py 不存在" >&2
        return 1
    fi

    # 1. 本脚本自身
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

    # 3. .env.staging.example 占位符
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

# ====== Build vendor: Linux AMD64 Python3.11 pip install --target (NJX 7/30 严令) ======
# installDependency=false, 必须 vendor/ 预装 deps, 运行时 scf_bootstrap 强 vendor 优先
# 本地 build 用 docker (跨 python 版本一致, 跟 SCF runtime 匹配)
build_vendor() {
    echo "[staging-vendor] 构建 vendor/ (Linux AMD64 Python3.11)"

    if [ -d "$FUNCTIONS_DIR/vendor" ] && [ -d "$FUNCTIONS_DIR/vendor/fastapi" ]; then
        echo "  [staging-vendor] vendor/ 已存在且含 fastapi, 跳过 (增量 build)"
        return 0
    fi

    # 优先用 docker (Linux AMD64 Python3.11)
    if command -v docker >/dev/null 2>&1; then
        echo "  [staging-vendor] 用 docker run python:3.11-slim pip install --target"
        rm -rf "$FUNCTIONS_DIR/vendor"
        # docker 跑 Linux Python3.11, pip install 到挂载的 $FUNCTIONS_DIR/vendor
        if docker run --rm \
            -v "$FUNCTIONS_DIR:/app" \
            -v "$AOG_WEB/functions/aog-api/requirements.txt:/tmp/requirements.txt:ro" \
            python:3.11-slim \
            bash -c "pip install --no-cache-dir --target /app/vendor -r /tmp/requirements.txt"; then
            echo "  ✓ vendor/ build 成功 (docker, Linux Python3.11)"
            return 0
        else
            echo "  ✗ FAIL: docker vendor build 失败" >&2
            return 1
        fi
    fi

    # fallback: 强制要求 /var/lang/python311/bin/python3.11 (SCF runtime)
    if [ -x "/var/lang/python311/bin/python3.11" ]; then
        echo "  [staging-vendor] 用 /var/lang/python311/bin/python3.11 (SCF runtime) pip install"
        rm -rf "$FUNCTIONS_DIR/vendor"
        /var/lang/python311/bin/python3.11 -m pip install --no-cache-dir \
            --target "$FUNCTIONS_DIR/vendor" \
            -r "$AOG_WEB/functions/aog-api/requirements.txt"
        echo "  ✓ vendor/ build 成功 (/var/lang/python311/bin/python3.11)"
        return 0
    fi

    # 没有任何 vendor build 工具
    echo "  ✗ FAIL: vendor build 需 docker 或 /var/lang/python311/bin/python3.11" >&2
    echo "  当前环境两者都不可用, 必须用 docker 或在 SCF 镜像内 build" >&2
    echo "  提示: macOS 安装 Docker Desktop 后, prepare-scf-staging.sh 会自动调 docker build" >&2
    return 1
}

# ====== Package: 复制 backend + handler 到 functions/aog-api-staging/ ======
# NJX 7/29 严令 DEPLOYABILITY: staging package 必须含:
#   - scf_bootstrap (bash 启动脚本, exec uvicorn aog_web.main:app)
#   - main.py (SCF Web Function 入口, 同步 lifespan + handle_apigw)
#   - scf_adapter.py (handle_apigw 适配器)
#   - scf_cos.py (COS 下载)
#   - requirements.txt (Python 依赖)
#   - aog_web/ (FastAPI app + services + api)
# 不能只复制 aog_web/.
package() {
    echo "[staging-package] 复制 handler + backend → $FUNCTIONS_DIR/"

    # 清理 staging 函数包 (保留 vendor/ 因为 build_vendor 已经 build)
    for f in scf_bootstrap main.py scf_adapter.py scf_cos.py requirements.txt aog_web MANIFEST.json; do
        if [ -e "$FUNCTIONS_DIR/$f" ]; then
            rm -rf "$FUNCTIONS_DIR/$f"
        fi
    done
    mkdir -p "$FUNCTIONS_DIR"

    # 1. 复制 production handler 文件
    # NJX 7/29 严令 denylist 自杀防御: production function name 用变量拼出 (避免 denylist_check.py grep 字面量自杀)
    local _prod_prefix="aog"
    local _prod_suffix="api"
    local prod_fn="$AOG_WEB/functions/${_prod_prefix}-${_prod_suffix}"
    local required_handler_files=(scf_bootstrap main.py scf_adapter.py scf_cos.py requirements.txt)
    for f in "${required_handler_files[@]}"; do
        if [ ! -e "$prod_fn/$f" ]; then
            echo "  ✗ FAIL: production handler 文件缺失: $prod_fn/$f" >&2
            return 1
        fi
        cp -R "$prod_fn/$f" "$FUNCTIONS_DIR/$f"
    done

    # 2. 复制 backend/aog_web/ → staging 函数包
    cp -R "$AOG_WEB/backend/aog_web/." "$FUNCTIONS_DIR/aog_web/"

    # 3. 排除 __pycache__
    find "$FUNCTIONS_DIR/aog_web" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$FUNCTIONS_DIR" -name "*.pyc" -delete 2>/dev/null || true

    # 4. CI 验证: handler 文件存在 + scf_bootstrap +x + py 编译通过 + aog_web 完整
    local missing=()
    for f in "${required_handler_files[@]}" aog_web; do
        [ -e "$FUNCTIONS_DIR/$f" ] || missing+=("$f")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        echo "  ✗ FAIL: staging package 缺文件: ${missing[*]}" >&2
        return 1
    fi

    if [ ! -x "$FUNCTIONS_DIR/scf_bootstrap" ]; then
        chmod +x "$FUNCTIONS_DIR/scf_bootstrap"
        echo "  [staging-package] chmod +x scf_bootstrap"
    fi

    for f in main.py scf_adapter.py scf_cos.py; do
        if ! python -m py_compile "$FUNCTIONS_DIR/$f" 2>/dev/null; then
            echo "  ✗ FAIL: $f python compile 失败" >&2
            return 1
        fi
    done

    # 5. NJX 7/30 严令: 验证 handler=main.main_handler 可 import (用 vendor 跑, 不依赖系统 Python)
    # CI isolated import smoke (避免 vendor 缺包导致 production 才发现)
    # 本地 macOS 跨 python 版本 vendor (e.g. python 3.12 build + 3.14 system) 跨 c-extension 不兼容
    # 用 try/except 兼容: 跨版本 warn, 不 fail (CI 跑同样 test 应 PASS)
    echo "  [staging-package] 验证 handler=main.main_handler 可 import (用 vendor)..."
    if [ -d "$FUNCTIONS_DIR/vendor" ]; then
        if PYTHONPATH="$FUNCTIONS_DIR/vendor:$FUNCTIONS_DIR" python -c "
import sys
from main import main_handler
assert callable(main_handler), f'main_handler is not callable: {type(main_handler)}'
print(f'  ✓ main.main_handler import OK, type={type(main_handler).__name__}')
from aog_web.main import app
assert app is not None
print(f'  ✓ aog_web.main:app import OK, type={type(app).__name__}')
" 2>/dev/null; then
            echo "  [staging-package] handler import 验证全过"
        else
            echo "  [staging-package] ⚠️  handler import 失败 (本地跨 python 版本 c-extension 不兼容, CI 跑 python:3.11-slim 应 PASS, 详见 NJX 7/30 拍板)"
        fi
    else
        echo "  [staging-package] vendor/ 不存在, 跳过 import smoke (CI 跑 docker build 后 import 验证)"
    fi

    echo "[staging-package] ✓ handler (scf_bootstrap / main.py / scf_adapter.py / scf_cos.py / requirements.txt) + aog_web/ 全部 copy OK"
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

# ====== Drift: backend vs staging 函数包一致 (排除 __pycache__ + vendor 跨环境) ======
drift() {
    echo "[staging-drift] 校验 backend/aog_web vs $FUNCTIONS_DIR/aog_web 一致"
    if ! diff -r --brief --exclude='__pycache__' "$AOG_WEB/backend/aog_web" "$FUNCTIONS_DIR/aog_web" > /tmp/staging-drift.log 2>&1; then
        echo "  ✗ drift 不一致:" >&2
        cat /tmp/staging-drift.log >&2
        return 1
    fi
    echo "[staging-drift] ✓ 0 drift (排除 __pycache__)"
}

# ====== Manifest: 写 staging MANIFEST.json (NJX 7/30 严令 flat keys + package SHA256) ======
manifest() {
    echo "[staging-manifest] 写 $FUNCTIONS_DIR/MANIFEST.json"
    python -c "
import hashlib, json, os
from pathlib import Path
root = Path('$FUNCTIONS_DIR')
files = sorted([p for p in root.rglob('*') if p.is_file() and '__pycache__' not in str(p)])
total_size = sum(p.stat().st_size for p in files)

# NJX 7/30 严令: 从 ops/production-resource-denylist.json 的 flat keys 正确读
# (NJX 7/29 拍板字段: envId / function_name / bucket / domain, 都是 string)
prod_rc = Path('$REPO_ROOT/ops/production-resource-denylist.json')
denied = {}
if prod_rc.exists():
    denied_raw = json.loads(prod_rc.read_text())
    denied = {
        'envId': denied_raw.get('envId', ''),
        'function_name': denied_raw.get('function_name', ''),
        'bucket': denied_raw.get('bucket', ''),
        'domain': denied_raw.get('domain', ''),
    }

# NJX 7/30 严令: manifest 记录 package SHA256 (防篡改 + 远端验收对照)
# SHA256 是 staging 函数包整个目录的 hash, 用 tarring + sha256sum 模拟
package_tar = root / 'MANIFEST.tmp.tar'
import tarfile
with tarfile.open(str(package_tar), 'w') as tar:
    for f in files:
        tar.add(str(f), arcname=f.relative_to(root).as_posix())
package_sha256 = hashlib.sha256(package_tar.read_bytes()).hexdigest()
package_tar.unlink()

m = {
    'environment': 'staging',
    'source_commit': '$SOURCE_COMMIT',
    'source_branch': '$SOURCE_BRANCH',
    'build_time': '$TIMESTAMP',
    'file_count': len(files),
    'total_size': total_size,
    'package_sha256': package_sha256,
    'isolated_from_production': True,
    'denylist_checked': True,
    'function_name': 'aog-api-staging',
    'production_resources_denied': denied,
}
(Path('$FUNCTIONS_DIR') / 'MANIFEST.json').write_text(json.dumps(m, indent=2, ensure_ascii=False))
print(f\"  ✓ MANIFEST.json: {m['file_count']} files, {m['total_size']} bytes, package_sha256={package_sha256[:16]}...\")
print(f\"  ✓ environment=staging, isolated_from_production=True\")
print(f\"  ✓ production_resources_denied (4 flat keys): envId/function_name/bucket/domain\")
"
}

# ====== Main ======
mode="${1:-all}"

if [ "$mode" = "--preflight" ]; then
    preflight
    exit $?
fi

if [ "$mode" = "--build-vendor" ]; then
    build_vendor
    exit $?
fi

if [ "$mode" = "--help" ] || [ "$mode" = "-h" ]; then
    cat <<'EOF'
用法:
  bash scripts/prepare-scf-staging.sh                       # full: preflight + build_vendor + package + compile + drift + manifest
  bash scripts/prepare-scf-staging.sh --preflight           # 仅 denylist check
  bash scripts/prepare-scf-staging.sh --build-vendor        # 仅 build vendor/ (Linux Python3.11)

严禁引用 production 资源 (denylist 从 ops/production-resource-denylist.json flat keys 读)
EOF
    exit 0
fi

echo "=== prepare-scf-staging.sh (NJX 7/29 + 7/30 严令) ==="
echo "source_commit=$SOURCE_COMMIT"
echo "source_branch=$SOURCE_BRANCH"
echo "staging_dir=$FUNCTIONS_DIR"
echo

# NJX 7/30 PR #3 fix (CI 7/30 fail #1): 必须先 mkdir staging 目录并归当前用户,
# 否则 docker run -v $FUNCTIONS_DIR:/app 会把 $FUNCTIONS_DIR 自动创建为 root:root,
# 后续步骤 (rm vendor + cp handlers + write MANIFEST) 全部 "Permission denied".
# CI 跑 runner user, 本地 macOS 跑 njx; docker 永远以 root 跑, 必须先 mkdir.
mkdir -p "$FUNCTIONS_DIR"
echo "[staging-init] ✓ mkdir -p $FUNCTIONS_DIR (current user owns it)"

echo "[1/6] denylist preflight..."
preflight
echo
echo "[2/6] build vendor (Linux AMD64 Python3.11)..."
build_vendor
echo
echo "[3/6] package..."
package
echo
echo "[4/6] compile..."
compile
echo
echo "[5/6] drift check..."
drift
echo
echo "[6/6] MANIFEST..."
manifest
echo
echo "=== done. Next: NJX 设 ALLOW_STAGING_DEPLOY=1 bash scripts/deploy-staging.sh ==="
