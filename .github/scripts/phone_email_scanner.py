#!/usr/bin/env python3
"""phone_email_scanner.py — Repository PII 扫描器 (Owner 7/29 严令)

扫描整个 git 仓库, 找出:
  - 真实手机号 (11 位 1[3-9]xx, 在中国)
  - 真实邮箱 (非 example/test/fixture/localhost/openclaw.local 域)

按 Owner 7/29 严令:
  1. 只扫明确文本扩展 (.py .ts .tsx .js .jsx .json .yaml .yml .md .txt .env .sh)
  2. 用 git grep -I 排除二进制 (无需 try/except)
  3. 即便用文本扩展白名单, 仍 catch UnicodeDecodeError (防御性, 因为 .txt 也可能含二进制)
     → 标 skipped_binary, 不静默跳过源代码
  4. 输出 4 类计数: scanned_text_files / skipped_binary_files / fixture_allowlisted_files / findings
  5. findings > 0 → exit 1 (CI fail)
  6. scanner 自身异常 (e.g. git 失败) → exit 2 (独立错误码)

排除 fixture / data:
  - tests/ 目录 (frontend + backend + pipeline)
  - lib/mock/ (frontend dev mockup data)
  - aog-web/AOG知识库/ (知识库原始 docx/md, read-only 数据源)
  - DELIVERY-*.md / reports/ (历史交付物, 含过往真实 PII 截图记录)
  - 文件名含 'fixture' (大小写不敏感)

运行:
  python3 .github/scripts/phone_email_scanner.py
  exit 0 = OK, 1 = 发现真实 PII, 2 = scanner 内部错误
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# 文本扩展白名单 (Owner 7/29 严令: 只扫明确文本扩展, 不扫二进制)
TEXT_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".md", ".txt", ".env", ".sh"}

# 真实手机号 (中国 11 位 1[3-9]xxxxxxxxx, 必须 11 位)
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

# 真实邮箱 (排除 fixture / example / test / localhost / openclaw.local 域)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_ALLOWLIST_TLDS = ("example", "test", "fixture", "localhost", "openclaw.local")
EMAIL_ALLOWLIST_DOMAINS = (
    "example.com", "example.org", "example.net",
    "test.com", "test.org", "test.local",
    "fixture.com", "fixture.example",
    "localhost", "openclaw.local",
    "izs.me",  # ★ npm registry owner email (Isaac Schlueter), 出现在 pnpm-lock.yaml 是合法的
)

# fixture 路径前缀 (Owner 7/29 严令: 显式 allowlist)
FIXTURE_PATH_PREFIXES = (
    "aog-web/pipeline/tests/",
    "aog-web/backend/tests/",
    "aog-web/frontend/tests/",
    "aog-web/frontend/lib/mock/",  # dev mockup fixture
    "aog-web/mockup/",              # ★ Sprint C 之前的 dev mockup, 已被 lib/mock/ 取代, 仅作历史归档
    "aog-web/AOG知识库/",  # read-only 知识库数据源 (D-029)
    "AOG知识库/",            # ★ 根目录知识库 (scanner prefix 不区分 aog-web/ 子目录)
    "aog-web/DELIVERY-",
    "aog-web/reports/",
    "aog-web/functions/",  # SCF 已 build 产物
    "aog-web/pipeline/data/",  # RAG 生成数据 (wiki/.meta.json 等)
    "aog-web/backend/data/",   # Chroma + FTS5 binary 索引
    "aog-web/frontend/.next/", # Next.js 编译 cache
    "aog-web/frontend/.next.died/",  # ★ 之前误 commit 的 .next.died 编译产物
    "reports/",
)


def _is_fixture_path(path: str) -> bool:
    """判断是否 fixture / data 路径 (allowlist)"""
    for prefix in FIXTURE_PATH_PREFIXES:
        if path.startswith(prefix):
            return True
    if "fixture" in path.lower():
        return True
    # .next.died/ (Next.js compile cache, 不应入仓)
    if "/.next.died/" in path or path.endswith("/.next.died"):
        return True
    # .venv / node_modules / dist / out
    base = Path(path)
    if any(p in base.parts for p in (".venv", "node_modules", "dist", "out", "__pycache__", "vendor")):
        return True
    return False


def _is_text_file(path: str) -> bool:
    """判断是否文本扩展白名单内的文件"""
    return Path(path).suffix.lower() in TEXT_EXTS


def _is_email_allowed(email: str) -> bool:
    """真实邮箱 vs fixture email 域判断"""
    email_lower = email.lower()
    for tld in EMAIL_ALLOWLIST_TLDS:
        if tld in email_lower:
            return True
    for d in EMAIL_ALLOWLIST_DOMAINS:
        if email_lower.endswith("@" + d) or email_lower == d:
            return True
    return False


def _git_ls_files(cwd: str | None = None) -> list[str]:
    """列出所有 git tracked files, 默认 cwd (subprocess 继承)"""
    try:
        r = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, check=True, timeout=30,
            cwd=cwd,
        )
    except subprocess.CalledProcessError as e:
        print(f"[scanner internal error] git ls-files failed: {e}", file=sys.stderr)
        sys.exit(2)
    except subprocess.TimeoutExpired:
        print("[scanner internal error] git ls-files timeout", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:
        # git 不在 PATH 或 不可执行 — scanner 自身异常, 独立错误码 2
        print(f"[scanner internal error] git executable not found: {e}", file=sys.stderr)
        sys.exit(2)
    return [f for f in r.stdout.splitlines() if f]


def _read_text_file(path: str) -> str | None:
    """读文本文件, 捕获 UnicodeDecodeError → 标 None (调用方记 skipped_binary)"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        return None
    except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
        # 文件找不到/是目录/无权限, scanner 不当作 binary, 跳过即可
        print(f"[scanner skip] {path}: {type(e).__name__}", file=sys.stderr)
        return None


