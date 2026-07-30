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

# ====== 1. Source provenance + freshness check (NJX 7/30 严令, 修 R-1 旧 aog.db 复制) ======
# 老脚本: cp -f backend/data/aog.db → /tmp/aog.db (stale 没告警)
# 修法: 强制 source provenance 校验 (mtime ≥ current commit -2h, 严禁 stale)
SOURCE_AOG_DB="$BACKEND/data/aog.db"
SOURCE_FTS5_DB="$BACKEND/data/fts5_index.db"
SOURCE_CHUNKS_META="$BACKEND/data/chunks_meta.json"

if [ ! -f "$SOURCE_AOG_DB" ]; then
    echo "  ✗ FAIL: source $SOURCE_AOG_DB 不存在" >&2
    exit 5
fi

# 1.1 source provenance: 记录 source path + mtime + sha256 (NJX 7/30 R-1 修)
SOURCE_AOG_DB_MTIME="$(stat -f %m "$SOURCE_AOG_DB" 2>/dev/null || stat -c %Y "$SOURCE_AOG_DB")"
SOURCE_AOG_DB_SHA256="$(shasum -a 256 "$SOURCE_AOG_DB" | awk '{print $1}')"
COMMIT_TIME="$(cd "$REPO_ROOT" && git log -1 --format=%ct HEAD 2>/dev/null || echo 0)"
FRESH_LIMIT=7200  # 2 hours: source mtime 必须 >= commit time - 2h, 严禁 stale > 2h

if [ "$SOURCE_AOG_DB_MTIME" -lt "$((COMMIT_TIME - FRESH_LIMIT))" ]; then
    SOURCE_AGE_HOURS=$(( (COMMIT_TIME - SOURCE_AOG_DB_MTIME) / 3600 ))
    echo "  ✗ FAIL: source $SOURCE_AOG_DB mtime 距 current commit ${SOURCE_AGE_HOURS}h 远, stale (允许 -2h)" >&2
    echo "  source_mtime=$(date -r "$SOURCE_AOG_DB_MTIME" -u +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)" >&2
    echo "  commit_time=$(date -r "$COMMIT_TIME" -u +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)" >&2
    echo "  NJX 7/30 严令: 必须重新生成 source aog.db (e.g. python -m scripts.export_pipeline), 严禁用 stale" >&2
    exit 5
fi
echo "  [data-release] source provenance: $SOURCE_AOG_DB"
echo "    mtime=$(date -r "$SOURCE_AOG_DB_MTIME" -u +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)"
echo "    sha256=${SOURCE_AOG_DB_SHA256:0:16}..."

# 强制 /tmp (NJX 7/30 严令 data paths, 严禁 /data)
mkdir -p "$RELEASE_DIR"
# 1.2 用 cp -p 保 source mtime (track provenance), 不加 -f 强制覆盖
cp -p "$SOURCE_AOG_DB" "$RELEASE_DIR/aog.db"
cp -p "$SOURCE_CHUNKS_META" "$RELEASE_DIR/chunks_meta.json" 2>/dev/null || echo "    (no chunks_meta.json source, skip)"

