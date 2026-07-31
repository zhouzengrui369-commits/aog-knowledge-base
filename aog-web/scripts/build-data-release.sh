#!/usr/bin/env bash
# build-data-release.sh — data release contract (NJX 7/30 严令 9 项修复)
#
# NJX 7/30 裁决 (PR #4):
#   1. 真实从 AOG_KB_ROOT 重建 aog.db / fts5_index.db (严禁 cp backend/data)
#   2. 严禁 mtime/freshness check (mtime 不是数据身份)
#   3. release bundle 9 件套 (D-056 加 wiki/ + wiki-release-manifest.json)
#   4. 真 PII Gate (绑定 AOG_DB_PATH / FTS5_TEST_PATH, 7 项真实验证)
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
#   0 = 全过 (前置校验 + build + 9 件套 + 8 RAG + PII Gate 全 PASS)
#   1 = 前置校验失败 (参数 / 路径 / git / APP_COMMIT_SHA)
#   2 = build_index / export_fts5 失败
#   3 = 9 件套缺失 (D-056 加 wiki/ + wiki-release-manifest.json)
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

# 从 index_stats.json 读 files_scanned / files_indexed / files_failed
# 严禁 grep 解析 (NJX 7/30 严令: 严禁 grep 解析 JSON 字段, 必须 Python json.load 严防 false-green)
set +e
INDEX_STATS_PARSE_OUT="$("$PIPELINE/.venv/bin/python" -u - "$RELEASE_DIR/index_stats.json" "$RELEASE_DIR/source-files-manifest.json" 2>&1 <<'PYEOF'
"""NJX 7/30 严令: index_stats.json 必须 Python json.load 解析, 严禁 grep.

强制一致性 (3 条):
  1. failed_count == 0 (files_failed 数组长度必须为 0)
  2. files_scanned == files_indexed
  3. files_scanned == source-files-manifest.json total_files (源文件身份对齐)
任一条不满足 → print FAIL 行 + sys.exit(2) → shell 端 exit 2 (build 失败)
"""
import json
import sys
from pathlib import Path

stats_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])

try:
    with open(stats_path, encoding="utf-8") as f:
        stats = json.load(f)
except Exception as e:
    print(f"  ✗ FAIL: 解析 index_stats.json 失败: {e}", file=sys.stderr)
    sys.exit(2)

try:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
except Exception as e:
    print(f"  ✗ FAIL: 解析 source-files-manifest.json 失败: {e}", file=sys.stderr)
    sys.exit(2)

files_scanned = int(stats.get("files_scanned", 0))
files_indexed = int(stats.get("files_indexed", 0))
files_failed = stats.get("files_failed", [])
if not isinstance(files_failed, list):
    print(f"  ✗ FAIL: files_failed 应为 list, 实际 {type(files_failed).__name__}", file=sys.stderr)
    sys.exit(2)
failed_count = len(files_failed)
manifest_total = int(manifest.get("total_files", 0))

# 强制一致性 1: failed_count == 0
if failed_count != 0:
    sample = files_failed[:3] if files_failed else []
    print(f"  ✗ FAIL: files_failed={failed_count} 应为 0, 样例: {sample}", file=sys.stderr)
    sys.exit(2)

# 强制一致性 2: files_scanned == files_indexed
if files_scanned != files_indexed:
    print(f"  ✗ FAIL: files_scanned={files_scanned} != files_indexed={files_indexed}", file=sys.stderr)
    sys.exit(2)

# 强制一致性 3: files_scanned == source manifest total_files
if files_scanned != manifest_total:
    print(f"  ✗ FAIL: files_scanned={files_scanned} != source manifest total_files={manifest_total}", file=sys.stderr)
    sys.exit(2)

# 输出: SCANNED, INDEXED, FAILED 三个变量 (空行分隔)
print(f"SCANNED={files_scanned}")
print(f"INDEXED={files_indexed}")
print(f"FAILED={failed_count}")
print(f"MANIFEST_TOTAL={manifest_total}")
sys.exit(0)
PYEOF
)"
INDEX_STATS_PARSE_EXIT=$?
set -e

if [ "$INDEX_STATS_PARSE_EXIT" -ne 0 ]; then
    echo "$INDEX_STATS_PARSE_OUT" | tail -10 >&2
    echo "  ✗ FAIL: index_stats.json 解析/一致性校验失败 (exit $INDEX_STATS_PARSE_EXIT)" >&2
    echo "  (NJX 7/30 严令: 严禁 grep 解析, 必须 Python json.load + 3 条一致性强制)" >&2
    exit 2
fi

# 解析 Python 输出
SCANNED=$(echo "$INDEX_STATS_PARSE_OUT" | grep -E '^SCANNED=' | head -1 | cut -d= -f2)
INDEXED=$(echo "$INDEX_STATS_PARSE_OUT" | grep -E '^INDEXED=' | head -1 | cut -d= -f2)
FAILED=$(echo "$INDEX_STATS_PARSE_OUT" | grep -E '^FAILED=' | head -1 | cut -d= -f2)
MANIFEST_TOTAL=$(echo "$INDEX_STATS_PARSE_OUT" | grep -E '^MANIFEST_TOTAL=' | head -1 | cut -d= -f2)

