#!/usr/bin/env bash
# build-data-release.sh — staging 数据 release contract (NJX 7/30 严令 PR #3)
#
# NJX 7/30 严令 data release contract:
#   1. 最终 main HEAD 上重新 build aog.db + fts5_index.db (从最新 source 重建, 避免 stale data)
#   2. build_commit 必须等于最终 APP_COMMIT_SHA (env var, deploy 时 NJX 注入)
#   3. 输出 release-manifest.json (含 aog.db + fts5_index.db 的 SHA256, build_commit, build_time)
#   4. staging upload 前跑 manifest / PII / 8-query Gate (NJX 7/29 8 RAG 回归 + PII redaction)
#   5. data release 全部 /tmp (NJX 7/30 严令 data paths, 严禁 /data)
#
# 用法:
#   APP_COMMIT_SHA=$(git rev-parse HEAD) bash scripts/build-data-release.sh
#   ALLOW_DATA_RELEASE_OVERRIDE=1 bash scripts/build-data-release.sh  # 强制覆盖 (NJX 拍板 release 频率)
#
# 输出:
#   /tmp/aog.db (重建的元数据 SQLite)
#   /tmp/fts5_index.db (重建的 FTS5 索引)
#   /tmp/chunks_meta.json (chunks meta 索引)
#   /tmp/release-manifest.json (SHA256 + build_commit + build_time + 8 RAG query 验证 + PII check)
#
# 退出码:
#   0 = 全过 (8 RAG query hit + PII redaction verified)
#   1 = build_commit != APP_COMMIT_SHA
#   2 = fts5 export 失败
#   3 = 8 RAG query fail (任何 query 0 hit)
#   4 = PII redaction fail (raw phone 泄漏)
#   5 = data release 数据不完整 (缺 aog.db / fts5_index.db / chunks_meta.json)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AOG_WEB="$REPO_ROOT/aog-web"
PIPELINE="$AOG_WEB/pipeline"
BACKEND="$AOG_WEB/backend"
RELEASE_DIR="${RELEASE_DIR:-/tmp}"

# 读取 APP_COMMIT_SHA (NJX 注入)
APP_COMMIT_SHA="${APP_COMMIT_SHA:-}"

echo "=== build-data-release.sh (NJX 7/30 严令) ==="
echo "release_dir=$RELEASE_DIR"
echo "app_commit_sha=${APP_COMMIT_SHA:-<not set>}"

# ====== Gate 1: build_commit == APP_COMMIT_SHA (NJX 7/30 严令) ======
if [ -z "$APP_COMMIT_SHA" ]; then
    echo "  ✗ FAIL: APP_COMMIT_SHA 未设" >&2
    echo "  必须 export APP_COMMIT_SHA=\$(git rev-parse HEAD) 后跑" >&2
    exit 1
fi
current_head="$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null)"
if [ "$current_head" != "$APP_COMMIT_SHA" ]; then
    echo "  ✗ FAIL: git HEAD=$current_head != APP_COMMIT_SHA=$APP_COMMIT_SHA" >&2
    exit 1
fi
echo "  ✓ Gate 1 PASS: build_commit == APP_COMMIT_SHA ($APP_COMMIT_SHA)"

# ====== 1. 重新 build aog.db (从生产 data 拷到 /tmp) ======
SOURCE_AOG_DB="$BACKEND/data/aog.db"
SOURCE_FTS5_DB="$BACKEND/data/fts5_index.db"
SOURCE_CHUNKS_META="$BACKEND/data/chunks_meta.json"

if [ ! -f "$SOURCE_AOG_DB" ]; then
    echo "  ✗ FAIL: source $SOURCE_AOG_DB 不存在" >&2
    exit 5
fi

# 强制 /tmp (NJX 7/30 严令 data paths, 严禁 /data)
mkdir -p "$RELEASE_DIR"
cp -f "$SOURCE_AOG_DB" "$RELEASE_DIR/aog.db"
cp -f "$SOURCE_FTS5_DB" "$RELEASE_DIR/fts5_index.db"
cp -f "$SOURCE_CHUNKS_META" "$RELEASE_DIR/chunks_meta.json" 2>/dev/null || true

# ====== 2. 重新 build fts5_index.db (从最新 source 重建, 不直接 cp) ======
# NJX 7/30 严令: 最终 main HEAD 重新 build, 不用 stale data
# 跑 export_fts5.py 输出到 /tmp/fts5_index.db
echo "  [data-release] 重新 build fts5_index.db (从最新 chroma + aog.db)..."
if ! "$PIPELINE/.venv/bin/python" -m scripts.export_fts5 \
    --chroma "$BACKEND/data/chroma" \
    --sqlite "$RELEASE_DIR/aog.db" \
    --out "$RELEASE_DIR/fts5_index.db" \
    --meta "$RELEASE_DIR/chunks_meta.json" 2>&1 | tail -10; then
    echo "  ✗ FAIL: export_fts5.py 失败" >&2
    exit 2
fi
echo "  ✓ fts5_index.db 重新 build 成功"

# ====== 3. 算 SHA256 (NJX 7/30 严令 package SHA256 防篡改) ======
AOG_DB_SHA256="$(shasum -a 256 "$RELEASE_DIR/aog.db" | awk '{print $1}')"
FTS5_DB_SHA256="$(shasum -a 256 "$RELEASE_DIR/fts5_index.db" | awk '{print $1}')"
CHUNKS_META_SHA256="$(shasum -a 256 "$RELEASE_DIR/chunks_meta.json" 2>/dev/null | awk '{print $1}' || echo none)"

