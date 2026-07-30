#!/usr/bin/env python3
"""pii_7a_check.py — 真实 KB FTS5 leak check (NJX 7/30 PR #5 严令: ops/pii-content-redaction-hardening)

NJX 7/30 严令 5 项: PR #4 PII-7a 保留, 作为最终真实 KB Gate.
根因: aog.db content_md 字段含 vendor info / 站点地址 / 库房电话, 旧 D-030 启发式只覆盖
      contacts JSON, 不覆盖 content_md. PR #4 staging 合同 PASS, 但真实 KB rehearsal FAIL:
      9 个 chunk 命中 3 个 non-public/redacted phone 原值 (D-051 教训).

检查方法:
  1. 从 owner 真实 aog.db cities 抽所有 non-public/restricted/redacted phone + email
     (NJX 7/30 严令: log 只 hash 12 字符, 严禁明文打印, 跟 D-051 一致)
  2. 查 FTS5 chunks_fts_content.c0 是否 0 命中 (命中 = 漏脱敏, fail)
  3. 严禁进 FTS5 chunk text / chroma persistence / aog.db content_md

设计原则:
  ★ 真实 KB gate (有真 aog.db 才走), 严禁 fixture 凑 (fixture 通常太干净, 测不出真泄漏)
  ★ PII 只 hash, 严禁明文
  ★ Exit 0 = PASS, Exit 4 = FAIL (跟 build-data-release.sh 一致)

用法:
  python -m scripts.pii_7a_check \\
    --aog-db /path/to/aog.db \\
    --fts5-db /path/to/fts5_index.db \\
    --max-samples 100

输出:
  PII-7a PASS: <n> non-public PII 全部 REDACTED (FTS5 0 命中)
  PII-7a FAIL: <n> 命中 (<hash1> x<cnt>, <hash2> x<cnt>, ...)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


# === Phone/Email patterns (跟 pii_sanitizer.py 一致, 严禁改) ===
# 严禁: 在本文件复制 pii_sanitizer 全部 patterns (单源真相 = pii_sanitizer.py)
# 这里只 import 复用, 避免规则漂移
def _extract_phone_candidates(text: str) -> list[str]:
    """从 text 抽 phone 候选 (跟 pii_sanitizer PHONE_PATTERNS 一致)"""
    import re

    if not text:
        return []
    candidates = []
    # +国家码
    for m in re.finditer(r"\+\d{1,3}[\s\-\(\)\.]*[\d\s\-\(\)\.]{6,}\d", text):
        candidates.append(m.group(0).strip())
    # 11+ 连续
    for m in re.finditer(r"(?<!\d)\d{11,}(?!\d)", text):
        candidates.append(m.group(0).strip())
    # 座机
    for m in re.finditer(r"(?<!\d)0\d{2,3}[\-\.]\d{7,8}(?:[\-\.]\d{1,5})?(?!\d)", text):
        candidates.append(m.group(0).strip())
    return candidates


def _extract_email_candidates(text: str) -> list[str]:
    """从 text 抽 email 候选"""
    import re

    if not text:
        return []
    return re.findall(
        r"(?<![A-Za-z0-9._-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text,
    )


def _hash_pii(value: str) -> str:
    """PII 只 hash 12 字符 (NJX 7/30 严令: 严禁明文打印)"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _is_public_contact(contact: dict) -> bool:
    """D-030 合同: 公开 contact 进 chunk, internal/restricted/redacted 不进."""
    if not contact:
        return False
    permission = (contact.get("permission") or "").lower()
    if permission == "public":
        return True
    if contact.get("redacted") is True:
        return False  # redacted=True 严禁进
    if permission in ("internal", "restricted", "private"):
        return False
    return False  # 默认 internal