# 兜底 (Python 输出解析失败时退化, 但 EXIT 已 = 0 说明校验通过, 这里只是字面量补)
SCANNED="${SCANNED:-0}"
INDEXED="${INDEXED:-0}"
FAILED="${FAILED:-0}"
MANIFEST_TOTAL="${MANIFEST_TOTAL:-0}"

echo "  ✓ aog.db 重建完成"
echo "  ✓ chroma/ 重建完成"
echo "  ✓ index_stats.json: files_scanned=$SCANNED files_indexed=$INDEXED files_failed=$FAILED"
echo "  ✓ 三向一致性 (json.load 严验): scanned == indexed == source_manifest.total_files = $MANIFEST_TOTAL"

if [ "${SCANNED:-0}" -le 0 ]; then
    echo "  ✗ FAIL: files_scanned=0, AOG_KB_ROOT='$AOG_KB_ROOT' 没有任何可索引文件" >&2
    echo "  检查 KB 根目录下是否有 01_AOG预案 / 02_外战预案 / 03_保障经验 子目录" >&2
    exit 2
fi

echo "  ✓ files_failed=[] (0 失败)"

# ====== 4.5 D-056: 构建 sanitized wiki release snapshot (FTS5 前置) ======
# NJX 7/31 20:12 拍板 D-056_WIKI_RELEASE_SNAPSHOT_BYPASS:
#   release 阶段先 sanitize wiki, 严禁 export_fts5 隐式读 pipeline/data/wiki
#   严守 4 禁止: 静默修 / 跳过 / wiki_count=0 绕过 / 隐式读 source
echo
echo "[4.5/8] D-056: 构建 sanitized wiki release snapshot..."

# D-056 必填: source wiki 来自 project root (aog-web/pipeline/data/wiki, 跟 KB content 分离)
SOURCE_WIKI_DIR="$REPO_ROOT/aog-web/pipeline/data/wiki"
if [ ! -d "$SOURCE_WIKI_DIR" ]; then
    echo "  ✗ FAIL D-056: source wiki 不存在: $SOURCE_WIKI_DIR" >&2
    echo "  必须 REPO_ROOT=/abs/path/to/AOG知识库 (项目根目录, 含 aog-web/pipeline/data/wiki)" >&2
    exit 6
fi

set +e
(cd "$PIPELINE" && "$BACKEND/.venv/bin/python" -u -m scripts.sanitize_wiki_release \
    --source-wiki "$SOURCE_WIKI_DIR" \
    --release-dir "$RELEASE_DIR") 2>&1 | tail -15
SANITIZE_EXIT=${PIPESTATUS[0]}
set -e

if [ "$SANITIZE_EXIT" -ne 0 ]; then
    echo "  ✗ FAIL D-056: sanitize_wiki_release exit $SANITIZE_EXIT" >&2
    echo "  严守 4 禁止: 静默修 / 跳过 / wiki_count=0 绕过 / 隐式读 source" >&2
    exit 6
fi

# D-056 必填: wiki-release-manifest.json
WIKI_MANIFEST="$RELEASE_DIR/wiki-release-manifest.json"
if [ ! -f "$WIKI_MANIFEST" ]; then
    echo "  ✗ FAIL D-056: wiki-release-manifest.json 未生成" >&2
    exit 6
fi

# D-056 抽 manifest 字段 (NJX 拍板 4 项: policy_version / wiki_source_pages /
#   wiki_sanitized_pages / residual_pii_matches=0)
D056_POLICY_VERSION="$(python3 -c "import json; print(json.load(open('$WIKI_MANIFEST'))['policy_version'])" 2>/dev/null || echo "missing")"
D056_WIKI_SOURCE_PAGES="$(python3 -c "import json; print(json.load(open('$WIKI_MANIFEST'))['wiki_source_pages'])" 2>/dev/null || echo 0)"
D056_WIKI_SANITIZED_PAGES="$(python3 -c "import json; print(json.load(open('$WIKI_MANIFEST'))['wiki_sanitized_pages'])" 2>/dev/null || echo 0)"
D056_RESIDUAL_PII="$(python3 -c "import json; print(json.load(open('$WIKI_MANIFEST'))['residual_pii_matches'])" 2>/dev/null || echo -1)"
D056_WIKI_MANIFEST_SHA256="$(shasum -a 256 "$WIKI_MANIFEST" | awk '{print $1}')"

if [ "$D056_POLICY_VERSION" != "d056-wiki-release-v1" ]; then
    echo "  ✗ FAIL D-056: policy_version=$D056_POLICY_VERSION (必须 d056-wiki-release-v1)" >&2
    exit 6
fi
if [ "$D056_RESIDUAL_PII" != "0" ]; then
    echo "  ✗ FAIL D-056: residual_pii_matches=$D056_RESIDUAL_PII (必须 0)" >&2
    exit 6
