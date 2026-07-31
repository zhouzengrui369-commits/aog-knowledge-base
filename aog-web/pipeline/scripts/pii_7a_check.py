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
    """D-030 + D-052 合同: 公开 contact 进 chunk, 其它全部不进.

    ★ D-052 fail-closed (NJX 7/31 拍板):
      - permission=public AND not redacted  → True (公开)
      - 其它所有 (missing/empty/internal/restricted/unknown/redacted) → False (视为 non-public)
      - 严禁: 默认 public (历史 D-030 bug: missing → public 导致 phone leak)
    """
    if not contact or not isinstance(contact, dict):
        return False
    if bool(contact.get("redacted")) is True:
        return False  # redacted=True 严禁进
    permission = (contact.get("permission") or "")
    if not isinstance(permission, str):
        return False
    permission = permission.strip().lower()
    if permission == "public":
        return True
    # 其它 (missing/empty/internal/restricted/private/unknown) 全部 non-public
    return False


def main():
    parser = argparse.ArgumentParser(
        description="PII-7a 真实 KB FTS5 leak check (NJX 7/31 D-052 严令: 改 schema + FAIL-on-error)"
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
    # D-052 修: 真实 schema 是 content_md + contacts, 严禁用 summary/contacts_json (跟 schema 不匹配)
    con = sqlite3.connect(str(aog_db_path))
    con.row_factory = sqlite3.Row
    try:
        # D-052 修: schema 错误 (OperationalError) 必须 FAIL, 严禁 SKIP
        # SKIP 会让 PII-7a 假绿 (NJX 7/31 拍板)
        # 期望 schema: code, name, content_md, contacts (TEXT, JSON list)
        cur = con.execute(
            "SELECT content_md, contacts FROM cities "
            "WHERE content_md IS NOT NULL OR contacts IS NOT NULL "
            "LIMIT ?",
            (args.max_samples * 10,),
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        # D-052 修: schema 错误 FAIL (不是 SKIP)
        print(f"✗ FAIL: aog.db cities schema 不匹配 (NJX 7/31 D-052 严令: 严禁 SKIP): {e}", file=sys.stderr)
        con.close()
        return 4
    finally:
        try:
            con.close()
        except Exception:
            pass

    # 抽 non-public PII (D-052 fail-closed: missing/empty/unknown 视为 non-public)
    pii_set: set[str] = set()  # 用 set dedup, 查 FTS5 用
    pii_hash_counts: dict[str, int] = {}  # hash -> 计数
    for row in rows:
        # 抽 content_md 文本里所有 phone/email (D-052: 不用 summary 字段, schema 没这字段)
        text = (row["content_md"] or "")
        for ph in _extract_phone_candidates(text):
            pii_set.add(ph)
        for em in _extract_email_candidates(text):
            pii_set.add(em)

        # 抽 contacts (D-052 真实字段, 不是 contacts_json) 里 non-public 的 phone/email
        try:
            contacts = json.loads(row["contacts"] or "[]")
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

    # D-052 修: 无 non-public 样本必须 FAIL (不是 PASS/SKIP)
    # 历史 SKIP 行为会假绿 (NJX 7/31 拍板: 严禁 SKIP-on-empty)
    if not pii_set:
        print("✗ FAIL: aog.db 抽不到 non-public PII (NJX 7/31 D-052 严令: 严禁 SKIP-on-empty, 必须 FAIL 提醒 owner 数据可能有问题)", file=sys.stderr)
        return 4

    # === 2. 查 FTS5 chunks_fts_content.c0 命中 ===
    fts5_con = sqlite3.connect(str(fts5_db_path))
    try:
        # 检查 FTS5 是否有 chunks_fts_content
        cur = fts5_con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts_content'"
        )
        if not cur.fetchone():
            # D-052 严令 4: 无 chunks_fts_content 表必须 FAIL, 严禁 SKIP
            # SKIP 会让 PII-7a 假绿, owner 部署后才发现 FTS5 没 export
            print("✗ FAIL: fts5_index.db 无 chunks_fts_content 表 (未 export, NJX 7/31 D-052 严令: 严禁 SKIP)", file=sys.stderr)
            return 4

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