echo "  [data-release] SHA256:"
echo "    aog.db           = ${AOG_DB_SHA256:0:16}..."
echo "    fts5_index.db    = ${FTS5_DB_SHA256:0:16}..."
echo "    chunks_meta.json = ${CHUNKS_META_SHA256:0:16}..."

# ====== Gate 2: 8 RAG query 验证 (NJX 7/29 8 RAG 回归) ======
# NJX 7/30 严令: staging upload 前必须 8 RAG query 验证, 任何 query 0 hit = fail
echo "  [data-release] Gate 2: 8 RAG query 验证 (NJX 7/29 8 RAG 回归)..."
RAG_TEST_OUT="$("$AOG_WEB/backend/.venv/bin/python" -m pytest tests/test_rag_8query_regression.py -v --tb=short 2>&1 | tail -20)" || true
RAG_PASS_COUNT="$(echo "$RAG_TEST_OUT" | grep -cE "PASSED" || echo 0)"
RAG_FAIL_COUNT="$(echo "$RAG_TEST_OUT" | grep -cE "FAILED" || echo 0)"
echo "$RAG_TEST_OUT" | tail -10
if [ "${RAG_FAIL_COUNT:-0}" -gt 0 ] || [ "${RAG_PASS_COUNT:-0}" -lt 8 ]; then
    echo "  ✗ FAIL Gate 2: 8 RAG query 必须 8/8 PASS, 实际 PASS=$RAG_PASS_COUNT FAIL=$RAG_FAIL_COUNT" >&2
    exit 3
fi
echo "  ✓ Gate 2 PASS: 8 RAG query 全 hit (PASS=$RAG_PASS_COUNT)"

# ====== Gate 3: PII redaction (NJX 7/30 严令: raw phone 不能泄漏) ======
# 用 test_journey_10_local.py 跑 PII check (J8: H-赫尔辛基 phone=["REDACTED"])
echo "  [data-release] Gate 3: PII redaction 验证 (raw phone 不能泄漏)..."
PII_TEST_OUT="$("$AOG_WEB/backend/.venv/bin/python" -m pytest backend/tests/test_journey_10_local.py::test_8_helsinki_phone_redacted -v --tb=short 2>&1 | tail -10)" || true
echo "$PII_TEST_OUT" | tail -5
if ! echo "$PII_TEST_OUT" | grep -q "PASSED"; then
    echo "  ✗ FAIL Gate 3: PII redaction 失败 (raw phone 可能泄漏)" >&2
    exit 4
fi
echo "  ✓ Gate 3 PASS: PII redaction 生效 (H-赫尔辛基 phone=[\"REDACTED\"])"

# ====== 4. 输出 release-manifest.json ======
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
RELEASE_MANIFEST="$RELEASE_DIR/release-manifest.json"

cat > "$RELEASE_MANIFEST" <<EOF
{
  "build_commit": "$APP_COMMIT_SHA",
  "build_time": "$TIMESTAMP",
  "build_host": "$(hostname)",
  "release_dir": "$RELEASE_DIR",
  "staging_function": "aog-api-staging",
  "data_paths": {
    "AOG_DB_PATH": "$RELEASE_DIR/aog.db",
    "FTS5_PATH": "$RELEASE_DIR/fts5_index.db",
    "CHROMA_PATH": "$BACKEND/data/chroma",
    "SYNC_STATE_DB_PATH": "$RELEASE_DIR/sync_state.db",
    "KNOWLEDGE_BASE_PATH": "$RELEASE_DIR/staging-kb",
    "RAW_PATH": "$RELEASE_DIR/staging-raw"
  },
  "artifacts": {
    "aog.db": {
      "path": "$RELEASE_DIR/aog.db",
      "sha256": "$AOG_DB_SHA256",
      "size_bytes": $(stat -f %z "$RELEASE_DIR/aog.db" 2>/dev/null || stat -c %s "$RELEASE_DIR/aog.db")
    },
    "fts5_index.db": {
      "path": "$RELEASE_DIR/fts5_index.db",
      "sha256": "$FTS5_DB_SHA256",
      "size_bytes": $(stat -f %z "$RELEASE_DIR/fts5_index.db" 2>/dev/null || stat -c %s "$RELEASE_DIR/fts5_index.db")
    },
    "chunks_meta.json": {
      "path": "$RELEASE_DIR/chunks_meta.json",
      "sha256": "$CHUNKS_META_SHA256"
    }
  },
  "gates_passed": {
    "build_commit_match": true,
    "rag_8_query": "8/8 PASS",
    "pii_redaction": "PASS (H-赫尔辛基 phone REDACTED)"
  },
  "deploy_contract": {
    "next_step": "NJX upload aog.db + fts5_index.db + chunks_meta.json to staging COS bucket, then deploy aog-api-staging",
    "blocked_action": "严禁回退到 /data 路径, 必须用 /tmp + COS upload"
  }
}
EOF

echo "  ✓ release-manifest.json 已写: $RELEASE_MANIFEST"
echo "    build_commit=$APP_COMMIT_SHA"
echo "    aog.db_sha256=${AOG_DB_SHA256:0:16}..."
echo "    fts5_index.db_sha256=${FTS5_DB_SHA256:0:16}..."
echo
echo "=== build-data-release.sh 全过, 3 gates PASS ==="
echo "  artifacts: /tmp/aog.db + /tmp/fts5_index.db + /tmp/chunks_meta.json + /tmp/release-manifest.json"
echo "  next: NJX upload to staging COS bucket + deploy aog-api-staging"
exit 0