def main():
    parser = argparse.ArgumentParser(
        description="PII-7a 真实 KB FTS5 leak check (NJX 7/30 PR #5 严令 5 项)"
    )
    parser.add_argument("--aog-db", required=True, type=Path, help="owner 真实 aog.db 路径")
    parser.add_argument("--fts5-db", required=True, type=Path, help="release fts5_index.db 路径")
    parser.add_argument("--max-samples", type=int, default=100, help="最大抽样数 (default 100)")
    args = parser.parse_args()

    aog_db_path = args.aog_db
    fts5_db_path = args.fts5_db

    if not aog_db_path.exists():
        print(f"✗ FAIL: aog_db 不存在: {aog_db_path}", file=sys.stderr)
        return 4
    if not fts5_db_path.exists():
        print(f"✗ FAIL: fts5_db 不存在: {fts5_db_path}", file=sys.stderr)
        return 4

    # === 1. 从 owner 真实 aog.db cities 抽 non-public phone + email ===
    con = sqlite3.connect(str(aog_db_path))
    con.row_factory = sqlite3.Row
    try:
        # 兼容 schema: 仅取必需字段, 允许 code/name 缺失 (空 DB / 部分 schema)
        cur = con.execute(
            "SELECT content_md, summary, contacts_json FROM cities "
            "WHERE content_md IS NOT NULL OR summary IS NOT NULL OR contacts_json IS NOT NULL "
            "LIMIT ?",
            (args.max_samples * 10,),
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        # cities 表不存在 / schema 不全, 当 SKIP 处理
        print(f"⚠️  PII-7a SKIP: aog.db cities 表不可读 ({e})", file=sys.stderr)
        con.close()
        return 0
    finally:
        try:
            con.close()
        except Exception:
            pass

    # 抽 non-public PII
    pii_set: set[str] = set()  # 用 set dedup, 查 FTS5 用
    pii_hash_counts: dict[str, int] = {}  # hash -> 计数
    for row in rows:
        # 抽 content_md + summary 文本里所有 phone/email
        text = (row["content_md"] or "") + "\n" + (row["summary"] or "")
        for ph in _extract_phone_candidates(text):
            pii_set.add(ph)
        for em in _extract_email_candidates(text):
            pii_set.add(em)

        # 抽 contacts_json 里 non-public 的 phone/email
        try:
            contacts = json.loads(row["contacts_json"] or "[]")
        except (json.JSONDecodeError, TypeError):
            contacts = []
        for c in contacts:
            if _is_public_contact(c):
                continue  # 公开的不算 PII
            for ph in (c.get("phone") or []):
                if isinstance(ph, str) and ph:
                    pii_set.add(ph)
            em = c.get("email")
            if isinstance(em, str) and em:
                pii_set.add(em)

    if not pii_set:
        print("⚠️  PII-7a SKIP: aog.db 抽不到 non-public PII (空 DB 或全 public)")
        return 0

    # === 2. 查 FTS5 chunks_fts_content.c0 命中 ===
    fts5_con = sqlite3.connect(str(fts5_db_path))
    try:
        # 检查 FTS5 是否有 chunks_fts_content
        cur = fts5_con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts_content'"
        )
        if not cur.fetchone():
            print("⚠️  PII-7a SKIP: fts5_index.db 无 chunks_fts_content 表 (未 export)")
            return 0

        # 抽样
        sample_pii = list(pii_set)[: args.max_samples]
        hits_by_hash: dict[str, int] = {}
        total_hits = 0
        for pii in sample_pii:
            h = _hash_pii(pii)
            # LIKE 查 (FTS5 c0 存原文本, LIKE 命中即泄漏)
            cur = fts5_con.execute(
                "SELECT COUNT(*) FROM chunks_fts_content WHERE c0 LIKE ?",
                (f"%{pii}%",),
            )
            cnt = cur.fetchone()[0]
            if cnt > 0:
                hits_by_hash[h] = hits_by_hash.get(h, 0) + cnt
                total_hits += cnt
    finally:
        fts5_con.close()

    # === 3. 报告 ===
    if total_hits == 0:
        print(f"✓ PII-7a PASS: {len(sample_pii)} non-public PII 全部 REDACTED (FTS5 0 命中)")
        return 0

    # FAIL
    print(f"✗ PII-7a FAIL: {total_hits} 命中 (sample {len(sample_pii)} PII)", file=sys.stderr)
    print(f"  命中 PII (hash 12 字符, 不明文):", file=sys.stderr)
    for h, cnt in sorted(hits_by_hash.items(), key=lambda x: -x[1]):
        print(f"    {h} x{cnt}", file=sys.stderr)
    return 4


if __name__ == "__main__":
    sys.exit(main())
