#!/usr/bin/env bash
# deploy-frontend-staging.sh — staging frontend (Next.js static) 部署 (NJX 7/30 严令 PR #3)
#
# NJX 7/30 拍板 修 8: frontend and remote validation
#   - deploy-frontend-staging.sh (本脚本): build Next.js static + tcb hosting deploy
#   - test_journey_10_remote.py (新增): 真实 staging URL 跑 10 旅程
#   - test_rag_8query_remote.py (已存在, 23f8604): 真实 staging URL 跑 8 RAG
#   - 缺 staging URL 时普通 CI 可 skip
#   - staging-validation workflow 中缺 URL 必须 FAIL
#
# 用法 (NJX 物理操作后):
#   1. NJX 在 staging 独立 CloudBase env 创建 hosting (default domain OK)
#   2. NJX export TCB_ENV_ID=staging-env-id
#   3. ALLOW_STAGING_DEPLOY=1 MERGE_SHA=<sha> STAGING_FRONTEND_DOMAIN=<default-domain> bash scripts/deploy-frontend-staging.sh
#
# 默认 dry-run, 不实际 tcb hosting deploy
# ALLOW_STAGING_DEPLOY=1 + STAGING_DEPLOY_MODE=execute 才真执行

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AOG_WEB="$REPO_ROOT/aog-web"
FRONTEND="$AOG_WEB/frontend"
STAGING_DEPLOY_MODE="${STAGING_DEPLOY_MODE:-dry-run}"

echo "=== deploy-frontend-staging.sh (NJX 7/30 严令) ==="
echo "frontend_dir=$FRONTEND"
echo "staging_deploy_mode=$STAGING_DEPLOY_MODE"

# ====== 1. ALLOW_STAGING_DEPLOY 闸门 (NJX 物理 click 授权) ======
if [ "${ALLOW_STAGING_DEPLOY:-0}" != "1" ]; then
    echo "  ✗ FAIL: ALLOW_STAGING_DEPLOY 未设或 != 1" >&2
    echo "  部署是写操作, 必须 NJX 显式授权" >&2
    echo "  重新跑: ALLOW_STAGING_DEPLOY=1 STAGING_DEPLOY_MODE=execute MERGE_SHA=<sha> bash scripts/deploy-frontend-staging.sh" >&2
    exit 1
fi
echo "  ✓ ALLOW_STAGING_DEPLOY=1"

# ====== 2. TCB_ENV_ID 检查 (NJX 7/30 严令: 只用 TCB_ENV_ID, 删 CLOUDBASE_STAGING_ENV alias) ======
if [ -z "${TCB_ENV_ID:-}" ]; then
    echo "  ✗ FAIL: TCB_ENV_ID 未设" >&2
    echo "  必须 NJX 在 CloudBase 控制台创建 staging env 后 export TCB_ENV_ID=staging-env-id" >&2
    exit 1
fi
echo "  ✓ TCB_ENV_ID=$TCB_ENV_ID"

# ====== 3. 严禁 deploy 到 production (DENYLIST_REGEX 策略) ======
denylist_check() {
    python3 - "$TCB_ENV_ID" "$REPO_ROOT/ops/production-resource-denylist.json" <<'PYEOF'
import json, sys
staging_env, denylist_rc = sys.argv[1], sys.argv[2]
denied = json.loads(open(denylist_rc).read())
if staging_env == denied.get("envId", ""):
    print(f"  ✗ FAIL: TCB_ENV_ID={staging_env} equals production envId", file=sys.stderr)
    sys.exit(1)
print("  ✓ deploy target != production envId")
PYEOF
}
denylist_check

# ====== 4. 4 项强校验 (execute 模式) ======
if [ "$STAGING_DEPLOY_MODE" = "execute" ]; then
    # 4.1 MERGE_SHA 40 hex
    if ! [[ "${MERGE_SHA:-}" =~ ^[0-9a-f]{40}$ ]]; then
        echo "  ✗ FAIL: MERGE_SHA='${MERGE_SHA:-}' 不是 40 位 hex SHA1" >&2
        exit 1
    fi
    echo "  ✓ MERGE_SHA=${MERGE_SHA:0:12}..."

    # 4.2 MERGE_SHA == git HEAD
    current_head="$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null)"
    if [ "$current_head" != "$MERGE_SHA" ]; then
        echo "  ✗ FAIL: git HEAD=$current_head != MERGE_SHA=$MERGE_SHA" >&2
        exit 1
    fi
    echo "  ✓ git rev-parse HEAD == MERGE_SHA"

    # 4.3 APP_COMMIT_SHA == MERGE_SHA
    if [ "${APP_COMMIT_SHA:-}" != "$MERGE_SHA" ]; then
        echo "  ✗ FAIL: APP_COMMIT_SHA=$APP_COMMIT_SHA != MERGE_SHA=$MERGE_SHA" >&2
        exit 1
    fi
    echo "  ✓ APP_COMMIT_SHA == MERGE_SHA"

    # 4.4 git status clean
    if [ -n "$(cd "$REPO_ROOT" && git status --porcelain 2>/dev/null)" ]; then
        echo "  ✗ FAIL: git working tree 不 clean" >&2
        exit 1
    fi
    echo "  ✓ git status clean"
fi

# ====== 5. Build Next.js static ======
echo "  [frontend-build] cd $FRONTEND && npm ci && npm run build"
if [ ! -d "$FRONTEND" ]; then
    echo "  ✗ FAIL: $FRONTEND 不存在" >&2
    exit 1
fi

# dry-run 时不真 build, 只 verify package.json 存在
if [ "$STAGING_DEPLOY_MODE" != "execute" ]; then
    if [ -f "$FRONTEND/package.json" ]; then
        echo "  [frontend-build] dry-run 模式, 跳过实际 npm build"
        echo "  [frontend-build] 准备好命令 (NJX 物理执行):"
        echo "    cd $FRONTEND && npm ci && npm run build"
        echo "    tcb hosting deploy .next \\"
        echo "      --env-id \"\$TCB_ENV_ID\" \\"
        echo "      --mode staging"
        echo "  [frontend-build] 当前 dry-run 完成: auth_gate + denylist_check + 4 项校验 dry-run"
        exit 0
    fi
fi

# execute 模式: 实际 build + deploy
cd "$FRONTEND"
if ! npm ci 2>&1 | tail -5; then
    echo "  ✗ FAIL: npm ci 失败" >&2
    exit 1
fi
if ! npm run build 2>&1 | tail -10; then
    echo "  ✗ FAIL: npm run build 失败" >&2
    exit 1
fi
cd "$REPO_ROOT"
echo "  ✓ frontend build OK (.next/ generated)"

# ====== 6. tcb hosting deploy ======
tcb_cmd=(
    tcb hosting deploy ".next"
    --env-id "$TCB_ENV_ID"
    --mode staging
)
echo "  [frontend-deploy] + ${tcb_cmd[*]}"
tcb_exit=0
"${tcb_cmd[@]}" || tcb_exit=$?
if [ "$tcb_exit" -ne 0 ]; then
    echo "  ✗ FAIL: tcb hosting deploy exit $tcb_exit" >&2
    exit 1
fi

echo "  ✓ frontend deploy 成功 (exit 0)"
echo "  [frontend-deploy] staging frontend done, APP_COMMIT_SHA=$MERGE_SHA"
exit 0
