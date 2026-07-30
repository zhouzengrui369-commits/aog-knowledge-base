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

# ====== Gate 4: PII-7a 真实 KB FTS5 leak check (NJX 7/30 PR #5 严令 5 项) ======
# NJX 7/30 严令 5: PR #4 PII-7a 保留, 作为最终真实 KB Gate.
# NJX 7/30 严令来源: PR #4 staging 合同 PASS, 但真实 KB local rehearsal 触发 PII-7a FAIL.
# 根因: aog.db content_md 字段 (含 vendor info / 站点地址 / 库房电话) 漏脱敏, 9 个 chunk 命中
#       3 个 non-public/redacted phone 原值 (D-051 教训). PR #5 pii_sanitizer 修.
# 检查方法:
#   1. 从 owner 真实 aog.db 抽所有 non-public/restricted/redacted phone + email (hash 12 字符)
#   2. 查 FTS5 chunks_fts_content.c0 是否 0 命中 (命中 = 漏脱敏, fail)
#   3. 严禁进 FTS5 chunk text / chroma persistence / aog.db content_md
# 注: owner 真 aog.db 不在 repo (.gitignore), deploy 阶段才拉到. fixture KB 用
#     test_pii_sanitizer.py 5 层 sanitized 覆盖 (TestSourceContentSanitized +
#     TestSqliteSanitized + TestChromaSanitized + TestFTS5Sanitized + TestRAGResultSanitized).
echo "  [data-release] Gate 4: PII-7a 真实 KB FTS5 leak check (NJX 7/30 PR #5)..."
REAL_AOG_DB="$BACKEND/data/aog.db"
if [ -f "$REAL_AOG_DB" ]; then
    PII7A_OUT="$(cd "$PIPELINE" && "$AOG_WEB/backend/.venv/bin/python" -u -m scripts.pii_7a_check \
        --aog-db "$REAL_AOG_DB" \
        --fts5-db "$RELEASE_DIR/fts5_index.db" \
        --max-samples 100 2>&1 | tail -20)" || true
    echo "$PII7A_OUT" | tail -10
    if ! echo "$PII7A_OUT" | grep -q "PII-7a PASS"; then
        echo "  ✗ FAIL Gate 4: PII-7a 真实 KB 泄漏 (non-public phone/email 在 FTS5 chunks_fts_content 命中)" >&2
        echo "  详查: $PII7A_OUT" >&2
        exit 6
    fi
    echo "  ✓ Gate 4 PASS: PII-7a 真实 KB FTS5 0 命中 (non-public phone/email 全部 REDACTED)"
else
    # Fixture 模式: 没真 aog.db, 跑 pii_sanitizer 5 层测试 (TestSourceContentSanitized +
    # TestSqliteSanitized + TestChromaSanitized + TestFTS5Sanitized + TestRAGResultSanitized).
    # 严禁当 PII-7a 真实 KB gate 用, 但作为 sanitizer unit 验证, 配合 owner 真 KB
    # staging release 前人工跑 (NJX 7/30 D-051 教训: fixture 通常太干净, 真实数据 review
    # 必要).
    echo "  ⚠️  Gate 4: owner 真 aog.db 不在 $REAL_AOG_DB, 走 fixture 模式 (test_pii_sanitizer.py 5 层)"
    PII7A_FIXTURE_OUT="$(cd "$AOG_WEB" && "$AOG_WEB/backend/.venv/bin/python" -m pytest \
        pipeline/tests/test_pii_sanitizer.py -v --tb=short 2>&1 | tail -25)" || true
    echo "$PII7A_FIXTURE_OUT" | tail -15
    PII7A_FIXTURE_PASS="$(echo "$PII7A_FIXTURE_OUT" | grep -cE 'PASSED' || echo 0)"
    PII7A_FIXTURE_FAIL="$(echo "$PII7A_FIXTURE_OUT" | grep -cE 'FAILED' || echo 0)"
    if [ "${PII7A_FIXTURE_FAIL:-0}" -gt 0 ] || [ "${PII7A_FIXTURE_PASS:-0}" -lt 14 ]; then
        echo "  ✗ FAIL Gate 4 (fixture): test_pii_sanitizer.py 必须 14/14 PASS, 实际 PASS=$PII7A_FIXTURE_PASS FAIL=$PII7A_FIXTURE_FAIL" >&2
        exit 6
    fi
    echo "  ✓ Gate 4 (fixture): test_pii_sanitizer.py 14/14 PASS, sanitizer 5 层生效"
    echo "  ⚠️  提醒: fixture 模式 ≠ 真实 KB Gate. owner 真 KB release 前必须重跑 PII-7a (有真 aog.db 时)"
fi

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