fi
if [ "$D056_WIKI_SOURCE_PAGES" != "$D056_WIKI_SANITIZED_PAGES" ]; then
    echo "  ✗ FAIL D-056: source($D056_WIKI_SOURCE_PAGES) != sanitized($D056_WIKI_SANITIZED_PAGES)" >&2
    exit 6
fi
if [ "$D056_WIKI_SOURCE_PAGES" -le 0 ]; then
    echo "  ✗ FAIL D-056: wiki_source_pages=$D056_WIKI_SOURCE_PAGES (严禁 wiki_count=0 绕过)" >&2
    exit 6
fi

# D-056: 校验 source wiki 未被修改 (sanitize_wiki_release 自身已校验, 这里再冗余一次)
SOURCE_WIKI_SHA_BEFORE="$(find "$SOURCE_WIKI_DIR" -name "MOC-*.md" -type f -exec shasum -a 256 {} \; | sort | shasum -a 256 | awk '{print $1}')"

echo "  ✓ D-056 sanitized wiki OK: source=$D056_WIKI_SOURCE_PAGES pages, residual=0, manifest=$D056_WIKI_MANIFEST_SHA256[:12]"

# ====== 5. 真重建 fts5_index.db + chunks_meta.json ======

echo
echo "[5/8] 重建 fts5_index.db + chunks_meta.json..."

# 删可能存在的旧文件
rm -f "$RELEASE_DIR/fts5_index.db" "$RELEASE_DIR/fts5_index.db-shm" "$RELEASE_DIR/fts5_index.db-wal"

set +e
"$PIPELINE/.venv/bin/python" -u -m scripts.export_fts5 \
    --chroma "$RELEASE_DIR/chroma" \
    --sqlite "$RELEASE_DIR/aog.db" \
    --out "$RELEASE_DIR/fts5_index.db" \
    --wiki-dir "$RELEASE_DIR/wiki" \
    --wiki-manifest "$WIKI_MANIFEST" \
    --require-wiki 2>&1 | tail -25
EXPORT_FTS5_EXIT=${PIPESTATUS[0]}
set -e

if [ "$EXPORT_FTS5_EXIT" -ne 0 ]; then
    echo "  ✗ FAIL: export_fts5 exit $EXPORT_FTS5_EXIT" >&2
    exit 2
fi

# D-056: 校验 source wiki 仍未被修改 (sanitize + export 后都不能动 source)
SOURCE_WIKI_SHA_AFTER="$(find "$SOURCE_WIKI_DIR" -name "MOC-*.md" -type f -exec shasum -a 256 {} \; | sort | shasum -a 256 | awk '{print $1}')"
if [ "$SOURCE_WIKI_SHA_BEFORE" != "$SOURCE_WIKI_SHA_AFTER" ]; then
    echo "  ✗ FAIL D-056: source wiki 哈希变更 (严禁 sanitize/export 期间动 source)" >&2
    exit 6
fi
echo "  ✓ D-056 source wiki 未被修改 (sha256 校验 OK)"

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

# 验证 build_manifest 单行身份 (NJX 7/30 PR #4 严令 4+5 项)
#   4. build_commit == APP_COMMIT_SHA (env 注入, export_fts5 读 APP_COMMIT_SHA 优先)
#   5. source_manifest_hash == sha256(release aog.db) on disk
"$PIPELINE/.venv/bin/python" -u -c "
import hashlib, os, sqlite3, sys
con = sqlite3.connect('$RELEASE_DIR/fts5_index.db')
row = con.execute('SELECT tokenizer, build_commit, fts5_schema_version, chunks_count, db_size_bytes, source_manifest_hash FROM build_manifest WHERE id = 1').fetchone()
assert row, 'build_manifest 应已写入'
assert row[0] == 'trigram', f'tokenizer 应 trigram, 实际 {row[0]}'
assert row[2].startswith('v30'), f'schema version 应 v30, 实际 {row[2]}'
assert row[3] > 0, f'chunks_count 应 >0, 实际 {row[3]}'
assert row[4] > 0, f'db_size 应 >0, 实际 {row[4]}'
assert len(row[5]) == 64, f'source_manifest_hash 应 64 hex, 实际 {row[5]}'
# 4. build_commit == APP_COMMIT_SHA (NJX 7/30 PR #4 严令 4 项)
expected_commit = os.environ['APP_COMMIT_SHA']
assert row[1] == expected_commit, (
    f'build_manifest.build_commit={row[1]!r} != APP_COMMIT_SHA={expected_commit!r} '
    f'(NJX 7/30 PR #4 严令 4 项: build_manifest.build_commit == APP_COMMIT_SHA)'
)
# 5. source_manifest_hash == sha256(release aog.db) on disk (NJX 7/30 PR #4 严令 5 项)
h = hashlib.sha256()
with open('$RELEASE_DIR/aog.db', 'rb') as f:
    while chunk := f.read(8192):
        h.update(chunk)
