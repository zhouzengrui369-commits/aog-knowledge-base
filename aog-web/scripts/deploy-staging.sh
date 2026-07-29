#!/usr/bin/env bash
# deploy-staging.sh — staging SCF 部署 (NJX 7/29 严令 staging 隔离)
#
# 严禁: 部署到 production 函数 (见 ops/production-resource-denylist.json)
# 严禁: 引用 production envId / bucket / domain (见 ops/production-resource-denylist.json)
#
# DENYLIST_REGEX 策略: production 4 项从 ops/production-resource-denylist.json 读, 不在脚本里 hardcode
# (避免脚本自杀 + 与 denylist_check.py 严格对齐)
#
# 启动时: 跑 denylist preflight (用 denylist_check.py) + ALLOW_STAGING_DEPLOY 闸门
# 部署目标: aog-api-staging (独立函数, staging env 隔离)
#
# NJX 7/29 严令 (本阶段不动云资源):
#   - 第一轮 staging 用 CloudBase 默认域名 (不配自定义 CNAME)
#   - 严禁老命令 (CloudBase v2 不再使用, 见 STAGING_ISOLATION_SPEC.md)
#   - 严禁老 flag (改用 cloudbaserc.staging.json envVariables + {{env.*}} 占位符, 见 SPEC)
#   - 正确命令: tcb fn deploy aog-api-staging --env-id --config-file --mode staging --yes
#
# 用法 (NJX 物理操作后):
#   1. NJX 在 CloudBase 控制台创建独立 staging env (新 envId)
#   2. NJX 申请独立 staging MINIMAX_API_KEY 凭据
#   3. NJX 充值 staging env (PM 建议 ¥50-100)
#   4. NJX export TCB_ENV_ID=staging-env-id, APP_COMMIT_SHA=<merge-sha>
#   5. ALLOW_STAGING_DEPLOY=1 MERGE_SHA=<merge-commit-sha> bash scripts/deploy-staging.sh
#   6. 部署后跑远程 10 旅程 + 8 RAG + PII 真实验收 (NJX 7/29 step 6)

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

    # 4. ops/production-resource-denylist.json 仅作 denylist reference (非可部署 rc)
    local prod_rc="$REPO_ROOT/ops/production-resource-denylist.json"
    if [ -f "$prod_rc" ]; then
        if ! grep -q '"_isolated_for_staging_denylist_only": true' "$prod_rc"; then
            echo "  ✗ FAIL: $prod_rc 缺 _isolated_for_staging_denylist_only: true" >&2
            error=1
        else
            echo "  ✓ $prod_rc (denylist reference 标记正确, 非可部署 rc)"
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

    # ============ 1. TCB_ENV_ID 检查 ============
    if [ -z "${TCB_ENV_ID:-}" ]; then
        echo "  ✗ FAIL: TCB_ENV_ID 未设" >&2
        echo "  必须 NJX 在 CloudBase 控制台创建 staging env 后 export TCB_ENV_ID=staging-env-id" >&2
        return 1
    fi

    local CLOUDBASE_STAGING_ENV="${CLOUDBASE_STAGING_ENV:-$TCB_ENV_ID}"
    echo "  staging env: $CLOUDBASE_STAGING_ENV (独立 staging, 严禁 production)"

    # ============ 2. 严禁 deploy 到 production (DENYLIST_REGEX 策略) ============
    local deploy_check
    deploy_check=$(python3 - "$CLOUDBASE_STAGING_ENV" "$STAGING_FUNCTION_NAME" "$REPO_ROOT/ops/production-resource-denylist.json" <<'PYEOF'
import json, sys
staging_env, staging_fn, denylist_rc = sys.argv[1], sys.argv[2], sys.argv[3]
denied = json.loads(open(denylist_rc).read())
errors = []
if staging_env == denied.get("envId", ""):
    errors.append(f"CLOUDBASE_STAGING_ENV={staging_env} equals production envId")
if staging_fn == denied.get("function_name", ""):
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

    # ============ 3. STAGING_DEPLOY_MODE 模式 (NJX 7/29 DEPLOYABILITY 严令) ============
    # 默认 dry-run, 不实际执行 tcb fn deploy
    # 只有 ALLOW_STAGING_DEPLOY=1 + STAGING_DEPLOY_MODE=execute 才真执行
    local STAGING_DEPLOY_MODE="${STAGING_DEPLOY_MODE:-dry-run}"

    if [ "$STAGING_DEPLOY_MODE" != "execute" ]; then
        echo "  [staging-deploy] STAGING_DEPLOY_MODE=$STAGING_DEPLOY_MODE (默认 dry-run, 不实际执行 tcb fn deploy)"
        echo "  [staging-deploy] 准备好命令 (NJX 物理执行):"
        echo "    tcb fn deploy aog-api-staging \\"
        echo "      --env-id \"\$TCB_ENV_ID\" \\"
        echo "      --config-file \"\$REPO_ROOT/cloudbaserc.staging.json\" \\"
        echo "      --mode staging \\"
        echo "      --yes"
        echo "  [staging-deploy] 严禁: 老命令 / 老 flag (见 STAGING_ISOLATION_SPEC.md §3.5)"
        echo "  [staging-deploy] 当前 dry-run 完成: preflight + verify_package + deploy_target_validate"
        return 0
    fi

    # ============ 4. STAGING_DEPLOY_MODE=execute 真实执行 + 4 项强校验 (NJX 7/29 严令) ============
    echo "  [staging-deploy] STAGING_DEPLOY_MODE=execute, 进入真实部署模式 (4 项强校验)"

    # 4.1 MERGE_SHA 必须是 40 位 hex SHA1
    if ! [[ "${MERGE_SHA:-}" =~ ^[0-9a-f]{40}$ ]]; then
        echo "  ✗ FAIL: MERGE_SHA='${MERGE_SHA:-}' 不是 40 位 hex SHA1" >&2
        return 1
    fi
    echo "  ✓ MERGE_SHA=${MERGE_SHA:0:12}... (40 hex)"

    # 4.2 MERGE_SHA == git rev-parse HEAD (本地 HEAD 必须等于 merge commit)
    local current_head
    current_head=$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null)
    if [ "$current_head" != "$MERGE_SHA" ]; then
        echo "  ✗ FAIL: git HEAD=$current_head != MERGE_SHA=$MERGE_SHA" >&2
        echo "  必须 checkout 到 MERGE_SHA 指向的 commit 后再执行部署" >&2
        return 1
    fi
    echo "  ✓ git rev-parse HEAD == MERGE_SHA"

    # 4.3 APP_COMMIT_SHA == MERGE_SHA (运行时环境变量一致性)
    if [ -z "${APP_COMMIT_SHA:-}" ]; then
        echo "  ✗ FAIL: APP_COMMIT_SHA 未设" >&2
        echo "  必须 export APP_COMMIT_SHA=\$MERGE_SHA (部署时由 CI 注入 {{env.APP_COMMIT_SHA}})" >&2
        return 1
    fi
    if [ "$APP_COMMIT_SHA" != "$MERGE_SHA" ]; then
        echo "  ✗ FAIL: APP_COMMIT_SHA=$APP_COMMIT_SHA != MERGE_SHA=$MERGE_SHA" >&2
        return 1
    fi
    echo "  ✓ APP_COMMIT_SHA == MERGE_SHA"

    # 4.4 git status clean (工作树无未提交变更, 含 untracked files)
    # 用 `git status --porcelain` 检查, 不只查 tracked 变更 (`git diff --quiet HEAD` 不查 untracked)
    if [ -n "$(cd "$REPO_ROOT" && git status --porcelain 2>/dev/null)" ]; then
        echo "  ✗ FAIL: git working tree 不 clean, 有未提交变更 (含 untracked)" >&2
        (cd "$REPO_ROOT" && git status --porcelain | head -10) >&2
        echo "  必须 commit 或 stash 后再执行部署" >&2
        return 1
    fi
    echo "  ✓ git status clean"

    # ============ 5. 真实执行 tcb fn deploy (参数数组, 不 eval) ============
    # NJX 7/29 严令: 严禁: 老命令 / 老 flag (见 STAGING_ISOLATION_SPEC.md §3.5)
    # 正确: tcb fn deploy aog-api-staging --env-id --config-file --mode staging --yes
    echo "  [staging-deploy] 真实执行 tcb fn deploy (参数数组, 不 eval):"

    # 用参数数组 (Bash 数组) 执行, 严禁 eval
    local tcb_cmd=(
        tcb fn deploy "aog-api-staging"
        --env-id "$TCB_ENV_ID"
        --config-file "$REPO_ROOT/cloudbaserc.staging.json"
        --mode staging
        --yes
    )
    echo "  + ${tcb_cmd[*]}"

    if ! "${tcb_cmd[@]}"; then
        local exit_code=$?
        echo "  ✗ FAIL: tcb fn deploy exit $exit_code" >&2
        return 1
    fi

    echo "  ✓ tcb fn deploy 成功"
    echo "  [staging-deploy] staging deployment done, APP_COMMIT_SHA=$MERGE_SHA"
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