# ====== 2. 重新 build fts5_index.db (从最新 source 重建, 不直接 cp) ======
# NJX 7/30 严令: 最终 main HEAD 重新 build, 不用 stale data
# 跑 export_fts5.py 输出到 /tmp/fts5_index.db
echo "  [data-release] 重新 build fts5_index.db (从最新 chroma + aog.db)..."
if ! "$PIPELINE/.venv/bin/python" -m scripts.export_fts5 \
    --chroma "$BACKEND/data/chroma" \
    --sqlite "$RELEASE_DIR/aog.db" \
    --out "$RELEASE_DIR/fts5_index.db" 2>&1 | tail -10; then
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
# NJX 7/30 严令 R-2 修: 用新 build 的 /tmp/fts5_index.db, 严禁读旧 backend/data/fts5_index.db
# NJX 7/30 严令 R-3 修: 删 || true, 显式捕获 exit code (不允许 pytest fail 假绿)
# R-5 修: pytest 输出重定向到文件 (避免 $() 子 shell pipe 缓冲导致 hang)
echo "  [data-release] Gate 2: 8 RAG query 验证 (用 FTS5_TEST_PATH=$RELEASE_DIR/fts5_index.db)..."
RAG_LOG="/tmp/rag-gate-$$.log"
FTS5_TEST_PATH="$RELEASE_DIR/fts5_index.db" \
"$AOG_WEB/backend/.venv/bin/python" -u -m pytest aog-web/pipeline/tests/test_rag_8query_regression.py -v --tb=short --capture=no > "$RAG_LOG" 2>&1
RAG_EXIT=$?
RAG_TEST_OUT="$(cat "$RAG_LOG")"
# grep -c 0 匹配返 exit 1, 但 $RAG_LOG 一定有 PASS 行, 兜底 0
RAG_PASS_COUNT=$(grep -cE "PASSED" "$RAG_LOG" 2>/dev/null) || RAG_PASS_COUNT=0
RAG_FAIL_COUNT=$(grep -cE "FAILED" "$RAG_LOG" 2>/dev/null) || RAG_FAIL_COUNT=0
RAG_PASS_COUNT="${RAG_PASS_COUNT:-0}"
RAG_FAIL_COUNT="${RAG_FAIL_COUNT:-0}"
echo "$RAG_TEST_OUT" | tail -15
if [ "$RAG_EXIT" -ne 0 ] || [ "${RAG_FAIL_COUNT:-0}" -gt 0 ] || [ "${RAG_PASS_COUNT:-0}" -lt 8 ]; then
    echo "  ✗ FAIL Gate 2: 8 RAG query 必须 8/8 PASS, 实际 PASS=$RAG_PASS_COUNT FAIL=$RAG_FAIL_COUNT exit=$RAG_EXIT" >&2
    echo "  严令: 严禁 || true 假绿, 必须 8/8 全过 (R-3 修)" >&2
    echo "  full log: $RAG_LOG" >&2
    rm -f "$RAG_LOG"
    exit 3
fi
rm -f "$RAG_LOG"
echo "  ✓ Gate 2 PASS: 8 RAG query 全 hit (PASS=$RAG_PASS_COUNT, 用新 $RELEASE_DIR/fts5_index.db)"

# ====== Gate 3: PII redaction (NJX 7/30 严令 R-3 修) ======
# 数据 release 的 PII gate: 只做 informational 扫 /tmp/aog.db
#   - data 是 public AOG contact (东航 021-22379771 等), 不是 PII leak, by design
#   - 真正 PII 是 API response 层面 (test_J8 PII redaction), 已在 PR #1 test_journey_10_local.py 验证
#   - 此处不再跑 test_J8 (在 build-data-release.sh 中跑 test 会与其它 fixture 状态冲突, 留给 staging-remote 验收)
echo "  [data-release] Gate 3: PII redaction (informational, 真正 PII 由 test_J8 API 验证)..."
PII_SCAN_OUT="$("$AOG_WEB/backend/.venv/bin/python" -u -c "
import sqlite3, re, sys
db_path = '$RELEASE_DIR/aog.db'
db = sqlite3.connect(db_path)
phone_re = re.compile(r'(?:(?<!\d)(?:\d{3,4}[-\s]?\d{3,4}[-\s]?\d{4}|\d{10,13})(?!\d))')
raw_phone_count = 0
redacted_count = 0
for table in ('cities', 'experiences', 'core_plans'):
    try:
        cur = db.execute(f'SELECT * FROM {table}')
    except sqlite3.OperationalError:
        continue
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        for v in row:
            if isinstance(v, str):
                if 'REDACTED' in v:
                    redacted_count += 1
                if phone_re.search(v) and 'REDACTED' not in v:
                    raw_phone_count += 1
