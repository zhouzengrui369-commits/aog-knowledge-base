#!/usr/bin/env python3
"""denylist_check.py — staging denylist 严格检查 (NJX 7/29 严令)

从 ops/production-resource-denylist.json 读 production 4 项 denylist, 严格检查 staging 文件不含:
  - production envId
  - production function name
  - production bucket
  - production domain

排除: # 注释行 + ops/production-resource-denylist.json 文件本身 (作为 denylist reference)
排除: 合法 staging 后缀 (aog-api-staging / aog-staging.njx.com), 用 word boundary + negative lookahead

用法:
  python3 scripts/denylist_check.py FILE [FILE ...]
  exit 0 = 0 production 命中
  exit 1 = 有 production 命中
  exit 2 = 配置错误 (denylist 文件不存在 / JSON 解析错)
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DENYLIST_RC = REPO_ROOT / "ops" / "production-resource-denylist.json"


def load_denylist() -> dict:
    """从 ops/production-resource-denylist.json 读 production 4 项"""
    if not DENYLIST_RC.exists():
        print(f"FAIL: {DENYLIST_RC} 不存在", file=sys.stderr)
        sys.exit(2)
    try:
        data = json.loads(DENYLIST_RC.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL: {DENYLIST_RC} JSON 解析错: {e}", file=sys.stderr)
        sys.exit(2)
    # 必须含 _isolated_for_staging_denylist_only: true
    if not data.get("_isolated_for_staging_denylist_only"):
        print(f"FAIL: {DENYLIST_RC} 缺 _isolated_for_staging_denylist_only: true 标记", file=sys.stderr)
        sys.exit(2)
    return {
        "envId": data.get("envId", ""),
        "function_name": data.get("function_name", ""),
        "bucket": data.get("bucket", ""),
        "domain": data.get("domain", ""),
    }


def check_file(path: Path, denylist: dict) -> list:
    """返回 (line_no, line, label) 命中的所有 production 引用"""
    hits = []
    if not path.exists():
        return [(0, f"FILE_NOT_FOUND: {path}")]

    # 排除 ops/production-resource-denylist.json 本身 (作为 denylist reference)
    if path.resolve() == DENYLIST_RC.resolve():
        return []

    # 排除 xxx-STAGING 占位符行 (.env.staging.example / cloudbaserc.staging.json 用)
    placeholder = re.compile(r"xxx-STAGING|\{\{env\.")

    # 排除 # 注释行
    # 排除合法 staging 后缀 (aog-api-staging / aog-staging.njx.com), 用 word boundary + negative lookahead
    # 排除路径分隔符 / 后的引用 (read 引用, 如 "$AOG_WEB/functions/aog-api/", 是 staging prepare copy handler 用, 不算 deploy 引用)
    envId_re = re.compile(re.escape(denylist["envId"])) if denylist["envId"] else None
    function_re = re.compile(r"\b" + re.escape(denylist["function_name"]) + r"\b(?![-/])") if denylist["function_name"] else None
    bucket_re = re.compile(re.escape(denylist["bucket"])) if denylist["bucket"] else None
    domain_re = re.compile(re.escape(denylist["domain"]) + r"(?!-staging)") if denylist["domain"] else None

    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # 排除 # 注释
        if line.strip().startswith("#"):
            continue
        # 排除 {{env.*}} 占位符
        if placeholder.search(line):
            continue
        # 检查 4 项
        for label, regex in [
            ("envId", envId_re),
            ("function", function_re),
            ("bucket", bucket_re),
            ("domain", domain_re),
        ]:
            if regex and regex.search(line):
                hits.append((i, line, label))
                break  # 1 行只报 1 命中
    return hits


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} FILE [FILE ...]", file=sys.stderr)
        sys.exit(2)

    denylist = load_denylist()
    error = 0
    for f in sys.argv[1:]:
        path = Path(f).resolve()
        hits = check_file(path, denylist)
        if hits:
            for line_no, line, label in hits:
                print(f"  ✗ {f}:L{line_no} ({label}): {line.strip()}")
            error += 1
        else:
            print(f"  ✓ {f}")
    if error:
        print(f"\n  ✗ denylist check FAIL: {error} files 含 production 引用")
        sys.exit(1)
    print(f"\n  ✓ denylist check 全过")
    sys.exit(0)


if __name__ == "__main__":
    main()
