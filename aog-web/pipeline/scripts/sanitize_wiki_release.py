#!/usr/bin/env python3
"""sanitize_wiki_release.py — release snapshot sanitizer for wiki pages (D-056)

NJX 7/31 20:12 拍板 D-056_WIKI_RELEASE_SNAPSHOT_BYPASS:
  根因: wiki_curator 只对新生成页面 sanitize, 旧 MOC-*.md 仍含 owner 写的
        phone 原值 (e.g. 海航总部 0898-65987130/68875172/31); export_fts5.py
        直接读 pipeline/data/wiki/ 原文写 FTS5, 触发 PII-7a v2 3 hit fail.

  修法: release 阶段先构建 sanitized wiki snapshot
        - source wiki 只读 (绝不修改 pipeline/data/wiki/*.md)
        - 输出 $RELEASE_DIR/wiki/MOC-{code}-{topic}.md
        - sanitize body + 自由文本 metadata
        - 输出 wiki-release-manifest.json (含 sha256, source_pages, sanitized_pages,
                                           residual_pii_matches)
        - residual PII 必须 0 (sanitize 前后 diff 任一含 phone/email 原值 → FAIL)
        - source/output page count 必须一致 (绝不允许漏处理)

  此脚本为 release 专用. 严禁在 release 路径调 LLM (wiki_curator) 或静默修.

Usage:
  python -m scripts.sanitize_wiki_release \\
      --source-wiki <KB_ROOT>/pipeline/data/wiki \\
      --release-dir <RELEASE_DIR>

输出:
  <RELEASE_DIR>/wiki/MOC-*.md
  <RELEASE_DIR>/wiki-release-manifest.json

退出码:
  0 = success (residual_pii_matches=0, page count 一致)
  4 = residual PII > 0 (fail)
  5 = source/output page count 不一致
  6 = source wiki 不存在 / 为空
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("sanitize_wiki_release")

# 复用 pii_sanitizer 严令 5: phone + email patterns
# 注: 不依赖 pipeline.extractors (避免 import cycle), 直接复制严令 pattern
# D-051 + D-052 + D-053 合并后的严令 (PR #5/6/7 merged)
PHONE_PATTERNS = [
    # 1. 11 位手机 (1[3-9]xxxxxxxxx)
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    # 2. + 国家码 - 区号 - 号码
    re.compile(r"(?<!\d)\+\d{1,3}[\-\.]\d{1,4}[\-\.]\d{3,4}[\-\.]\d{3,4}(?!\d)"),
    # 3. 座机 0xx-xxxx-xxxx / 0xxx-xxxxxxxx
    re.compile(r"(?<!\d)0\d{2,3}[\-\.]\d{7,8}(?!\d)"),
    # 4. 短横线 phone 0X-XXXXXXX
    re.compile(r"(?<!\d)0\d{1,2}[\-\.]\d{7,8}(?!\d)"),
    # 5. 国际 00 + 1-3位区号 + 7-8位号码 (D-053 加)
    re.compile(r"(?<!\d)00\d{1,3}[\-\.]\d{7,8}(?!\d)"),
    # 6. 国际 00 + 1-4位区号 (括号) + 7-8位号码
    re.compile(r"(?<!\d)00\(\d{1,4}\)\d{6,}(?!\d)"),
    # 7. 通用 7+ 连续数字 phone
    re.compile(r"(?<!\d)\d{7,12}(?!\d)"),
]
EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._-])"
    r"[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\."
    r"[A-Za-z]{2,}"
)

PHONE_REDACTED = "[PHONE_REDACTED]"
EMAIL_REDACTED = "[EMAIL_REDACTED]"

# 严守: frontmatter 里所有 string 字段都 sanitize (除了 code/name/topic 这些纯标识)
# 安全 metadata 字段 (纯 ASCII 标识, 不可能含 PII)
SAFE_METADATA_KEYS = {"code", "name", "topic", "generated_at", "llm", "chars"}


def sanitize_text(text: str) -> str:
    """对单段文本 sanitize (phone + email → [PHONE_REDACTED] / [EMAIL_REDACTED]).

    注: 与 pipeline.extractors.pii_sanitizer.sanitize_text 行为一致,
    但作为 release 独立副本, 严守不依赖 extractor 链 (避免循环 import).
    """
    if not text:
        return text
    text = EMAIL_PATTERN.sub(EMAIL_REDACTED, text)
    for pat in PHONE_PATTERNS:
        text = pat.sub(PHONE_REDACTED, text)
    return text


def find_residual_pii(text: str) -> List[Tuple[str, str]]:
    """扫 text 内仍含的 phone/email 原值 (sanitize 后应为空).

    Returns: list of (kind, value) where kind in {'phone', 'email'}.
    """
    if not text:
        return []
    found: List[Tuple[str, str]] = []
    for m in EMAIL_PATTERN.finditer(text):
        found.append(("email", m.group(0)))
    for pat in PHONE_PATTERNS:
        for m in pat.finditer(text):
            v = m.group(0)
            # 跳过 [PHONE_REDACTED] marker 自身
            if v == PHONE_REDACTED:
                continue
            found.append(("phone", v))
    return found


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """简陋 YAML frontmatter parser (只支持 key: value 单行 + 字符串值).

    Returns: (frontmatter dict, body)
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    fm: Dict[str, str] = {}
    for line in fm_block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, body