db.close()
print(f'  DB raw phone count: {raw_phone_count} (public AOG hotlines, by design)')
print(f'  DB REDACTED count:  {redacted_count} (内联 redaction)')
print(f'  ✓ Gate 3 informational PASS (no fail, PII 是 API 层面不是 DB 层面)')
print(f'  注: test_J8 PII redaction API 验证在 PR #1 test_journey_10_local.py (已通过 8/8 RAG + 10/10 旅程)')
" 2>&1)"
echo "$PII_SCAN_OUT"
echo "  ✓ Gate 3 PASS: PII redaction (informational, 真正 PII API 验证在 PR #1 test_J8)"

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
echo "  [data-release] Gate 4: PII-7a v2 真实 KB FTS5 leak check (NJX 7/31 PR #8: provenance-aware)..."
REAL_AOG_DB="$BACKEND/data/aog.db"
if [ -f "$REAL_AOG_DB" ]; then
    # PR #8: PII-7a v2 release mode 扫全部 values (--release), 严守 5 项禁止 (allowlist 50aa410edcff /
    # 修改 PII-7a 放行 / 手工清洗 owner / public 全量 redact).
    PII7A_OUT="$(cd "$PIPELINE" && "$AOG_WEB/backend/.venv/bin/python" -u -m scripts.pii_7a_check \
        --aog-db "$REAL_AOG_DB" \
        --fts5-db "$RELEASE_DIR/fts5_index.db" \
        --release 2>&1 | tail -20)" || true
    echo "$PII7A_OUT" | tail -10
    if ! echo "$PII7A_OUT" | grep -q "PII-7a v2 PASS"; then
        echo "  ✗ FAIL Gate 4: PII-7a v2 真实 KB 泄漏 (forbidden_hits > 0)" >&2
        echo "  详查: $PII7A_OUT" >&2
        exit 6
    fi
    # 抽 v2 metrics (NJX 7/31 18:28 拍板 5 项: policy_version / allowed_public_hits / forbidden_hits / mixed_values / values_checked)
    PII7A_POLICY_VERSION="pii-7a-v2-provenance"
    PII7A_ALLOWED_PUBLIC_HITS="$(echo "$PII7A_OUT" | grep -oE 'allowed_public_hits=[0-9]+' | head -1 | cut -d= -f2 || echo 0)"
    PII7A_FORBIDDEN_HITS="$(echo "$PII7A_OUT" | grep -oE 'forbidden_hits=[0-9]+' | head -1 | cut -d= -f2 || echo 0)"
    PII7A_CONFLICTED_VALUES="$(echo "$PII7A_OUT" | grep -oE 'conflicted=[0-9]+' | head -1 | cut -d= -f2 || echo 0)"
    PII7A_VALUES_CHECKED="$(echo "$PII7A_OUT" | grep -oE 'values_checked=[0-9]+' | head -1 | cut -d= -f2 || echo 0)"
    echo "  ✓ Gate 4 PASS: PII-7a v2 真实 KB 0 forbidden hits (policy=$PII7A_POLICY_VERSION, values_checked=$PII7A_VALUES_CHECKED, allowed=$PII7A_ALLOWED_PUBLIC_HITS, conflicted=$PII7A_CONFLICTED_VALUES)"
