#!/usr/bin/env bash
# deploy-staging.sh — staging SCF 部署 (NJX 7/29 严令 staging 隔离)
#
# 严禁: 部署到 production 函数 (见 cloudbaserc.production.json denylist)
# 严禁: 引用 production envId / bucket / domain (见 cloudbaserc.production.json denylist)
#
# DENYLIST_REGEX 策略: production 4 项从 cloudbaserc.production.json 读, 不在脚本里 hardcode
# (避免脚本自杀 + 与 denylist_check.py 严格对齐)
#
# 启动时: 跑 denylist preflight (用 denylist_check.py) + ALLOW_STAGING_DEPLOY 闸门
# 部署目标: aog-api-staging (独立函数, staging env 隔离)
#
# 用法:
#   1. NJX 在 CloudBase 控制台创建独立 staging env (新 envId)
#   2. NJX 申请独立 staging MINIMAX_API_KEY 凭据
#   3. NJX 创建 staging sub-domain CNAME
#   4. NJX 创建独立 COS bucket (staging 命名空间)
#   5. NJX 充值 staging env (PM 建议 ¥50-100)
#   6. NJX export CLOUDBASE_STAGING_ENV=staging-env-id, CLOUDBASE_STAGING_SECRET_ID=xxx
#   7. ALLOW_STAGING_DEPLOY=1 MERGE_SHA=<merge-commit-sha> bash scripts/deploy-staging.sh
#   8. 部署后跑远程 10 旅程 + 8 RAG + PII 真实验收 (NJX 7/29 step 6)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AOG_WEB="$REPO_ROOT/aog-web"
FUNCTIONS_DIR="$AOG_WEB/functions/aog-api-staging"
STAGING_FUNCTION_NAME="aog-api-staging"

# ====== DENYLIST_REGEX: production 4 项从 cloudbaserc.production.json 读, 不在脚本里 hardcode ======
# 用独立 denylist_check.py 严格检查, 避免脚本自杀 (NJX 7/29 严令)

# ====== Preflight: 严格 DENYLIST_REGEX + ALLOW_STAGING_DEPLOY 闸门 ======
# 用独立 denylist_check.py 严格检查 (从 cloudbaserc.production.json 读 denylist)
preflight() {
    local error=0

    echo "[deploy-staging] 1/4 denylist preflight..."

    local denylist_py="$AOG_WEB/scripts/denylist_check.py"
    if [ ! -f "$denylist_py" ]; then
        echo "  ✗ FAIL: $denylist_py 不存在" >&2
        return 1
    fi

    # 1. 本脚本自身 (denylist_check.py 自动排除 # 注释 + xxx-STAGING 占位符)
    if ! python3 "$denylist_py" "$0" >/dev/null 2>&1; then
        echo "  ✗ FAIL: $0 含 production denylist" >&2
        python3 "$denylist_py" "$0" | head -3 >&2
        error=1
    else
        echo "  ✓ $0 (0 production 命中)"
    fi

    # 2. .env.staging.example
    local env_staging="$REPO_ROOT/.env.staging.example"
    if [ -f "$env_staging" ]; then
        if ! python3 "$denylist_py" "$env_staging" >/dev/null 2>&1; then
            echo "  ✗ FAIL: $env_staging 含 production 凭据" >&2
            error=1
        else
            echo "  ✓ $env_staging (0 真 production 凭据)"
        fi
    fi

    # 3. cloudbaserc.staging.json
    local staging_rc="$REPO_ROOT/cloudbaserc.staging.json"
    if [ -f "$staging_rc" ]; then
        if ! python3 "$denylist_py" "$staging_rc" >/dev/null 2>&1; then
            echo "  ✗ FAIL: $staging_rc 含 production 资源" >&2
            error=1
        else
            echo "  ✓ $staging_rc (0 production 命中)"
        fi
    fi

    # 4. cloudbaserc.production.json 仅作 denylist reference
    local prod_rc="$REPO_ROOT/cloudbaserc.production.json"
    if [ -f "$prod_rc" ]; then
        if ! grep -q '"_isolated_for_staging_denylist_only": true' "$prod_rc"; then
            echo "  ✗ FAIL: $prod_rc 缺 _isolated_for_staging_denylist_only: true" >&2
            error=1
        else
            echo "  ✓ $prod_rc (denylist reference 标记正确)"
        fi
    fi

    # 5. functions/aog-api-staging/MANIFEST.json
    local manifest="$FUNCTIONS_DIR/MANIFEST.json"
    if [ ! -f "$manifest" ]; then
        echo "  ✗ FAIL: $manifest 不存在, 请先跑 bash scripts/prepare-scf-staging.sh" >&2
        error=1
    else
        if ! grep -q '"environment": "staging"' "$manifest"; then
            echo "  ✗ FAIL: $manifest environment != staging" >&2
            error=1
        else
            echo "  ✓ $manifest (environment=staging)"
        fi
    fi

    if [ $error -eq 0 ]; then
        echo "  ✓ denylist + manifest check 全过"
    else
        echo "  ✗ preflight FAIL, 阻断部署" >&2
        echo "  提示: 即使 denylist fail, 部署仍需 ALLOW_STAGING_DEPLOY=1 授权" >&2
    fi
    return $error
}