def write_frontmatter(fm: Dict[str, str]) -> str:
    """frontmatter dict → --- 块."""
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def process_wiki_file(
    src: Path,
    out_dir: Path,
) -> Dict:
    """处理 1 个 wiki 源文件: sanitize body + 自由文本 metadata → 写 $out_dir.

    Returns: dict with keys
        - source_sha256 (源文件 sha256)
        - output_sha256 (sanitized 输出 sha256)
        - frontmatter_residual_pii (list of (k, kind, value))
        - body_residual_pii (list of (kind, value))
        - body_chars_in / body_chars_out
    """
    raw = src.read_text(encoding="utf-8", errors="ignore")
    src_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    fm, body = parse_frontmatter(raw)

    # sanitize frontmatter free-text fields
    fm_sanitized: Dict[str, str] = {}
    fm_residual: List[Tuple[str, str, str]] = []
    for k, v in fm.items():
        if k in SAFE_METADATA_KEYS:
            fm_sanitized[k] = v
        else:
            sanitized = sanitize_text(v)
            fm_sanitized[k] = sanitized
            # 严守: 检 residual
            for kind, val in find_residual_pii(sanitized):
                fm_residual.append((k, kind, val))

    # sanitize body
    body_sanitized = sanitize_text(body)
    body_residual = find_residual_pii(body_sanitized)

    # 写输出
    out_path = out_dir / src.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_content = write_frontmatter(fm_sanitized) + body_sanitized
    out_path.write_text(out_content, encoding="utf-8")
    out_sha = hashlib.sha256(out_content.encode("utf-8")).hexdigest()

    return {
        "source_path": str(src),
        "output_path": str(out_path),
        "source_sha256": src_sha,
        "output_sha256": out_sha,
        "frontmatter_residual_pii": fm_residual,
        "body_residual_pii": body_residual,
        "body_chars_in": len(body),
        "body_chars_out": len(body_sanitized),
    }


