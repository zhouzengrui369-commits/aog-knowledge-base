#!/usr/bin/env python3
"""denylist_check.py — staging denylist 严格检查 (NJX 7/29 严令)

从 cloudbaserc.production.json 读 production 4 项 denylist, 严格检查 staging 文件不含:
  - production envId (njx-copilot-d6gs7642f8fa17122)
  - production function (aog-api)
  - production bucket (aog-prod-data-1343051603)
  - production domain (aog.njx.com)

排除: # 注释行 + cloudbaserc.production.json 文件本身 (作为 denylist reference)

用法:
  python3 scripts/denylist_check.py FILE [FILE ...]
  exit 0 = 0 production 命中
  exit 1 = 有 production 命中
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROD_RC = REPO_ROOT / "cloudbaserc.production.json"


def load_denylist() -> dict:
    """从 cloudbaserc.production.json 读 production 4 项"""
    if not PROD_RC.exists():
        print(f"FAIL: {PROD_RC} 不存在", file=sys.stderr)
        sys.exit(2)
    try:
        data = json.loads(PROD_RC.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL: {PROD_RC} JSON 解析错: {e}", file=sys.stderr)
        sys.exit(2)
    return {
        "envId": data.get("envId", ""),
        "function_name": data.get("function", {}).get("name", ""),
        "bucket": data.get("storage", {}).get("bucket", ""),
        "domain": data.get("hosting", {}).get("domain", ""),
    }


def check_file(path: Path, denylist: dict) -> list:
    """返回 (line_no, line) 命中的所有 production 引用"""
    hits = []
    if not path.exists():
        return [(0, f"FILE_NOT_FOUND: {path}")]

    # 排除 cloudbaserc.production.json 本身 (作为 denylist reference, 必须含 production 4 项)
    if path == PROD_RC:
        return []

    # 排除 xxx-STAGING 占位符行 (.env.staging.example 用)
    placeholder = re.compile(r"xxx-STAGING")

    # 排除 cloudbaserc.staging.json 含 "STAGING" 标识
    is_staging_config = path.name == "cloudbaserc.staging.json" or path.name == ".env.staging.example"

    # 排除 # 注释行 + 含 "aog-api-staging" 的引用 (合法 staging 引用)
    # 注: aog-api 单独匹配 production function name, 但 aog-api-staging 是合法 staging function
    envId_re = re.compile(re.escape(denylist["envId"])) if denylist["envId"] else None
    function_re = re.compile(r"\b" + re.escape(denylist["function_name"]) + r"\b(?!-staging)") if denylist["function_name"] else None
    bucket_re = re.compile(re.escape(denylist["bucket"])) if denylist["bucket"] else None
    domain_re = re.compile(re.escape(denylist["domain"])) if denylist["domain"] else None

    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # 排除 # 注释
        if line.strip().startswith("#"):
            continue
        # 排除 xxx-STAGING 占位符
        if is_staging_config and placeholder.search(line):
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
