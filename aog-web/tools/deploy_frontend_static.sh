#!/bin/bash
# P6: Frontend Next.js build + static hosting deploy
# 用法: ./tools/deploy_frontend_static.sh <api-base-url>
# 例: ./tools/deploy_frontend_static.sh https://njx-copilot-d6gs7642f8fa17122.ap-shanghai.app.tcloudbase.com/aog-api

set -e

API_BASE="${1:?Usage: $0 <api-base-url>}"
ENV_ID="njx-copilot-d6gs7642f8fa17122"
ROOT="/Users/njx/Project/AOG知识库/aog-web"
FRONTEND="$ROOT/frontend"
OUT_DIR="/tmp/aog-frontend-build"

echo "=== AOG Frontend Static Deploy ==="
echo "API base: $API_BASE"
echo "envId: $ENV_ID"
echo

cd "$FRONTEND"

# 1. 写 .env.local
echo "→ 1. 写 .env.local"
echo "NEXT_PUBLIC_API_BASE=$API_BASE" > .env.local
cat .env.local

# 2. pnpm install (如未装)
echo "→ 2. pnpm install"
pnpm install --frozen-lockfile --prefer-offline 2>&1 | tail -5

# 3. pnpm build
echo "→ 3. pnpm build"
rm -rf "$OUT_DIR"
pnpm build 2>&1 | tail -20

# 4. 验证 out 目录
echo "→ 4. verify out 目录"
ls -la out/ 2>&1 | head -10

# 5. 静态托管 deploy
echo "→ 5. tcb hosting deploy"
cd "$ROOT"
tcb hosting deploy "$OUT_DIR/out/" -e "$ENV_ID" 2>&1 | tail -20

echo
echo "=== ✅ Frontend 部署完成 ==="
echo "前端 URL: https://$ENV_ID.ap-shanghai.app.tcloudbase.com"
echo "API base: $API_BASE"