# ====== Auth gate: ALLOW_STAGING_DEPLOY 闸门 (NJX 物理 click 授权) ======
auth_gate() {
    echo "[deploy-staging] 2/4 auth gate..."

    # 必须 ALLOW_STAGING_DEPLOY=1 显式授权
    if [ "${ALLOW_STAGING_DEPLOY:-0}" != "1" ]; then
        echo "  ✗ FAIL: ALLOW_STAGING_DEPLOY 未设或 != 1" >&2
        echo "  部署是写操作, 必须 NJX 显式授权" >&2
        echo "  重新跑: ALLOW_STAGING_DEPLOY=1 MERGE_SHA=<merge-sha> bash scripts/deploy-staging.sh" >&2
        return 1
    fi

    # 必须 MERGE_SHA env (merge commit 锁定)
    if [ -z "${MERGE_SHA:-}" ]; then
        echo "  ✗ FAIL: MERGE_SHA 未设" >&2
        echo "  必须 NJX 拍板的 merge commit SHA (e.g. 3427542850be6ae0da2383e540cbeaf2f729e4d7)" >&2
        return 1
    fi

    echo "  ✓ ALLOW_STAGING_DEPLOY=1"
    echo "  ✓ MERGE_SHA=${MERGE_SHA:0:12}..."
    return 0
}

# ====== Verify staging SCF package 完整 ======
verify_package() {
    echo "[deploy-staging] 3/4 verify staging package..."

    if [ ! -d "$FUNCTIONS_DIR/aog_web" ]; then
        echo "  ✗ FAIL: $FUNCTIONS_DIR/aog_web 不存在" >&2
        return 1
    fi

    local file_count
    file_count=$(find "$FUNCTIONS_DIR/aog_web" -type f -name "*.py" | wc -l | tr -d ' ')
    if [ "$file_count" -lt 30 ]; then
        echo "  ✗ FAIL: aog_web/ python 文件数 $file_count 异常 (期望 ≥30)" >&2
        return 1
    fi

    echo "  ✓ $STAGING_FUNCTION_NAME/aog_web/ 完整 ($file_count py files)"
    return 0
}

# ====== Deploy: 实际云端写操作 (仅 ALLOW_STAGING_DEPLOY=1 时) ======
deploy() {
    echo "[deploy-staging] 4/4 deploy (实际云端写操作)..."

    # 部署到 staging 独立 env (严禁 production envId)
    if [ -z "${CLOUDBASE_STAGING_ENV:-}" ]; then
        echo "  ✗ FAIL: CLOUDBASE_STAGING_ENV 未设" >&2
        echo "  必须 NJX 在 CloudBase 控制台创建 staging env 后 export CLOUDBASE_STAGING_ENV=staging-env-id" >&2
        return 1
    fi

    echo "  staging env: $CLOUDBASE_STAGING_ENV (独立 staging, 严禁 production)"

    # ★ 严禁 deploy 到 production: 用 python 读 production envId + function name, 严格比较
    # (DENYLIST_REGEX 策略: 不在脚本里 hardcode production 值, 全部从 rc 读)
    local deploy_check
    deploy_check=$(python3 - "$CLOUDBASE_STAGING_ENV" "$STAGING_FUNCTION_NAME" "$REPO_ROOT/cloudbaserc.production.json" <<'PYEOF'
import json, sys
staging_env, staging_fn, prod_rc = sys.argv[1], sys.argv[2], sys.argv[3]
prod = json.loads(open(prod_rc).read())
errors = []
if staging_env == prod.get("envId", ""):
    errors.append(f"CLOUDBASE_STAGING_ENV={staging_env} equals production envId")
if staging_fn == prod.get("function", {}).get("name", ""):
    errors.append(f"STAGING_FUNCTION_NAME={staging_fn} equals production function name")
if errors:
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
sys.exit(0)
PYEOF
)
    if [ $? -ne 0 ]; then
        echo "$deploy_check" >&2
        echo "  ✗ FAIL: deploy 目标等于 production" >&2
        return 1
    fi

    echo "  function:    $STAGING_FUNCTION_NAME (独立 staging, 见 cloudbaserc.staging.json)"
    echo "  APP_COMMIT_SHA: ${MERGE_SHA:0:12}..."

    # 真实部署 (此行下方需要 NJX 已经 tcb login)
    # tcb env switch "$CLOUDBASE_STAGING_ENV"
    # tcb fn deploy "$STAGING_FUNCTION_NAME" -e APP_COMMIT_SHA="$MERGE_SHA"
    # 当前 PM 阶段仅做 preflight 验证, 不实际 tcb (NJX 拍板后由 NJX 物理执行)
    echo "  [staging-deploy] ⚠️ 实际 tcb fn deploy 需 NJX 物理执行:"
    echo "    tcb env switch \$CLOUDBASE_STAGING_ENV"
    echo "    tcb fn deploy \$STAGING_FUNCTION_NAME -e APP_COMMIT_SHA=\$MERGE_SHA"
    echo "  [staging-deploy] 当前仅完成 preflight + verify_package"
    return 0
}

# ====== Main ======
echo "=== deploy-staging.sh (NJX 7/29 严令 staging 隔离, DENYLIST_REGEX 严格模式) ==="
echo "staging_function=$STAGING_FUNCTION_NAME (独立 staging function)"
echo "denylist_source=cloudbaserc.production.json (脚本零 hardcode)"
echo
echo "  ⚠️  本脚本需要 ALLOW_STAGING_DEPLOY=1 + MERGE_SHA=<sha> 才能执行 deploy()"
echo

preflight
echo
auth_gate
echo
verify_package
echo
deploy
echo
echo "=== deploy-staging.sh preflight 全过. NJX 物理执行 tcb fn deploy ==="
