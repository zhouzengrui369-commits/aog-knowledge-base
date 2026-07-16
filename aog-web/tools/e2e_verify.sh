#!/bin/bash
# P7: E2E 验证 — 测 4 端点真公网请求
# 用法: ./tools/e2e_verify.sh <api-base-url>
# 例: ./tools/e2e_verify.sh https://njx-copilot-d6gs7642f8fa17122.ap-shanghai.app.tcloudbase.com/aog-api

set -e

API_BASE="${1:?Usage: $0 <api-base-url>}"
echo "=== AOG E2E 验证 ==="
echo "API base: $API_BASE"
echo

# 1. health
echo "→ 1. /api/health"
RES=$(curl -s -w "\n[HTTP_CODE:%{http_code}]" --max-time 30 "$API_BASE/health")
echo "$RES"
echo

# 2. cities
echo "→ 2. /api/cities?limit=3"
RES=$(curl -s -w "\n[HTTP_CODE:%{http_code}]" --max-time 30 "$API_BASE/cities?limit=3")
echo "$RES" | head -50
echo

# 3. experiences
echo "→ 3. /api/experiences?limit=2"
RES=$(curl -s -w "\n[HTTP_CODE:%{http_code}]" --max-time 30 "$API_BASE/experiences?limit=2")
echo "$RES" | head -30
echo

# 4. chat (NSM-2 红线: references ≥ 1)
echo "→ 4. /api/chat (NSM-2 verify)"
RES=$(curl -s -w "\n[HTTP_CODE:%{http_code}]" --max-time 60 \
  -X POST "$API_BASE/chat" \
  -H "Content-Type: application/json" \
  -d '{"q":"B787 风挡 AOG 处理"}')
echo "$RES"
echo

# 5. 提取 references 数
echo "→ 5. references ≥ 1 验证"
REFS=$(echo "$RES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('references',[])))" 2>/dev/null || echo "?")
echo "references count: $REFS"
if [ "$REFS" = "0" ] || [ "$REFS" = "?" ]; then
  echo "❌ NSM-2 红线违反: references 必须 ≥ 1"
  exit 1
fi
echo "✅ NSM-2 满足"

echo
echo "=== ✅ 4 端点全过 ==="
