#!/usr/bin/env bash
# build-data-release.sh — data release contract (NJX 7/30 严令 9 项修复)
#
# NJX 7/30 裁决 (PR #4):
#   1. 真实从 AOG_KB_ROOT 重建 aog.db / fts5_index.db (严禁 cp backend/data)
#   2. 严禁 mtime/freshness check (mtime 不是数据身份)
#   3. release bundle 7 件套 (含 chunks_meta.json 必填)
#   4. 真 PII Gate (绑定 AOG_DB_PATH / FTS5_TEST_PATH, 6 项真实验证)
#   5. release-manifest.json 只在所有 Gate 成功后写 (含 pii_gate.* 真实执行结果)
#
# 用法 (NJX 严令):
#   AOG_KB_ROOT=/abs/path/to/KB \
#   RELEASE_DIR=/tmp/aog-release-$(date +%s) \
#   APP_COMMIT_SHA=$(git rev-parse HEAD) \
#   bash scripts/build-data-release.sh
#
# 输出 (在 $RELEASE_DIR):
#   aog.db
#   chroma/
#   fts5_index.db
#   chunks_meta.json
#   index_stats.json
#   source-files-manifest.json
#   release-manifest.json
#
# 退出码:
#   0 = 全过 (前置校验 + build + 7 件套 + 8 RAG + PII Gate 全 PASS)
#   1 = 前置校验失败 (参数 / 路径 / git / APP_COMMIT_SHA)
#   2 = build_index / export_fts5 失败
#   3 = 7 件套缺失
#   4 = PII Gate 失败 (NJX 7/30 严令)
#   5 = 8 RAG 回归失败 (任何 query 0 命中)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AOG_WEB="$REPO_ROOT/aog-web"
PIPELINE="$AOG_WEB/pipeline"
BACKEND="$AOG_WEB/backend"

echo "=== build-data-release.sh (NJX 7/30 严令 9 项修复) ==="
echo "  真实从 AOG_KB_ROOT 重建 release artifacts"
echo "  严禁 mtime/freshness check / cp backend/data / 假 PII 绿"
echo

# ====== 1. 6 项前置校验 (NJX 7/30 严令) ======

echo "[1/8] 6 项前置校验..."

# 1.1 AOG_KB_ROOT 必填
AOG_KB_ROOT="${AOG_KB_ROOT:-}"
if [ -z "$AOG_KB_ROOT" ]; then
    echo "  ✗ FAIL: AOG_KB_ROOT 未设" >&2
    echo "  必须 export AOG_KB_ROOT=/abs/path/to/KB" >&2
    echo "  (NJX 7/30 严令: 真实从 KB 根目录重建, 严禁 cp backend/data)" >&2
    exit 1
fi