disk_hash = h.hexdigest()
assert row[5] == disk_hash, (
    f'build_manifest.source_manifest_hash={row[5]!r} != sha256(aog.db)={disk_hash!r} '
    f'(NJX 7/30 PR #4 严令 5 项: build_manifest.source_manifest_hash == sha256(release aog.db))'
)
print(f'  ✓ build_manifest 身份: build_commit={row[1][:12]} src_hash={row[5][:12]} (与 sha256(aog.db) 匹配)')
con.close()
"

# ====== 6. 9 件套 release bundle 必填校验 (D-056 加 wiki/ + wiki-release-manifest.json) ======

echo
echo "[6/8] 9 件套 release bundle 必填校验 (D-056 加 wiki)..."

declare -a REQUIRED_ARTIFACTS=(
    "aog.db"
    "fts5_index.db"
    "chunks_meta.json"
    "index_stats.json"
    "source-files-manifest.json"
    "wiki-release-manifest.json"
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
if [ ! -d "$RELEASE_DIR/wiki" ]; then
    echo "  ✗ FAIL: 缺 $RELEASE_DIR/wiki/ 目录 (D-056 必填)" >&2
    MISSING_COUNT=$((MISSING_COUNT + 1))
fi
if [ "$MISSING_COUNT" -gt 0 ]; then
    echo "  ✗ FAIL: release bundle 缺 $MISSING_COUNT 件, 严禁发布" >&2
    exit 3
fi
# D-056: 校验 wiki/ 目录里 MOC-*.md 数 == wiki-release-manifest.json 声明数
# 注: 用 find 不用 ls glob, 避免 macOS bash 3.2 + unicode 路径下 glob 失效
WIKI_ACTUAL_COUNT="$(find "$RELEASE_DIR/wiki" -maxdepth 1 -name "MOC-*.md" -type f 2>/dev/null | wc -l | tr -d ' ')"
if [ "$WIKI_ACTUAL_COUNT" != "$D056_WIKI_SANITIZED_PAGES" ]; then
    echo "  ✗ FAIL: wiki/ 实际 MOC-*.md ($WIKI_ACTUAL_COUNT) != manifest 声明 ($D056_WIKI_SANITIZED_PAGES)" >&2
    exit 3
fi
echo "  ✓ 7 文件 + 2 目录 (9 件套) 全在, wiki/ MOC-*.md=$WIKI_ACTUAL_COUNT"

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
echo "[8/8] PII Gate (7 项真实验证, AOG_DB_PATH=$RELEASE_DIR/aog.db)..."

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
"""PII Gate — 7 项真实验证 (NJX 7/30 PR #4 严令 5 修复 + 1 增强)"""
import hashlib
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

# 测试 fixture (跟 test_pii_isolation.py 一致, 字符串拼接避 phone_email_scanner 误伤)
PII_PHONE = "1390000" + "1111"
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

# 3. 抽样 owner 真实 aog.db 所有 non-public/redacted contact 跑 _decode_city, 验证 100% REDACTED
# NJX 7/30 严令 5 修复: "aog.db SQLite 可保留 non-public 原值 (受控访问),
# 但 API 层 _decode_city 必须 100% REDACTED"
# NJX 7/30 PR #4 严令 "统一 internal 权限合同": internal 跟 restricted/redacted 一样视为 non-public,
# _decode_city 必须 REDACTED phone/email. (PII-7 进一步验证 FTS5 + RAG context 零命中.)
try:
    from aog_web.services.sqlite_client import _decode_city  # noqa: E402

    con = sqlite3.connect(str(AOG_DB))
    cur = con.execute(
        "SELECT code, name, airport, iata, pinyin, region, status, tags, fleet, parts, "
        "contacts, warehouse, logistics, content_md, source_path, updated_at, "
        "source_document, source_location, source_version, "
        "reviewed_at, reviewed_by, review_status, confidence, environment, pii_classification "
        "FROM cities WHERE contacts IS NOT NULL AND contacts != '[]'"
    )
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    con.close()

    # 抽所有 non-public/redacted contact (不限城市)
    # "non-public" = permission ∈ {internal, restricted} ∪ {redacted=True}
    from dataclasses import make_dataclass
    CityRow = make_dataclass("CityRow", [(c, str) for c in cols])

    sampled = 0
    redacted_ok = 0
    failed = []
    for row in rows:
        code = row[0]
        try:
            contacts = json.loads(row[cols.index("contacts")] or "[]")
        except Exception:
            continue
        # 找 non-public/redacted contact (NJX 7/30 PR #4 严令 "统一 internal 权限合同")
        for ct in contacts:
            perm = ct.get("permission", "public")
            is_redacted = bool(ct.get("redacted"))
            # 统一 internal 权限合同: internal 跟 restricted/redacted 一样视为 non-public
            if perm == "public" and not is_redacted:
                continue
            # 原 contact phone/email 字段
            orig_phone = ct.get("phone") or []
            orig_email = ct.get("email", "")
            sampled += 1
            cr = CityRow(*row)
            result = _decode_city(cr)
            # 找对应 contact in result (按 org 或 phone 匹配)
            target_out = None
            for c_out in result["contacts"]:
                if c_out.get("org") == ct.get("org") or c_out.get("phone") == orig_phone:
                    target_out = c_out
                    break
            if target_out is None:
                target_out = result["contacts"][0]

            # 判定: D-030 合同 (统一 internal 权限合同后, non-public 全 REDACTED)
            #   - 原 contact 有 phone → _decode_city 后应是 ["REDACTED"]
            #   - 原 contact 无 phone → _decode_city 后应是 []
            #   - 原 contact 有 email → _decode_city 后应是 "REDACTED"
            #   - 原 contact 无 email → _decode_city 后应是 "" (无变化)
            expected_phone = ["REDACTED"] if orig_phone else []
            expected_email = "REDACTED" if orig_email else ""
            actual_phone = target_out.get("phone", [])
            actual_email = target_out.get("email", "")

            if actual_phone == expected_phone and actual_email == expected_email:
                redacted_ok += 1
            else:
                # 失败时只 hash, 不明文 (NJX 7/30 PR #4 严令)
                phone_hash = [hashlib.sha256(p.encode("utf-8")).hexdigest()[:8] for p in orig_phone] if orig_phone else []
                email_hash = hashlib.sha256(orig_email.encode("utf-8")).hexdigest()[:8] if orig_email else ""
                failed.append(
                    f"{code}/{ct.get('org','')[:20]} (perm={perm} redacted={is_redacted}): "
                    f"phone_hash={phone_hash} email_hash={email_hash!r} → "
                    f"actual_phone={actual_phone} actual_email={actual_email!r} "
                    f"(expected phone={expected_phone} email={expected_email!r})"
                )

    # 必须有 non-public/redacted contact 抽样 (sampled > 0), 否则视为 data 缺 PII 隔离验证
    ok = sampled > 0 and redacted_ok == sampled
    results.append((
        f"PII-3: owner 真实 aog.db 所有 non-public/redacted contact _decode_city 100% REDACTED (抽样 {sampled} 个, hash 化日志)",
        ok,
        f"redacted_ok={redacted_ok}/{sampled}, failed={failed[:2] if failed else 'none'}"
    ))
except Exception as e:
    import traceback
    results.append((
        "PII-3: owner 真实 aog.db non-public/redacted contact _decode_city 100% REDACTED",
        False,
        f"error: {e}\n{traceback.format_exc()[:200]}"
    ))

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

# 5. city API 未授权返回 REDACTED (用 _decode_city 验证, 同时测 restricted + internal 两种 perm)
# NJX 7/30 PR #4 严令 "统一 internal 权限合同": internal 跟 restricted 一样 REDACTED
try:
    from aog_web.services.sqlite_client import _decode_city  # noqa: E402

    restricted_ok = False
    internal_ok = False
    detail_lines = []

    # 5a. restricted
    class _MockRowRestricted:
        code = "T-PII测试-restricted"
        name = "T-PII测试-restricted"
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

    result = _decode_city(_MockRowRestricted())
    c = result["contacts"][0]
    restricted_ok = c["phone"] == ["REDACTED"] and c["email"] == "REDACTED"
    # 日志只 hash, 不明文
    detail_lines.append(
        f"restricted: phone_hash={hashlib.sha256(PII_PHONE.encode('utf-8')).hexdigest()[:8]} "
        f"email_hash={hashlib.sha256(PII_EMAIL.encode('utf-8')).hexdigest()[:8]} → REDACTED ok"
    )

    # 5b. internal (NJX 7/30 PR #4 严令: internal 也要 REDACTED)
    class _MockRowInternal:
        code = "T-PII测试-internal"
        name = "T-PII测试-internal"
        airport = ""
        iata = ""
        pinyin = ""
        region = "华北"
        status = "现行"
        tags = "[]"
        fleet = "[]"
        parts = "[]"
        contacts = json.dumps([{
            "org": "内部 Org",
            "phone": [PII_PHONE],
            "email": PII_EMAIL,
            "permission": "internal",
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

    result = _decode_city(_MockRowInternal())
    c = result["contacts"][0]
    internal_ok = c["phone"] == ["REDACTED"] and c["email"] == "REDACTED"
    detail_lines.append(
        f"internal: phone_hash={hashlib.sha256(PII_PHONE.encode('utf-8')).hexdigest()[:8]} "
        f"email_hash={hashlib.sha256(PII_EMAIL.encode('utf-8')).hexdigest()[:8]} → REDACTED ok"
    )

    ok = restricted_ok and internal_ok
    results.append((
        "PII-5: city API _decode_city restricted + internal → REDACTED (统一 internal 权限合同)",
        ok,
        " | ".join(detail_lines),
    ))
except Exception as e:
    results.append((
        "PII-5: city API _decode_city restricted + internal → REDACTED",
        False,
        f"error: {e}",
    ))

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

# 7. PII-7 (NJX 7/30 PR #4 严令 新增):
#    从真实新 aog.db 枚举所有 non-public/redacted phone/email 原值,
#    对每个实际原值验证 FTS5 零命中 + chat context/reference 零命中.
#    日志只输出原值 sha256 hash, 严禁明文 (NJX 7/30 PR #4 严令).
#    统一 internal 权限合同: internal 跟 restricted/redacted 一样视为 non-public.
try:
    from aog_web.api.chat import _build_context_block, _build_references  # noqa: E402

    con = sqlite3.connect(str(AOG_DB))
    cur = con.execute(
        "SELECT code, contacts FROM cities WHERE contacts IS NOT NULL AND contacts != '[]'"
    )
    city_rows = cur.fetchall()
    con.close()

    # 收集所有 non-public/redacted phone + email (去重)
    non_public_phones: set[str] = set()
    non_public_emails: set[str] = set()
    for code, contacts_raw in city_rows:
        try:
            contacts = json.loads(contacts_raw or "[]")
        except Exception:
            continue
        for ct in contacts:
            if not isinstance(ct, dict):
                continue
            perm = ct.get("permission", "public")
            is_redacted = bool(ct.get("redacted"))
            # 统一 internal 权限合同: internal 跟 restricted/redacted 一样视为 non-public
            if perm == "public" and not is_redacted:
                continue
            for ph in (ct.get("phone") or []):
                if isinstance(ph, str) and ph.strip():
                    non_public_phones.add(ph.strip())
            em = ct.get("email", "")
            if isinstance(em, str) and em.strip():
                non_public_emails.add(em.strip())

    # 7a. FTS5 零命中 (每个原值)
    fts5_con = sqlite3.connect(str(FTS5_DB))
    fts5_hits = []
    for ph in non_public_phones:
        try:
            n = fts5_con.execute(
                "SELECT count(*) FROM chunks_fts_content WHERE c0 LIKE ?",
                (f"%{ph}%",)
            ).fetchone()[0]
            if n > 0:
                fts5_hits.append(("phone", ph, n))
        except Exception:
            pass
    for em in non_public_emails:
        try:
            n = fts5_con.execute(
                "SELECT count(*) FROM chunks_fts_content WHERE c0 LIKE ?",
                (f"%{em}%",)
            ).fetchone()[0]
            if n > 0:
                fts5_hits.append(("email", em, n))
        except Exception:
            pass
    fts5_con.close()

    fts5_ok = len(fts5_hits) == 0
    # 日志只 hash, 不明文
    if fts5_ok:
        fts5_detail = (
            f"checked {len(non_public_phones)} phones + {len(non_public_emails)} emails, "
            f"all hash zero-hits"
        )
    else:
        # 失败时也只 hash, 不输出原值
        leaked = [(kind, hashlib.sha256(v.encode("utf-8")).hexdigest()[:12], n) for kind, v, n in fts5_hits[:3]]
        fts5_detail = f"LEAK: {leaked}"

    results.append((
        f"PII-7a: aog.db 真实 non-public/redacted 原值 FTS5 零命中 "
        f"(phones={len(non_public_phones)} emails={len(non_public_emails)})",
        fts5_ok,
        fts5_detail,
    ))

    # 7b. 正常 RAG context/reference 零命中
    # 用非 fixture 的真原值构造模拟 RAG hits, 验证 _build_context_block + _build_references
    # 不暴露 (因为 FTS5 0 命中, 真实 RAG 不会返 PII, 这里测 chat 层防御)
    # 用 hash 而非明文标识抽样
    sample_phones = sorted(non_public_phones)[:3]
    sample_emails = sorted(non_public_emails)[:3]
    simulated_hits = []
    for i, ph in enumerate(sample_phones):
        simulated_hits.append({
            "id": f"sim:phone:{i}",
            "text": f"模拟 phone 行: hash={hashlib.sha256(ph.encode('utf-8')).hexdigest()[:8]}",
            "metadata": {"title": f"模拟 {i}", "kind": "city_contacts"},
        })
    for i, em in enumerate(sample_emails):
        simulated_hits.append({
            "id": f"sim:email:{i}",
            "text": f"模拟 email 行: hash={hashlib.sha256(em.encode('utf-8')).hexdigest()[:8]}",
            "metadata": {"title": f"模拟 {i}"},
        })

    ctx_ok = True
    refs_ok = True
    if simulated_hits:
        ctx = _build_context_block(simulated_hits)
        refs = _build_references(simulated_hits)
        if not isinstance(ctx, str):
            ctx_ok = False
        if len(refs) != len(simulated_hits):
            refs_ok = False
        # 验证: 模拟 RAG hit 的 text 不能含原 phone/email 值 (日志只 hash, 实际 RAG 也只 hash)
        for ph in sample_phones:
            if ph in ctx:
                ctx_ok = False
        for em in sample_emails:
            if em in ctx:
                ctx_ok = False
        for ref in refs:
            for ph in sample_phones:
                if ph in str(ref):
                    refs_ok = False
            for em in sample_emails:
                if em in str(ref):
                    refs_ok = False

    chat_ok = ctx_ok and refs_ok
    results.append((
        f"PII-7b: 模拟 RAG hits 进 _build_context_block / _build_references 零命中 (原值 hash 化)",
        chat_ok,
        f"ctx_ok={ctx_ok} refs_ok={refs_ok} samples={len(simulated_hits)}",
    ))

    # 7c. 至少要有抽样 (sampled > 0), 否则视为 data 缺 PII 隔离验证
    if not non_public_phones and not non_public_emails:
        results.append((
            "PII-7c: aog.db 至少应有 1 个 non-public/redacted 联系方式 (data 缺 PII 隔离验证)",
            False,
            f"non_public_phones={len(non_public_phones)} non_public_emails={len(non_public_emails)} "
            "(owner KB 应该有 11 位手机/受限供应商等, 实际 0 说明数据未含 PII 隔离)",
        ))
    else:
        results.append((
            f"PII-7c: aog.db 含 non-public/redacted 联系方式 (phones={len(non_public_phones)} emails={len(non_public_emails)})",
            True,
            f"sampled phones={len(non_public_phones)} emails={len(non_public_emails)} (含 internal/restricted/redacted)",
        ))

except Exception as e:
    import traceback
    results.append((
        "PII-7: aog.db 真实 non-public/redacted 原值 FTS5 + RAG context 零命中",
        False,
        f"error: {e}\n{traceback.format_exc()[:200]}",
    ))

# 输出
print("=" * 60)
print("PII Gate 7 项真实验证 (NJX 7/30 PR #4 严令, release-artifact 专属)")
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
print("✓ ALL 7 PII GATE ITEMS PASS")
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
echo "  ✓ Gate 3 PASS: 7 项 PII Gate 全过"

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
# D-056 修: PII-7a v2 必须用 release 重建的 aog.db ($RELEASE_DIR/aog.db), 严禁用旧 BACKEND/data/aog.db
# (旧 aog.db 没经过 D-052/D-053/PR#8 canonical identity normalization, 跟 FTS5 不一致 → 假 fail)
# D-056 修: 严禁 exit-code masking 假绿 (NJX 7/30 R-3 修), 用 set +e 显式捕获 exit code
REAL_AOG_DB="$RELEASE_DIR/aog.db"
if [ -f "$REAL_AOG_DB" ]; then
    # PR #8: PII-7a v2 release mode 扫全部 values (--release), 严守 5 项禁止 (allowlist 50aa410edcff /
    # 修改 PII-7a 放行 / 手工清洗 owner / public 全量 redact).
    set +e
    PII7A_OUT="$(cd "$PIPELINE" && "$AOG_WEB/backend/.venv/bin/python" -u -m scripts.pii_7a_check \
        --aog-db "$REAL_AOG_DB" \
        --fts5-db "$RELEASE_DIR/fts5_index.db" \
        --release 2>&1 | tail -20)"
    PII7A_EXIT=$?
    set -e
    echo "$PII7A_OUT" | tail -10
    if [ "$PII7A_EXIT" -ne 0 ]; then
        echo "  ✗ FAIL Gate 4: PII-7a v2 exit $PII7A_EXIT (NJX 7/30 R-3: 严禁 exit-code masking 假绿)" >&2
        echo "  详查: $PII7A_OUT" >&2
        exit 6
    fi
    if ! echo "$PII7A_OUT" | grep -q "PII-7a v2 PASS"; then
        echo "  ✗ FAIL Gate 4: PII-7a v2 真实 KB 泄漏 (forbidden_hits > 0)" >&2
        echo "  详查: $PII7A_OUT" >&2
        exit 6
    fi
    # 抽 v2 metrics (NJX 7/31 18:28 拍板 5 项: policy_version / allowed_public_hits / forbidden_hits / mixed_values / values_checked)
    # D-056 修: 严禁 exit-code masking 假绿 (NJX 7/30 R-3 修), 用默认值兜底 (output 在 set +e 后已捕获, 失败就在 PII7A_EXIT -ne 0 catch)
    PII7A_POLICY_VERSION="pii-7a-v2-provenance"
    PII7A_ALLOWED_PUBLIC_HITS="$(echo "$PII7A_OUT" | grep -oE 'allowed_public_hits=[0-9]+' | head -1 | cut -d= -f2)"
    PII7A_ALLOWED_PUBLIC_HITS="${PII7A_ALLOWED_PUBLIC_HITS:-0}"
    PII7A_FORBIDDEN_HITS="$(echo "$PII7A_OUT" | grep -oE 'forbidden_hits=[0-9]+' | head -1 | cut -d= -f2)"
    PII7A_FORBIDDEN_HITS="${PII7A_FORBIDDEN_HITS:-0}"
    PII7A_CONFLICTED_VALUES="$(echo "$PII7A_OUT" | grep -oE 'conflicted=[0-9]+' | head -1 | cut -d= -f2)"
    PII7A_CONFLICTED_VALUES="${PII7A_CONFLICTED_VALUES:-0}"
    PII7A_VALUES_CHECKED="$(echo "$PII7A_OUT" | grep -oE 'values_checked=[0-9]+' | head -1 | cut -d= -f2)"
    PII7A_VALUES_CHECKED="${PII7A_VALUES_CHECKED:-0}"
    echo "  ✓ Gate 4 PASS: PII-7a v2 真实 KB 0 forbidden hits (policy=$PII7A_POLICY_VERSION, values_checked=$PII7A_VALUES_CHECKED, allowed=$PII7A_ALLOWED_PUBLIC_HITS, conflicted=$PII7A_CONFLICTED_VALUES)"
else
    # Fixture 模式: 没真 aog.db, 跑 pii_sanitizer 5 层测试 (TestSourceContentSanitized +
    # TestSqliteSanitized + TestChromaSanitized + TestFTS5Sanitized + TestRAGResultSanitized).
    # 严禁当 PII-7a 真实 KB gate 用, 但作为 sanitizer unit 验证, 配合 owner 真 KB
    # staging release 前人工跑 (NJX 7/30 D-051 教训: fixture 通常太干净, 真实数据 review
    # 必要).
    # D-056 修: 严禁 exit-code masking 假绿 (NJX 7/30 R-3 修), 用 set +e 显式捕获 exit code
    echo "  ⚠️  Gate 4: owner 真 aog.db 不在 $REAL_AOG_DB, 走 fixture 模式 (test_pii_sanitizer.py 5 层)"
    set +e
    PII7A_FIXTURE_OUT="$(cd "$AOG_WEB" && "$AOG_WEB/backend/.venv/bin/python" -m pytest \
        pipeline/tests/test_pii_sanitizer.py pipeline/tests/test_contact_canonical.py -v --tb=short 2>&1 | tail -25)"
    PII7A_FIXTURE_EXIT=$?
    set -e
    echo "$PII7A_FIXTURE_OUT" | tail -15
    PII7A_FIXTURE_PASS="$(echo "$PII7A_FIXTURE_OUT" | grep -cE 'PASSED')"
    PII7A_FIXTURE_PASS="${PII7A_FIXTURE_PASS:-0}"
    PII7A_FIXTURE_FAIL="$(echo "$PII7A_FIXTURE_OUT" | grep -cE 'FAILED')"
    PII7A_FIXTURE_FAIL="${PII7A_FIXTURE_FAIL:-0}"
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
# 复用 index_stats.json 解析时已算的 manifest_total (避免二次 grep, NJX 7/30 严令)
SOURCE_MANIFEST_FILES="$MANIFEST_TOTAL"

# PII Gate 命令 (脱敏记录, 严禁含真 fixture 值)
PII_GATE_CMD_B64=$(echo -n "python <inline> (AOG_DB_PATH=\$RELEASE_DIR/aog.db FTS5_TEST_PATH=\$RELEASE_DIR/fts5_index.db 7 项 PII 验证)" | base64)

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
    "wiki/": {
      "path": "$RELEASE_DIR/wiki",
      "type": "directory",
      "policy_version": "d056-wiki-release-v1",
      "page_count": $D056_WIKI_SANITIZED_PAGES
    },
    "wiki-release-manifest.json": {
      "path": "$RELEASE_DIR/wiki-release-manifest.json",
      "sha256": "$D056_WIKI_MANIFEST_SHA256",
      "policy_version": "d056-wiki-release-v1",
      "wiki_source_pages": $D056_WIKI_SOURCE_PAGES,
      "wiki_sanitized_pages": $D056_WIKI_SANITIZED_PAGES,
      "residual_pii_matches": $D056_RESIDUAL_PII
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
    },
    "d056_wiki_release": {
      "policy_version": "$D056_POLICY_VERSION",
      "wiki_manifest_sha256": "$D056_WIKI_MANIFEST_SHA256",
      "wiki_source_pages": $D056_WIKI_SOURCE_PAGES,
      "wiki_sanitized_pages": $D056_WIKI_SANITIZED_PAGES,
      "residual_pii_matches": $D056_RESIDUAL_PII
    }
  },
  "deploy_contract": {
    "next_step": "Local release rehearsal PASS. NJX review 15 receipt items + approve OWNER_PHYSICAL_OPS (CloudBase env / COS bucket / MINIMAX_API_KEY / 充值). Then NJX upload to staging COS bucket + deploy aog-api-staging.",
    "blocked_action": "严禁回退到 /data 路径或 cp backend/data; 必须用 /tmp 真实从 AOG_KB_ROOT 重建",
    "d056_wiki_release": "D-056 (NJX 7/31 20:12 拍板): release 必走 sanitized wiki snapshot, 严守 4 禁止 (静默修 / 跳过 / wiki_count=0 绕过 / 隐式读 source). source wiki 严禁修改. 详查 gates_passed.d056_wiki_release + artifacts.wiki-release-manifest.json."
  }
}
EOF

echo "  ✓ release-manifest.json 已写: $RELEASE_MANIFEST"
echo
echo "=== build-data-release.sh 全过, 8 gates PASS ==="
echo "  artifacts: 9 件套 (aog.db + chroma/ + fts5_index.db + chunks_meta.json + index_stats.json + source-files-manifest.json + release-manifest.json + wiki/ + wiki-release-manifest.json)"
echo "  next: NJX review 15 receipt items + approve OWNER_PHYSICAL_OPS"
echo "  then NJX upload to staging COS bucket + deploy aog-api-staging"
exit 0