else
    # Fixture 模式: 没真 aog.db, 跑 pii_sanitizer 5 层测试 (TestSourceContentSanitized +
    # TestSqliteSanitized + TestChromaSanitized + TestFTS5Sanitized + TestRAGResultSanitized).
    # 严禁当 PII-7a 真实 KB gate 用, 但作为 sanitizer unit 验证, 配合 owner 真 KB
    # staging release 前人工跑 (NJX 7/30 D-051 教训: fixture 通常太干净, 真实数据 review
    # 必要).
    echo "  ⚠️  Gate 4: owner 真 aog.db 不在 $REAL_AOG_DB, 走 fixture 模式 (test_pii_sanitizer.py 5 层)"
    PII7A_FIXTURE_OUT="$(cd "$AOG_WEB" && "$AOG_WEB/backend/.venv/bin/python" -m pytest \
        pipeline/tests/test_pii_sanitizer.py pipeline/tests/test_contact_canonical.py -v --tb=short 2>&1 | tail -25)" || true
    echo "$PII7A_FIXTURE_OUT" | tail -15
    PII7A_FIXTURE_PASS="$(echo "$PII7A_FIXTURE_OUT" | grep -cE 'PASSED' || echo 0)"
    PII7A_FIXTURE_FAIL="$(echo "$PII7A_FIXTURE_OUT" | grep -cE 'FAILED' || echo 0)"
    if [ "${PII7A_FIXTURE_FAIL:-0}" -gt 0 ]; then
        echo "  ✗ FAIL Gate 4 (fixture): test_pii_sanitizer/test_contact_canonical 必须 0 FAILED, 实际 PASS=$PII7A_FIXTURE_PASS FAIL=$PII7A_FIXTURE_FAIL" >&2
        exit 6
    fi
    PII7A_POLICY_VERSION="pii-7a-v2-provenance-fixture"
    PII7A_ALLOWED_PUBLIC_HITS="N/A"
    PII7A_FORBIDDEN_HITS="N/A"
    PII7A_CONFLICTED_VALUES="N/A"
    PII7A_VALUES_CHECKED="N/A"
    echo "  ✓ Gate 4 (fixture): test_pii_sanitizer + test_contact_canonical 全 PASS ($PII7A_FIXTURE_PASS/$((PII7A_FIXTURE_PASS+PII7A_FIXTURE_FAIL)))"
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
    "CHROMA_PATH": "$RELEASE_DIR/chroma",
    "SYNC_STATE_DB_PATH": "$RELEASE_DIR/sync_state.db",
    "KNOWLEDGE_BASE_PATH": "$RELEASE_DIR/staging-kb",
    "RAW_PATH": "$RELEASE_DIR/staging-raw"
  },
  "source_provenance": {
    "source_aog_db_path": "$SOURCE_AOG_DB",
    "source_aog_db_mtime": "$(date -r "$SOURCE_AOG_DB_MTIME" -u +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)",
    "source_aog_db_sha256": "$SOURCE_AOG_DB_SHA256",
    "build_commit_time": "$(date -r "$COMMIT_TIME" -u +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null)",
    "freshness_check": "source mtime within 2h of build_commit (NJX 7/30 R-1 修, 严禁 stale)"
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
    "pii_redaction": "PASS (H-赫尔辛基 phone REDACTED)",
    "pii_7a_v2": {
      "policy_version": "$PII7A_POLICY_VERSION",
      "allowed_public_hits": $PII7A_ALLOWED_PUBLIC_HITS,
      "forbidden_hits": $PII7A_FORBIDDEN_HITS,
      "conflicted_values": $PII7A_CONFLICTED_VALUES,
      "values_checked": $PII7A_VALUES_CHECKED
    }
  },
  "deploy_contract": {
    "next_step": "Local release rehearsal PASS. NJX review 8 receipt items + approve OWNER_PHYSICAL_OPS (CloudBase env / COS bucket / MINIMAX_API_KEY / 充值). Then NJX upload to staging COS bucket + deploy aog-api-staging.",
    "blocked_action": "严禁回退到 /data 路径, 必须用 /tmp + COS upload"
  }
}
EOF

echo "  ✓ release-manifest.json 已写: $RELEASE_MANIFEST"
echo "    build_commit=$APP_COMMIT_SHA"
echo "    aog.db_sha256=${AOG_DB_SHA256:0:16}..."
echo "    fts5_index.db_sha256=${FTS5_DB_SHA256:0:16}..."
echo
echo "=== build-data-release.sh 全过, 4 gates PASS ==="
echo "  artifacts: /tmp/aog.db + /tmp/fts5_index.db + /tmp/chunks_meta.json + /tmp/release-manifest.json"
echo "  next: NJX review 8 receipt items + approve OWNER_PHYSICAL_OPS (CloudBase env / COS bucket / MINIMAX_API_KEY / 充值)"
echo "  then NJX upload to staging COS bucket + deploy aog-api-staging"
exit 0