def scan(repo_root: str | None = None) -> dict:
    """主扫描逻辑, 返回结果 dict

    Returns:
        {
            "scanned_text_files": int,
            "skipped_binary_files": int,
            "skipped_fixture_files": int,
            "findings": [{"file": str, "type": "phone"|"email", "match": str}, ...],
            "internal_error": str | None,
        }
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    files = _git_ls_files(cwd=str(root))

    scanned_text = 0
    skipped_binary = 0
    skipped_fixture = 0
    findings: list[dict] = []

    for f in files:
        if _is_fixture_path(f):
            skipped_fixture += 1
            continue
        if not _is_text_file(f):
            continue
        full = root / f
        content = _read_text_file(str(full))
        if content is None:
            # 可能是 binary 或 IO 错误, 计入 skipped_binary
            skipped_binary += 1
            continue
        scanned_text += 1
        # 真实手机号
        for m in PHONE_RE.findall(content):
            findings.append({"file": f, "type": "phone", "match": m})
        # 真实邮箱 (排除 fixture 域)
        for m in EMAIL_RE.findall(content):
            if not _is_email_allowed(m):
                findings.append({"file": f, "type": "email", "match": m})

    return {
        "scanned_text_files": scanned_text,
        "skipped_binary_files": skipped_binary,
        "skipped_fixture_files": skipped_fixture,
        "findings": findings,
        "internal_error": None,
    }


def main() -> int:
    repo_root = os.environ.get("REPO_ROOT", ".")
    try:
        result = scan(repo_root=repo_root)
    except Exception as e:
        # scanner 自身异常 (e.g. git 不可用, 文件权限) — 独立错误码
        print(f"[scanner internal error] {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    print(f"[scanner] scanned_text_files={result['scanned_text_files']}")
    print(f"[scanner] skipped_binary_files={result['skipped_binary_files']}")
    print(f"[scanner] skipped_fixture_files={result['skipped_fixture_files']}")
    print(f"[scanner] findings={len(result['findings'])}")

    if result["findings"]:
        for f in result["findings"]:
            print(f"  - {f['file']}: {f['type']}={f['match']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