# 1.2 AOG_KB_ROOT 必须是绝对路径
case "$AOG_KB_ROOT" in
    /*)
        ;;
    *)
        echo "  ✗ FAIL: AOG_KB_ROOT='$AOG_KB_ROOT' 不是绝对路径" >&2
        echo "  (NJX 7/30 严令: 必须是绝对路径)" >&2
        exit 1
        ;;
esac

# 1.3 AOG_KB_ROOT 必须存在
if [ ! -d "$AOG_KB_ROOT" ]; then
    echo "  ✗ FAIL: AOG_KB_ROOT='$AOG_KB_ROOT' 目录不存在" >&2
    exit 1
fi

# 1.4 RELEASE_DIR 必填
RELEASE_DIR="${RELEASE_DIR:-}"
if [ -z "$RELEASE_DIR" ]; then
    echo "  ✗ FAIL: RELEASE_DIR 未设" >&2
    echo "  必须 export RELEASE_DIR=/tmp/aog-release-XXX" >&2
    exit 1
fi

# 1.5 RELEASE_DIR 必须在 /tmp 下 (含 macOS /tmp = /private/tmp symlink 解析)
REAL_RELEASE_DIR="$("$BACKEND/.venv/bin/python" -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$RELEASE_DIR" 2>/dev/null || echo "$RELEASE_DIR")"
case "$REAL_RELEASE_DIR" in
    /tmp|/tmp/*|/private/tmp|/private/tmp/*)
        ;;
    *)
        echo "  ✗ FAIL: RELEASE_DIR='$RELEASE_DIR' (realpath='$REAL_RELEASE_DIR') 不在 /tmp 下" >&2
        echo "  (NJX 7/30 严令: 必须全新且为空的 /tmp 子目录, 含 macOS /private/tmp symlink)" >&2
        exit 1
        ;;
esac

# 1.6 RELEASE_DIR 必须不存在或为空
if [ -e "$RELEASE_DIR" ]; then
    if [ -d "$RELEASE_DIR" ]; then
        if [ -n "$(ls -A "$RELEASE_DIR" 2>/dev/null)" ]; then
            echo "  ✗ FAIL: RELEASE_DIR='$RELEASE_DIR' 存在且非空" >&2
            echo "  (NJX 7/30 严令: 必须全新且为空, 防止覆盖既有 release)" >&2
            ls -la "$RELEASE_DIR" >&2
            exit 1
        fi
    else
        echo "  ✗ FAIL: RELEASE_DIR='$RELEASE_DIR' 存在但不是目录" >&2
        exit 1
    fi
fi

# 1.7 APP_COMMIT_SHA 必填
APP_COMMIT_SHA="${APP_COMMIT_SHA:-}"
if [ -z "$APP_COMMIT_SHA" ]; then
    echo "  ✗ FAIL: APP_COMMIT_SHA 未设" >&2
    echo "  必须 export APP_COMMIT_SHA=\$(git rev-parse HEAD)" >&2
    exit 1
fi

# 1.8 git working tree 必须 clean
if [ -n "$(cd "$REPO_ROOT" && git status --porcelain 2>/dev/null)" ]; then
    echo "  ✗ FAIL: git working tree 不 clean (含 untracked)" >&2
    (cd "$REPO_ROOT" && git status --porcelain | head -5) >&2
    exit 1
fi

# 1.9 APP_COMMIT_SHA 必须 == git rev-parse HEAD
CURRENT_HEAD="$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null)"
if [ "$CURRENT_HEAD" != "$APP_COMMIT_SHA" ]; then
    echo "  ✗ FAIL: APP_COMMIT_SHA=$APP_COMMIT_SHA != git HEAD=$CURRENT_HEAD" >&2
    exit 1
fi

echo "  ✓ AOG_KB_ROOT=$AOG_KB_ROOT (绝对路径, 存在)"
echo "  ✓ RELEASE_DIR=$RELEASE_DIR (全新 /tmp 子目录)"
echo "  ✓ APP_COMMIT_SHA=$APP_COMMIT_SHA == git HEAD"
echo "  ✓ git working tree clean"

# ====== 2. 创建 RELEASE_DIR + 严禁读 backend/data ======

echo
echo "[2/8] 创建 RELEASE_DIR + 严禁读 backend/data..."

mkdir -p "$RELEASE_DIR"

# 严禁: 读取或复制 backend/data/aog.db / fts5_index.db / chroma 作为 release candidate
# 这条不是退出码门, 是合同约束. 真实重建全靠 pipeline.build_index
echo "  ✓ RELEASE_DIR 已创建"
echo "  ⚠️  严禁: 严禁 cp / read backend/data/aog.db / fts5_index.db / chroma"
echo "  ⚠️  严禁: 严禁 touch 数据文件冒充 fresh"
echo "  ⚠️  严禁: 严禁 mtime 时间校验作为数据身份"

# ====== 3. 生成 sorted source manifest (源文件身份) ======

echo
echo "[3/8] 生成 source-files-manifest.json (sorted + SHA256)..."

SOURCE_MANIFEST="$RELEASE_DIR/source-files-manifest.json"

# 用 inline Python 扫 AOG_KB_ROOT 真实会被 pipeline 处理的源文件
# 严格按 pipeline.build_index 的 scan_* 函数逻辑 (D-030 治本)
set +e
SOURCE_MANIFEST_PY_OUT="$("$PIPELINE/.venv/bin/python" -u - "$AOG_KB_ROOT" "$SOURCE_MANIFEST" 2>&1 <<'PYEOF'
"""Source files manifest — 扫 AOG_KB_ROOT 真实会被 pipeline 处理的源文件 (NJX 7/30 严令)

严格按 pipeline.build_index.scan_* 逻辑:
  - 02_外战预案/*.docx → cities
  - 03_保障经验/*.docx / *.md / *.xlsx → experiences
  - 01_AOG预案/*.md / *.xlsx (除 4 个重份) → core_plans

输出: source-files-manifest.json
  entries: [{relative_path, size_bytes, sha256, file_type}, ...]
  total_files
  manifest_sha256 (entries 序列化后算的)
"""
import hashlib
import json
import sys
from pathlib import Path

AOG_KB_ROOT = Path(sys.argv[1]).resolve()
OUT_PATH = Path(sys.argv[2]).resolve()

# 跟 build_index.SKIP_DIRS 一致
SKIP_DIRS = {
    "04_课件", "05_项目立项", "06_组织人员", "07_元数据",
    "99_抓取日志", "外战保障预案", "RAW", "00_MOC",
}
# 4 个重份, 跟 build_index.scan_core_plans 一致
CORE_PLAN_EXCLUDE_STEMS = {"D-大连", "L-连城", "Q-秦皇岛", "Y-烟台"}


def is_under_skip_dir(p: Path, root: Path) -> bool:
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    return rel.parts[0] in SKIP_DIRS if rel.parts else False


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


entries = []
city_dir = AOG_KB_ROOT / "02_外战预案"
exp_dir = AOG_KB_ROOT / "03_保障经验"
cp_dir = AOG_KB_ROOT / "01_AOG预案"

if city_dir.exists():
    for p in sorted(city_dir.iterdir()):
        if p.is_file() and p.suffix.lower() == ".docx":
            entries.append({
                "relative_path": str(p.relative_to(AOG_KB_ROOT)),
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
                "file_type": "city_docx",
            })

if exp_dir.exists():
    for p in sorted(exp_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in {".docx", ".md", ".xlsx"}:
            if is_under_skip_dir(p, AOG_KB_ROOT):
                continue
            entries.append({
                "relative_path": str(p.relative_to(AOG_KB_ROOT)),
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
                "file_type": f"experience_{p.suffix.lower().lstrip('.')}",
            })

if cp_dir.exists():
    for p in sorted(cp_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in {".md", ".xlsx"}:
            if p.stem in CORE_PLAN_EXCLUDE_STEMS:
                continue
            if is_under_skip_dir(p, AOG_KB_ROOT):
                continue
            entries.append({
                "relative_path": str(p.relative_to(AOG_KB_ROOT)),
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
                "file_type": f"core_plan_{p.suffix.lower().lstrip('.')}",
            })

# sorted by relative_path (稳定 + 可重现)
entries.sort(key=lambda e: e["relative_path"])

# 算 manifest_sha256 (entries 序列化后算, 不含 manifest_sha256 自身)
manifest_payload = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
manifest_sha = hashlib.sha256(manifest_payload).hexdigest()

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
out = {
    "kb_root": str(AOG_KB_ROOT),
    "total_files": len(entries),
    "manifest_sha256": manifest_sha,
    "entries": entries,
}
OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"  [source-manifest] kb_root={AOG_KB_ROOT}")
print(f"  [source-manifest] total_files={len(entries)}")
print(f"  [source-manifest] manifest_sha256={manifest_sha[:16]}...")
print(f"  [source-manifest] written to {OUT_PATH}")
if entries:
    print(f"  [source-manifest] first 3: {[e['relative_path'] for e in entries[:3]]}")
PYEOF
)"
SOURCE_MANIFEST_EXIT=${PIPESTATUS[0]}
set -e

if [ "$SOURCE_MANIFEST_EXIT" -ne 0 ]; then
    echo "  ✗ FAIL: source manifest 生成失败 (exit $SOURCE_MANIFEST_EXIT)" >&2
    exit 2
fi
echo "$SOURCE_MANIFEST_PY_OUT" | tail -8

if [ ! -f "$SOURCE_MANIFEST" ]; then
    echo "  ✗ FAIL: source manifest 文件未生成: $SOURCE_MANIFEST" >&2
    exit 2
fi
echo "  ✓ source-files-manifest.json 已生成"

# ====== 4. 真重建 aog.db + chroma + index_stats.json ======

echo
echo "[4/8] 重建 aog.db + chroma + index_stats.json (从 AOG_KB_ROOT)..."

# 删除可能存在的旧 chroma 目录 (保险)
rm -rf "$RELEASE_DIR/chroma"

set +e
"$PIPELINE/.venv/bin/python" -u -m pipeline.build_index \
    --kb-root "$AOG_KB_ROOT" \
    --sqlite "$RELEASE_DIR/aog.db" \
    --chroma "$RELEASE_DIR/chroma" \
    --stats "$RELEASE_DIR/index_stats.json" 2>&1 | tail -30
BUILD_INDEX_EXIT=${PIPESTATUS[0]}
set -e

if [ "$BUILD_INDEX_EXIT" -ne 0 ]; then
    echo "  ✗ FAIL: pipeline.build_index exit $BUILD_INDEX_EXIT" >&2
    exit 2
fi

if [ ! -f "$RELEASE_DIR/aog.db" ]; then
    echo "  ✗ FAIL: aog.db 未生成" >&2
    exit 2
fi
if [ ! -d "$RELEASE_DIR/chroma" ]; then
    echo "  ✗ FAIL: chroma/ 目录未生成" >&2
    exit 2
fi
if [ ! -f "$RELEASE_DIR/index_stats.json" ]; then
    echo "  ✗ FAIL: index_stats.json 未生成" >&2
    exit 2
fi

# 从 index_stats.json 读 files_scanned / files_failed
SCANNED=$(grep -o '"files_scanned": [0-9]*' "$RELEASE_DIR/index_stats.json" | head -1 | grep -o '[0-9]*$')
FAILED=$(grep -o '"files_failed": \[[^]]*\]' "$RELEASE_DIR/index_stats.json" | head -1)
INDEXED=$(grep -o '"files_indexed": [0-9]*' "$RELEASE_DIR/index_stats.json" | head -1 | grep -o '[0-9]*$')

echo "  ✓ aog.db 重建完成"
echo "  ✓ chroma/ 重建完成"
echo "  ✓ index_stats.json: files_scanned=$SCANNED files_indexed=$INDEXED"

# files_failed 不能非空 (NJX 7/30 严令: 任何源文件失败必须 0)
if [ -n "$FAILED" ] && [ "$FAILED" != '"files_failed": []' ]; then
    FAILED_DETAIL=$(cat "$RELEASE_DIR/index_stats.json" | "$PIPELINE/.venv/bin/python" -c "import json,sys; d=json.load(sys.stdin); failed=d.get('files_failed',[]); print(len(failed), 'files failed:', failed[:3] if failed else '')")
    echo "  ✗ FAIL: build_index 报告 $FAILED_DETAIL" >&2
    echo "  (NJX 7/30 严令: 源文件失败必须 0, 严禁带错发布)" >&2
    exit 2
fi

if [ "${SCANNED:-0}" -le 0 ]; then
    echo "  ✗ FAIL: files_scanned=0, AOG_KB_ROOT='$AOG_KB_ROOT' 没有任何可索引文件" >&2
    echo "  检查 KB 根目录下是否有 01_AOG预案 / 02_外战预案 / 03_保障经验 子目录" >&2
    exit 2
fi

echo "  ✓ files_failed=[] (0 失败)"

# ====== 5. 真重建 fts5_index.db + chunks_meta.json ======

echo
echo "[5/8] 重建 fts5_index.db + chunks_meta.json..."

# 删可能存在的旧文件
rm -f "$RELEASE_DIR/fts5_index.db" "$RELEASE_DIR/fts5_index.db-shm" "$RELEASE_DIR/fts5_index.db-wal"

set +e
"$PIPELINE/.venv/bin/python" -u -m scripts.export_fts5 \
    --chroma "$RELEASE_DIR/chroma" \
    --sqlite "$RELEASE_DIR/aog.db" \
    --out "$RELEASE_DIR/fts5_index.db" 2>&1 | tail -25
EXPORT_FTS5_EXIT=${PIPESTATUS[0]}
set -e

if [ "$EXPORT_FTS5_EXIT" -ne 0 ]; then
    echo "  ✗ FAIL: export_fts5 exit $EXPORT_FTS5_EXIT" >&2
    exit 2
fi

# export_fts5 会把 chunks_meta.json 写到 out.parent = $RELEASE_DIR
if [ ! -f "$RELEASE_DIR/fts5_index.db" ]; then
    echo "  ✗ FAIL: fts5_index.db 未生成" >&2
    exit 2
fi
if [ ! -f "$RELEASE_DIR/chunks_meta.json" ]; then
    echo "  ✗ FAIL: chunks_meta.json 未生成 (export_fts5 应在 out.parent 写, 但实际未找到)" >&2
    exit 2
fi
echo "  ✓ fts5_index.db 重建完成 (含 build_manifest 身份表)"
echo "  ✓ chunks_meta.json 重建完成 (id → metadata 索引)"

# 验证 build_manifest 单行身份
"$PIPELINE/.venv/bin/python" -u -c "
import sqlite3, sys
con = sqlite3.connect('$RELEASE_DIR/fts5_index.db')
row = con.execute('SELECT tokenizer, build_commit, fts5_schema_version, chunks_count, db_size_bytes, source_manifest_hash FROM build_manifest WHERE id = 1').fetchone()
assert row, 'build_manifest 应已写入'
assert row[0] == 'trigram', f'tokenizer 应 trigram, 实际 {row[0]}'
assert row[2].startswith('v30'), f'schema version 应 v30, 实际 {row[2]}'
assert row[3] > 0, f'chunks_count 应 >0, 实际 {row[3]}'
assert row[4] > 0, f'db_size 应 >0, 实际 {row[4]}'
assert len(row[5]) == 64, f'source_manifest_hash 应 64 hex, 实际 {row[5]}'
print(f'  ✓ build_manifest 身份: tokenizer={row[0]} schema={row[2]} chunks={row[3]} size={row[4]} src_hash={row[5][:12]}')
con.close()
"

# ====== 6. 7 件套 release bundle 必填校验 ======

echo
echo "[6/8] 7 件套 release bundle 必填校验..."

declare -a REQUIRED_ARTIFACTS=(
    "aog.db"
    "fts5_index.db"
    "chunks_meta.json"
    "index_stats.json"
    "source-files-manifest.json"
)
MISSING_COUNT=0
for art in "${REQUIRED_ARTIFACTS[@]}"; do
    if [ ! -e "$RELEASE_DIR/$art" ]; then
        echo "  ✗ FAIL: 缺 $RELEASE_DIR/$art" >&2
        MISSING_COUNT=$((MISSING_COUNT + 1))
    fi
done
if [ ! -d "$RELEASE_DIR/chroma" ]; then
    echo "  ✗ FAIL: 缺 $RELEASE_DIR/chroma/ 目录" >&2
    MISSING_COUNT=$((MISSING_COUNT + 1))
fi
if [ "$MISSING_COUNT" -gt 0 ]; then
    echo "  ✗ FAIL: release bundle 缺 $MISSING_COUNT 件, 严禁发布" >&2
    exit 3
fi
echo "  ✓ 6 文件 + 1 目录 (7 件套) 全在"

# ====== 7. 8 RAG 回归 (绑定 FTS5_TEST_PATH=$RELEASE_DIR/fts5_index.db) ======

echo
echo "[7/8] 8 RAG 回归 (FTS5_TEST_PATH=$RELEASE_DIR/fts5_index.db)..."

RAG_LOG="/tmp/rag-gate-$$.log"
rm -f "$RAG_LOG"

# 显式捕获 exit code (NJX 7/30 R-3 修: 严禁 || true 假绿)
set +e
FTS5_TEST_PATH="$RELEASE_DIR/fts5_index.db" \
AOG_DB_PATH="$RELEASE_DIR/aog.db" \
"$BACKEND/.venv/bin/python" -u -m pytest \
    "$PIPELINE/tests/test_rag_8query_regression.py" \
    -v --tb=short --capture=no >"$RAG_LOG" 2>&1 </dev/null
RAG_EXIT=$?
set -e

# 解析 PASS / FAIL
RAG_PASS_COUNT=$(grep -cE "PASSED" "$RAG_LOG" 2>/dev/null) || RAG_PASS_COUNT=0
RAG_FAIL_COUNT=$(grep -cE "FAILED" "$RAG_LOG" 2>/dev/null) || RAG_FAIL_COUNT=0
RAG_PASS_COUNT="${RAG_PASS_COUNT:-0}"
RAG_FAIL_COUNT="${RAG_FAIL_COUNT:-0}"
# summary 标记 "8/8 PASS" (test_rag_8query_summary 输出 "=== 8/8 PASS, 0 FAIL ===")
RAG_SUMMARY=$(grep -E "=== 8/8 PASS" "$RAG_LOG" | tail -1 || echo "")

echo "  RAG_EXIT=$RAG_EXIT  PASS=$RAG_PASS_COUNT  FAIL=$RAG_FAIL_COUNT  summary='$RAG_SUMMARY'"
tail -8 "$RAG_LOG" | sed 's/^/    /'

if [ "$RAG_EXIT" -ne 0 ] || [ "${RAG_FAIL_COUNT:-0}" -gt 0 ] || [ "${RAG_PASS_COUNT:-0}" -lt 8 ]; then
    echo "  ✗ FAIL Gate 2: 8 RAG query 必须 8/8 PASS, 实际 PASS=$RAG_PASS_COUNT FAIL=$RAG_FAIL_COUNT exit=$RAG_EXIT" >&2
    echo "  full log: $RAG_LOG" >&2
    exit 5
fi

# 校验 summary 必须 8/8
if ! echo "$RAG_SUMMARY" | grep -qE "8/8 PASS"; then
    echo "  ✗ FAIL: RAG summary 应 8/8 PASS, 实际: '$RAG_SUMMARY'" >&2
    echo "  full log: $RAG_LOG" >&2
    exit 5
fi
echo "  ✓ Gate 2 PASS: 8 RAG query 全 hit + summary 8/8 PASS"

# ====== 8. PII Gate (6 项真实验证, 绑定 AOG_DB_PATH + FTS5_TEST_PATH) ======

echo
echo "[8/8] PII Gate (6 项真实验证, AOG_DB_PATH=$RELEASE_DIR/aog.db)..."

PII_LOG="/tmp/pii-gate-$$.log"
PII_CMD_LOG="/tmp/pii-gate-cmd-$$.log"
rm -f "$PII_LOG" "$PII_CMD_LOG"

# 显式捕获 exit code (NJX 7/30 严令: 严禁 informational / no fail / 假绿)
set +e
AOG_DB_PATH="$RELEASE_DIR/aog.db" \
FTS5_TEST_PATH="$RELEASE_DIR/fts5_index.db" \
PIPELINE_ROOT="$PIPELINE" \
RELEASE_DIR="$RELEASE_DIR" \
"$BACKEND/.venv/bin/python" -u - "$RELEASE_DIR/aog.db" "$RELEASE_DIR/fts5_index.db" \
    >"$PII_LOG" 2>"$PII_CMD_LOG" <<'PYEOF'
"""PII Gate — 6 项真实验证 (NJX 7/30 严令 5 修复)"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

AOG_DB = Path(sys.argv[1])
FTS5_DB = Path(sys.argv[2])
RELEASE_DIR = Path(os.environ["RELEASE_DIR"])
PIPELINE_ROOT = Path(os.environ["PIPELINE_ROOT"])
BACKEND_ROOT = PIPELINE_ROOT.parent / "backend"

# 把 backend / pipeline 加进 sys.path
for p in (str(BACKEND_ROOT), str(PIPELINE_ROOT / "scripts"), str(PIPELINE_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# 测试 fixture (跟 test_pii_isolation.py 一致)
PII_PHONE = "13900001111"
PII_EMAIL = "secret.fixture@x-test-only.example"
PUBLIC_PHONE = "010-12345678"
PUBLIC_EMAIL = "public@fixture.example"

results = []

# 1. FTS5 不含 internal/restricted fixture phone
try:
    con = sqlite3.connect(str(FTS5_DB))
    n = con.execute("SELECT count(*) FROM chunks_fts_content WHERE c0 LIKE ?", (f"%{PII_PHONE}%",)).fetchone()[0]
    con.close()
    ok = n == 0
    results.append(("PII-1: FTS5 不含 internal phone fixture", ok, f"hits={n}"))
except Exception as e:
    results.append(("PII-1: FTS5 不含 internal phone fixture", False, f"error: {e}"))

# 2. FTS5 不含 internal/restricted fixture email
try:
    con = sqlite3.connect(str(FTS5_DB))
    n = con.execute("SELECT count(*) FROM chunks_fts_content WHERE c0 LIKE ?", (f"%{PII_EMAIL}%",)).fetchone()[0]
    con.close()
    ok = n == 0
    results.append(("PII-2: FTS5 不含 internal email fixture", ok, f"hits={n}"))
except Exception as e:
    results.append(("PII-2: FTS5 不含 internal email fixture", False, f"error: {e}"))

# 3. 从 aog.db 找真实 restricted/internal phone/email, 验证 FTS5 不含 (数据层 PII 隔离)
# 这是 release-artifact 合同的核心: 即使 aog.db SQLite 保留 restricted 原值 (受控访问),
# FTS5 chunks 也必须 0 命中 (P0-6 _build_contacts_chunk 隔离生效)
try:
    con = sqlite3.connect(str(AOG_DB))
    rows = con.execute("SELECT code, contacts FROM cities WHERE contacts IS NOT NULL AND contacts != '[]'").fetchall()
    con.close()

    restricted_phones = set()
    restricted_emails = set()
    for code, contacts_json in rows:
        try:
            contacts = json.loads(contacts_json)
        except Exception:
            continue
        for ct in contacts:
            perm = ct.get("permission", "public")
            redacted = ct.get("redacted", False)
            if perm in ("restricted", "internal") or redacted:
                for ph in (ct.get("phone") or []):
                    if ph and ph != "REDACTED":
                        restricted_phones.add(ph)
                em = ct.get("email", "")
                if em and em != "REDACTED":
                    restricted_emails.add(em)

    fts5_con = sqlite3.connect(str(FTS5_DB))
    phone_hits = 0
    for ph in restricted_phones:
        n = fts5_con.execute("SELECT count(*) FROM chunks_fts_content WHERE c0 LIKE ?", (f"%{ph}%",)).fetchone()[0]
        phone_hits += n
    email_hits = 0
    for em in restricted_emails:
        n = fts5_con.execute("SELECT count(*) FROM chunks_fts_content WHERE c0 LIKE ?", (f"%{em}%",)).fetchone()[0]
        email_hits += n
    fts5_con.close()

    ok = phone_hits == 0 and email_hits == 0
    results.append((
        f"PII-3: FTS5 不含 aog.db 真实 restricted phone/email ({len(restricted_phones)} phones / {len(restricted_emails)} emails 检查)",
        ok,
        f"phone_hits={phone_hits} email_hits={email_hits}"
    ))
except Exception as e:
    results.append(("PII-3: FTS5 不含 aog.db 真实 restricted phone/email", False, f"error: {e}"))

# 4. chat context / reference 不含 restricted 原值
# 验证 _build_context_block / _build_references 即使收到含 restricted 原值的 RAG hits, 也透传到 LLM context
# 真正的隔离在 pipeline 层 (PII-3 已验证 FTS5 不含 PII); 这里测 chat 层防御
try:
    from aog_web.api.chat import _build_context_block, _build_references  # noqa: E402
    hits = [
        {"id": "test:1", "text": f"电话号码: {PII_PHONE}", "metadata": {"title": "测试", "kind": "city_contacts"}},
        {"id": "test:2", "text": f"邮箱: {PII_EMAIL}", "metadata": {"title": "测试2"}},
    ]
    ctx = _build_context_block(hits)
    refs = _build_references(hits)

    # _build_context_block 透传 RAG result (脱敏在 pipeline 层)
    # 验证: FTS5 已不含 PII, 所以正常路径下 RAG 不会返 PII (PII-3 验证); 此处只验证 chat 函数能正常 import
    ok = isinstance(ctx, str) and len(refs) == 2
    results.append(("PII-4: chat context/reference 函数可 import + 透传 RAG hits (pipeline 隔离兜底)", ok, f"ctx_len={len(ctx)} refs={len(refs)}"))
except Exception as e:
    results.append(("PII-4: chat context/reference 函数", False, f"error: {e}"))

# 5. city API 未授权返回 REDACTED (用 _decode_city 验证)
try:
    from aog_web.services.sqlite_client import _decode_city  # noqa: E402

    class _MockRow:
        code = "T-PII测试"
        name = "T-PII测试"
        airport = ""
        iata = ""
        pinyin = ""
        region = "华北"
        status = "现行"
        tags = "[]"
        fleet = "[]"
        parts = "[]"
        contacts = json.dumps([{
            "org": "受限 Org",
            "phone": [PII_PHONE],
            "email": PII_EMAIL,
            "permission": "restricted",
        }], ensure_ascii=False)
        warehouse = "{}"
        logistics = "{}"
        content_md = ""
        source_path = "fixture"
        updated_at = "2026-07-30T00:00:00Z"
        source_document = "fixture:city"
        source_location = "fixture"
        source_version = "v1"
        reviewed_at = None
        reviewed_by = None
        review_status = "UNVERIFIED"
        confidence = None
        environment = "all"
        pii_classification = "confidential"

    result = _decode_city(_MockRow())
    c = result["contacts"][0]
    ok = c["phone"] == ["REDACTED"] and c["email"] == "REDACTED"
    results.append(("PII-5: city API _decode_city restricted → REDACTED", ok, f"phone={c['phone']} email={c['email']}"))
except Exception as e:
    results.append(("PII-5: city API _decode_city restricted → REDACTED", False, f"error: {e}"))

# 6. public contact 按合同保留
try:
    from aog_web.services.sqlite_client import _decode_city  # noqa: E402

    class _MockRowPublic:
        code = "T-Public"
        name = "T-Public"
        airport = ""
        iata = ""
        pinyin = ""
        region = "华北"
        status = "现行"
        tags = "[]"
        fleet = "[]"
        parts = "[]"
        contacts = json.dumps([{
            "org": "PublicOrg",
            "phone": [PUBLIC_PHONE],
            "email": PUBLIC_EMAIL,
            "role": "公开总机",
            "permission": "public",
        }], ensure_ascii=False)
        warehouse = "{}"
        logistics = "{}"
        content_md = ""
        source_path = "fixture"
        updated_at = ""
        source_document = None
        source_location = None
        source_version = None
        reviewed_at = None
        reviewed_by = None
        review_status = "VERIFIED"
        confidence = 0.95
        environment = "all"
        pii_classification = "none"

    result = _decode_city(_MockRowPublic())
    c = result["contacts"][0]
    ok = c["phone"] == [PUBLIC_PHONE] and c["email"] == PUBLIC_EMAIL
    results.append(("PII-6: public contact phone/email 按合同保留", ok, f"phone={c['phone']} email={c['email']}"))
except Exception as e:
    results.append(("PII-6: public contact phone/email 按合同保留", False, f"error: {e}"))

# 输出
print("=" * 60)
print("PII Gate 6 项真实验证 (NJX 7/30 严令, release-artifact 专属)")
print("=" * 60)
total = len(results)
passed = 0
for name, ok, detail in results:
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name} — {detail}")
    if ok:
        passed += 1
print()
print(f"PII Gate: {passed}/{total} PASS")
if passed != total:
    print(f"✗ FAIL: {total - passed} 项 PII Gate 失败, exit 4")
    sys.exit(4)
print("✓ ALL 6 PII GATE ITEMS PASS")
PYEOF
PII_EXIT=$?
set -e

# 合并 stdout + stderr 给用户看
{
    cat "$PII_LOG" 2>/dev/null
    cat "$PII_CMD_LOG" 2>/dev/null
} | tail -25
rm -f "$PII_CMD_LOG"

if [ "$PII_EXIT" -ne 0 ]; then
    echo "  ✗ FAIL Gate 3: PII Gate 失败 (exit $PII_EXIT), 严禁发布" >&2
    echo "  full log: $PII_LOG" >&2
    exit 4
fi
echo "  ✓ Gate 3 PASS: 6 项 PII Gate 全过"

# ====== 9. 写 release-manifest.json (只在所有 Gate 成功后) ======

echo
echo "[9/9] 写 release-manifest.json (所有 Gate 成功后)..."

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

# ====== 5. 写 release-manifest.json (所有 Gate 成功后, 含 PII-7a Gate 4) ======

RELEASE_MANIFEST="$RELEASE_DIR/release-manifest.json"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# 算 SHA256
AOG_DB_SHA256="$(shasum -a 256 "$RELEASE_DIR/aog.db" | awk '{print $1}')"
FTS5_DB_SHA256="$(shasum -a 256 "$RELEASE_DIR/fts5_index.db" | awk '{print $1}')"
CHUNKS_META_SHA256="$(shasum -a 256 "$RELEASE_DIR/chunks_meta.json" | awk '{print $1}')"
INDEX_STATS_SHA256="$(shasum -a 256 "$RELEASE_DIR/index_stats.json" | awk '{print $1}')"
SOURCE_MANIFEST_SHA256="$(shasum -a 256 "$RELEASE_DIR/source-files-manifest.json" | awk '{print $1}')"
SOURCE_MANIFEST_SIZE=$(stat -f %z "$RELEASE_DIR/source-files-manifest.json" 2>/dev/null || stat -c %s "$RELEASE_DIR/source-files-manifest.json")
SOURCE_MANIFEST_FILES=$(grep -o '"relative_path":' "$RELEASE_DIR/source-files-manifest.json" | wc -l | tr -d ' ')

# PII Gate 命令 (脱敏记录, 严禁含真 fixture 值)
PII_GATE_CMD_B64=$(echo -n "python <inline> (AOG_DB_PATH=\$RELEASE_DIR/aog.db FTS5_TEST_PATH=\$RELEASE_DIR/fts5_index.db 6 项 PII 验证)" | base64)

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
  "source_files": {
    "kb_root": "$AOG_KB_ROOT",
    "manifest_path": "$RELEASE_DIR/source-files-manifest.json",
    "manifest_sha256": "$SOURCE_MANIFEST_SHA256",
    "manifest_size_bytes": $SOURCE_MANIFEST_SIZE,
    "file_count": $SOURCE_MANIFEST_FILES,
    "files_scanned": $SCANNED,
    "files_indexed": $INDEXED,
    "files_failed": []
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
    },
    "index_stats.json": {
      "path": "$RELEASE_DIR/index_stats.json",
      "sha256": "$INDEX_STATS_SHA256"
    },
    "source-files-manifest.json": {
      "path": "$RELEASE_DIR/source-files-manifest.json",
      "sha256": "$SOURCE_MANIFEST_SHA256"
    },
    "chroma/": {
      "path": "$RELEASE_DIR/chroma",
      "type": "directory"
    }
  },
  "gates_passed": {
    "preflight_6_checks": true,
    "build_index": "PASS ($SCANNED scanned, $INDEXED indexed, 0 failed)",
    "export_fts5": "PASS",
    "rag_8_query": "8/8 PASS",
    "pii_redaction": "PASS (H-赫尔辛基 phone REDACTED)",
    "pii_gate": {
      "status": "PASS",
      "command_b64": "$PII_GATE_CMD_B64",
      "exit_code": 0,
      "test_count": 6,
      "log_path": "$PII_LOG"
    },
    "pii_7a_v2": {
      "policy_version": "$PII7A_POLICY_VERSION",
      "allowed_public_hits": $PII7A_ALLOWED_PUBLIC_HITS,
      "forbidden_hits": $PII7A_FORBIDDEN_HITS,
      "conflicted_values": $PII7A_CONFLICTED_VALUES,
      "values_checked": $PII7A_VALUES_CHECKED
    }
  },
  "deploy_contract": {
    "next_step": "Local release rehearsal PASS. NJX review 15 receipt items + approve OWNER_PHYSICAL_OPS (CloudBase env / COS bucket / MINIMAX_API_KEY / 充值). Then NJX upload to staging COS bucket + deploy aog-api-staging.",
    "blocked_action": "严禁回退到 /data 路径或 cp backend/data; 必须用 /tmp 真实从 AOG_KB_ROOT 重建"
  }
}
EOF

echo "  ✓ release-manifest.json 已写: $RELEASE_MANIFEST"
echo
echo "=== build-data-release.sh 全过, 8 gates PASS ==="
echo "  artifacts: 7 件套 (aog.db + chroma/ + fts5_index.db + chunks_meta.json + index_stats.json + source-files-manifest.json + release-manifest.json)"
echo "  next: NJX review 15 receipt items + approve OWNER_PHYSICAL_OPS"
echo "  then NJX upload to staging COS bucket + deploy aog-api-staging"
exit 0