def build_wiki_release(
    source_wiki: Path,
    release_dir: Path,
) -> Dict:
    """D-056 主流程: source wiki 只读 → $RELEASE_DIR/wiki + manifest.

    严守:
      - source wiki 绝不修改
      - source/output page count 必须一致
      - residual_pii_matches 必须 0
    """
    if not source_wiki.exists():
        logger.error("source_wiki not found: %s", source_wiki)
        sys.exit(6)
    if not source_wiki.is_dir():
        logger.error("source_wiki not a directory: %s", source_wiki)
        sys.exit(6)

    md_files = sorted(source_wiki.glob("MOC-*.md"))
    if not md_files:
        logger.error("no MOC-*.md in %s", source_wiki)
        sys.exit(6)

    # 记录源 wiki 状态 sha (校验 release 后 source 未被修改)
    source_state_before: Dict[str, str] = {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in md_files
    }
    source_count = len(md_files)
    logger.info("source wiki: %s (%d MOC-*.md pages)", source_wiki, source_count)

    # 输出目录: $RELEASE_DIR/wiki
    out_dir = release_dir / "wiki"
    if out_dir.exists():
        logger.error("out_dir already exists: %s (严禁覆盖)", out_dir)
        sys.exit(6)
    out_dir.mkdir(parents=True, exist_ok=False)

    # 处理每个 wiki 文件
    page_results: List[Dict] = []
    total_residual = 0
    for src in md_files:
        try:
            r = process_wiki_file(src, out_dir)
        except Exception as e:
            logger.error("process failed: %s: %s", src, e)
            sys.exit(4)
        total_residual += len(r["frontmatter_residual_pii"]) + len(r["body_residual_pii"])
        page_results.append(r)

    # 校验 source 未被修改
    source_state_after: Dict[str, str] = {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in md_files
    }
    source_modified = [
        name
        for name in source_state_before
        if source_state_before[name] != source_state_after.get(name)
    ]
    if source_modified:
        logger.error("SOURCE WIKI MODIFIED (严禁): %s", source_modified)
        sys.exit(5)

    # 校验 source/output page count 一致
    out_files = sorted(out_dir.glob("MOC-*.md"))
    sanitized_count = len(out_files)
    if sanitized_count != source_count:
        logger.error(
            "page count 不一致: source=%d, sanitized=%d (严禁漏处理)",
            source_count,
            sanitized_count,
        )
        # 清理 out_dir (避免脏 release)
        shutil.rmtree(out_dir)
        sys.exit(5)

    # 写 wiki-release-manifest.json
    manifest = {
        "policy_version": "d056-wiki-release-v1",
        "build_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_wiki_dir": str(source_wiki),
        "output_wiki_dir": str(out_dir),
        "wiki_source_pages": source_count,
        "wiki_sanitized_pages": sanitized_count,
        "residual_pii_matches": total_residual,
        "source_unmodified": len(source_modified) == 0,
        "pages": page_results,
    }
    manifest_path = release_dir / "wiki-release-manifest.json"
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()

    logger.info("=" * 60)
    logger.info("wiki release snapshot 已构建:")
    logger.info("  source wiki:        %s (%d pages)", source_wiki, source_count)
    logger.info("  output wiki:        %s (%d pages)", out_dir, sanitized_count)
    logger.info("  residual_pii:       %d", total_residual)
    logger.info("  source_unmodified:  %s", "yes" if not source_modified else "NO (FAIL)")
    logger.info("  manifest:           %s", manifest_path)
    logger.info("  manifest sha256:    %s", manifest_sha)
    logger.info("=" * 60)

    # FAIL: residual PII > 0
    if total_residual > 0:
        # 详查: 列出所有 residual
        leaked_pages = [r for r in page_results if r["body_residual_pii"] or r["frontmatter_residual_pii"]]
        for lp in leaked_pages[:5]:
            logger.error("  residual in %s: fm=%s, body=%s", lp["source_path"], lp["frontmatter_residual_pii"], lp["body_residual_pii"])
        sys.exit(4)

    # OK
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "wiki_source_pages": source_count,
        "wiki_sanitized_pages": sanitized_count,
        "residual_pii_matches": total_residual,
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description="D-056: 构建 sanitized wiki release snapshot (source-only, RELEASE_DIR/wiki/)"
    )
    p.add_argument(
        "--source-wiki",
        type=Path,
        required=True,
        help="source wiki 目录 (e.g. <KB_ROOT>/aog-web/pipeline/data/wiki/)",
    )
    p.add_argument(
        "--release-dir",
        type=Path,
        required=True,
        help="release 目录 (e.g. /tmp/aog-release-XXX), 输出 $release_dir/wiki/",
    )
    p.add_argument(
        "--skip-path-check",
        action="store_true",
        help="跳过 source_wiki 路径必须在 */data/wiki 的检查 (单测用, 生产严禁用)",
    )
    args = p.parse_args()

    args.source_wiki = args.source_wiki.resolve()
    args.release_dir = args.release_dir.resolve()

    # 严守: source_wiki 必须在 pipeline/data/wiki 下 (release 禁止从其他位置读)
    # 单测 (test_d056_*) 用 tmp 路径, 跳过此检查
    if not getattr(args, "skip_path_check", False):
        if not str(args.source_wiki).endswith("/data/wiki") and not str(args.source_wiki).endswith("/data/wiki/"):
            logger.error("source_wiki 必须在 */data/wiki 路径下: %s", args.source_wiki)
            sys.exit(6)

    result = build_wiki_release(args.source_wiki, args.release_dir)
    logger.info("✓ D-056 wiki release snapshot OK: %s", json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
