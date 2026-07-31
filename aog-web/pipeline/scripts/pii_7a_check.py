#!/usr/bin/env python3
"""pii_7a_check.py — 真实 KB FTS5 leak check (PII_7A_V2_PROVENANCE_AWARE_GATE)

NJX 7/30 PR #5 严令: PII-7a 真实 KB Gate, 取代 D-051/D-052/D-053 启发式.
NJX 7/31 16:12 D-054 拍板: PII-7a 判定模型 v2 (provenance-aware), 解决公开 contact 共享值
触发误报的设计问题. 在 PR #4 当前分支完成, 不建新 PR.

判定模型 (NJX 7/31 D-054 拍板):
  ★ 不是降低安全标准, NON_PUBLIC_ONLY 仍全局 0 hits
  ★ PUBLIC_ONLY 只允许 public city_contacts 来源
  ★ MIXED 只允许 public occurrence 来源
  ★ non-public source / free-text / experience / core / wiki 任一命中仍 FAIL

设计原则 (NJX 7/30 PR #5 严令):
  ★ 真实 KB gate (有真 aog.db 才走), 严禁 fixture 凑
  ★ PII 只 hash, 严禁明文打印
  ★ Exit 0 = PASS, Exit 4 = FAIL (跟 build-data-release.sh 一致)

用法:
  python -m scripts.pii_7a_check \\
    --aog-db /path/to/aog.db \\
    --fts5-db /path/to/fts5_index.db \\
    [--release]                # release mode 扫全部 values, 禁 max-samples
    [--max-samples 100]        # unit test mode 默认 100, --release 强制 None

输出 (release 模式):
  ✓ PII-7a v2 PASS: values_checked=N allowed_public_hits=N forbidden_hits=0 mixed_values=N
  ✗ PII-7a v2 FAIL: ... forbidden_hits=N ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# === Phone/Email patterns (跟 pii_sanitizer.py 一致, 严禁改) ===
def _extract_phone_candidates(text: str) -> list[str]:
    """从 text 抽 phone 候选 (跟 pii_sanitizer PHONE_PATTERNS 一致)

    PR #8 (NJX 7/31 18:28) 修: owner data 写不规范, 座机后有分机号黏连
    (e.g. `031-0898-68875172` = 031 区号 - 0898-6887517 + 2 黏连). 扩展 regex
    匹配 `\d{7,12}` 允许 7-12 数字 (11 位中国手机 + 1-4 位分机号).
    """
    if not text:
        return []
    candidates = []
    # +国家码
    for m in re.finditer(r"\+\d{1,3}[\s\-\(\)\.]*[\d\s\-\(\)\.]{6,}\d", text):
        candidates.append(m.group(0).strip())
    # 11+ 连续
    for m in re.finditer(r"(?<!\d)\d{11,}(?!\d)", text):
        candidates.append(m.group(0).strip())
    # 座机 (PR #8 扩展: 允许 7-12 数字含分机号, 排除 00XX 国际给 P4)
    for m in re.finditer(r"(?<!\d)0(?!0)\d{1,2}[\-\.]\d{7,12}(?!\d)", text):
        candidates.append(m.group(0).strip())
    return candidates


def _extract_email_candidates(text: str) -> list[str]:
    """从 text 抽 email 候选"""
    if not text:
        return []
    return re.findall(
        r"(?<![A-Za-z0-9._-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text,
    )


# === Phone validation (跟 pii_sanitizer.py PHONE_PATTERNS 同步, fail-closed) ===
# D-053 严令 6 修: pii_7a 抽 phone candidates 后用 is_valid_phone 验证,
# 排除 false positive (e.g. `+1 0230 1230` 是航班号时间戳, 不是 phone).
# 跟 pii_sanitizer.is_valid_phone 保持一致 (避免规则漂移).
PHONE_PATTERNS_PII7A = [
    # P1: +国家码 + phone
    re.compile(r"\+\d{1,3}[\s\-\(\)\.]*[\d\s\-\(\)\.]{6,}\d"),
    # P2: 11+ 连续数字
    re.compile(r"(?<!\d)\d{11,}(?!\d)"),
    # P3: 0XX-XXXXXXX 座机 (PR #8 扩展: 允许 7-12 数字含分机号黏连, 排除 00XX 国际)
    re.compile(r"(?<!\d)0(?!0)\d{1,2}[\-\.]\d{7,12}(?!\d)"),
    # P4: 00XX-XXXX-XXXX 国际 (PR #8 扩展: 允许 7-12 数字含分机号黏连)
    re.compile(r"(?<!\d)00\d{1,3}[\-\.]\d{7,12}(?!\d)"),
    # P5: 00(X)X... 国际括号格式 (D-053)
    re.compile(r"(?<!\d)00\(\d{1,4}\)\d{6,}(?!\d)"),
]


def _is_valid_phone_pii7a(phone: str) -> bool:
    """D-053 fail-closed: 验证 phone candidate 是否 valid.

    跟 pii_sanitizer.is_valid_phone 同步, 严守 D-053 严令 6:
      - 黏连 (含 \\d\\s+\\d) 整体 invalid (D-053 严令 2: 禁止整体 regex 吞掉多个号码)
      - 8 digit 无前导 0 视为 invalid (避免 owner data 异常 / false positive)
      - 任何 candidate 必须在 P1-P5 patterns 里

    Returns:
      True: valid phone
      False: invalid (false positive 或 黏连 或 owner data 异常)
    """
    if not phone or not isinstance(phone, str):
        return False
    # 严禁: 黏连 (含 \d\s+\d) — D-053 严令 2
    if re.search(r"\d\s+\d", phone):
        return False
    # 必须命中 5 个 pattern 之一
    matched = False
    for pat in PHONE_PATTERNS_PII7A:
        if pat.search(phone):
            matched = True
            break
    if not matched:
        return False
    # 8 digit 无前导 0 视为 invalid (D-053 fail-closed)
    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) == 8 and not digits_only.startswith("0"):
        return False
    return True


def _hash_pii(value: str) -> str:
    """PII 只 hash 12 字符 (NJX 7/30 严令: 严禁明文打印)"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _classify_contact_permission(contact: dict) -> str:
    """D-052 fail-closed 启发式: permission 分类.
    返回 'public' / 'internal' / 'restricted' / 'unknown' (缺省 unknown, 严守 D-052 fail-closed).
    """
    if not contact or not isinstance(contact, dict):
        return "unknown"
    if bool(contact.get("redacted")) is True:
        return "unknown"  # redacted=True 视为 unknown (不进 chunk)
    permission = (contact.get("permission") or "")
    if not isinstance(permission, str):
        return "unknown"
    permission = permission.strip().lower()
    if permission == "public":
        return "public"
    if permission in ("internal", "private"):
        return "internal"
    if permission == "restricted":
        return "restricted"
    return "unknown"  # missing/empty/unknown 全部 fail-closed


# === D-054 v2 数据结构: occurrence map ===

# Provenance constants (aog.db 来源)
PROV_FREE_TEXT = "free_text"  # content_md 自由文本
PROV_CONTACT_PUBLIC = "contact.public"
PROV_CONTACT_INTERNAL = "contact.internal"
PROV_CONTACT_RESTRICTED = "contact.restricted"
PROV_CONTACT_UNKNOWN = "contact.unknown"

# Allowed chunk sources (FTS5 c4 source_type)
ALLOWED_CHUNK_SOURCES = frozenset({"city_contacts"})
FORBIDDEN_CHUNK_SOURCES = frozenset({"city", "experience", "core_plan", "wiki", ""})


@dataclass
class AogDbOccurrence:
    """aog.db 里 value 的来源"""
    provenance: str  # PROV_* 常量
    city_code: str
    field: str  # 'content_md' | 'contact.org' | 'contact.phone' | 'contact.email'
    permission: str  # 'public' | 'internal' | 'restricted' | 'unknown' | 'free_text'


@dataclass
class Fts5Occurrence:
    """FTS5 chunk 里 value 的命中"""
    chunk_id: str
    source_id: str
    source_type: str  # c4: city_contacts / city / experience / core_plan / wiki / empty
    source_path: str  # c2: e.g. '02_外战预案/A-澳门.docx'


@dataclass
class ValueAssessment:
    """每个 PII value 的完整判定结果"""
    value: str
    hash: str
    aog_db_occurrences: list[AogDbOccurrence] = field(default_factory=list)
    fts5_occurrences: list[Fts5Occurrence] = field(default_factory=list)
    classification: str = "UNCLASSIFIED"  # PUBLIC_ONLY / NON_PUBLIC_ONLY / FREE_TEXT / MIXED / CONFLICTED / NO_HIT
    decision: str = "OK"  # ALLOWED / FORBIDDEN / OK
    is_conflicted: bool = False  # PR #8: 跨 city 出现 public + non-public
    effective_permission: str = "unknown"  # PR #8: public / restricted (canonical identity 算的)

    def add_aog_db(self, occ: AogDbOccurrence) -> None:
        self.aog_db_occurrences.append(occ)

    def add_fts5(self, occ: Fts5Occurrence) -> None:
        self.fts5_occurrences.append(occ)


def _classify_value(assessment: ValueAssessment) -> str:
    """基于 aog_db_occurrences 分类 value (NJX 7/31 D-054 v2 + PR #8 CONFLICTED).

    PR #8 (NJX 7/31 18:28 拍板): 跨 city 出现 public + non-public 的 value 标 CONFLICTED.
    CONFLICTED 决策跟 NON_PUBLIC_ONLY 一样: 任意 hit → FORBIDDEN (保守原则).
    但 PR #8 build 阶段 canonical identity 计算 effective_permission=restricted, 所以
    CONFLICTED value 不进 chunk, FTS5 hit=0 → OK (PII-7a PASS).
    """
    provenances = {occ.provenance for occ in assessment.aog_db_occurrences}
    if not provenances:
        return "NO_HIT"
    # PR #8 CONFLICTED: 跨 city 出现 public + non-public
    has_public = PROV_CONTACT_PUBLIC in provenances
    has_non_public = bool(provenances & {PROV_CONTACT_INTERNAL, PROV_CONTACT_RESTRICTED, PROV_CONTACT_UNKNOWN})
    if has_public and has_non_public:
        assessment.is_conflicted = True
        return "CONFLICTED"
    if provenances == {PROV_FREE_TEXT}:
        return "FREE_TEXT"
    if provenances == {PROV_CONTACT_PUBLIC}:
        return "PUBLIC_ONLY"
    if provenances <= {PROV_CONTACT_INTERNAL, PROV_CONTACT_RESTRICTED, PROV_CONTACT_UNKNOWN}:
        return "NON_PUBLIC_ONLY"
    # 包含 free_text + 任何 contact
    return "MIXED"


def _decide_value(assessment: ValueAssessment) -> str:
    """NJX 7/31 D-054 Gate 判定 (provenance-aware) + PR #8 CONFLICTED.

    NJX 7/31 16:12 拍板 Gate 规则:
      - NON_PUBLIC_ONLY: 任意 hit FAIL (non-public source 不应进任何 chunk)
      - PUBLIC_ONLY: 仅 public city_contacts hit 允许 (其他 hit FAIL)
      - MIXED: 仅 public source city_contacts hit 允许
        (公开 occurrence 允许, non-public occurrence hit FAIL)
      - 所有 free-text / experience / core / wiki hit FAIL (source_type 严格)
      - 没有 FTS5 hit: OK (没 leak, 通过)

    NJX 7/31 18:28 拍板 (PR #8) CONFLICTED 严守:
      - CONFLICTED: 跨 city 出现 public + non-public, 跟 NON_PUBLIC_ONLY 一样
        任意 hit FAIL (保守原则, 跟 build 阶段 effective_permission 协同)
      - 严禁: CONFLICTED 放宽 (NJX 拍板禁止修改 PII-7a 放行)
      - PR #8 build 阶段用 effective_permission=restricted 降级进 chunk,
        CONFLICTED value 不进任何 chunk, FTS5 hit=0 → OK
    """
    classification = assessment.classification
    fts5_hits = assessment.fts5_occurrences

    if not fts5_hits:
        # 无 FTS5 hit: 没 leak, OK
        return "OK"

    # 任何 FTS5 hit 的 source_type 不在 allowed 集合 (city_contacts) → FORBIDDEN
    # (free-text / experience / core / wiki 严格 FAIL, NJX 7/31 拍板)
    for hit in fts5_hits:
        if hit.source_type not in ALLOWED_CHUNK_SOURCES:
            return "FORBIDDEN"

    # 所有 FTS5 hits 都在 allowed (city_contacts)
    if classification in ("PUBLIC_ONLY", "MIXED"):
        # PUBLIC_ONLY: 公开 contact 全部 in city_contacts → ALLOWED
        # MIXED: 公开 occurrence + 全部 hits in city_contacts → ALLOWED
        #        (NJX 7/31 拍板: "MIXED 只允许 public occurrence 来源")
        return "ALLOWED"
    # CONFLICTED (PR #8) / FREE_TEXT / NON_PUBLIC_ONLY 即使只在 city_contacts 也 FAIL
    # CONFLICTED 跟 NON_PUBLIC_ONLY 一样, 因为 effective_permission=restricted,
    # build 阶段不应进任何 chunk, FTS5 hit=0 → 实际场景 OK
    return "FORBIDDEN"


# === Main gate logic ===

def _build_occurrence_map(
    aog_db_path: Path,
    max_samples: int | None,
) -> dict[str, ValueAssessment]:
    """从 aog.db 抽所有 PII, build occurrence map (value → ValueAssessment)."""
    con = sqlite3.connect(str(aog_db_path))
    con.row_factory = sqlite3.Row
    try:
        # D-052 修: 真实 schema 是 content_md + contacts, 严禁用 summary/contacts_json
        # schema 错误 (OperationalError) 必须 FAIL, 严禁 SKIP
        cur = con.execute(
            "SELECT code, content_md, contacts FROM cities "
            "WHERE content_md IS NOT NULL OR contacts IS NOT NULL "
            "LIMIT ?",
            (max_samples * 10 if max_samples else 10_000_000,),
        )
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(
            f"✗ FAIL: aog.db cities schema 不匹配 (NJX 7/31 D-052 严令: 严禁 SKIP): {e}",
            file=sys.stderr,
        )
        con.close()
        sys.exit(4)
    finally:
        try:
            con.close()
        except Exception:
            pass

    occurrence_map: dict[str, ValueAssessment] = {}

    def _add(value: str, occ: AogDbOccurrence) -> None:
        if value not in occurrence_map:
            occurrence_map[value] = ValueAssessment(value=value, hash=_hash_pii(value))
        occurrence_map[value].add_aog_db(occ)

    for row in rows:
        city_code = row["code"] or "?"

        # 抽 content_md 自由文本
        content_md = row["content_md"] or ""
        for ph in _extract_phone_candidates(content_md):
            if not _is_valid_phone_pii7a(ph):
                continue  # D-053 fail-closed: 排除 false positive (航班号/黏连/异常)
            _add(ph, AogDbOccurrence(
                provenance=PROV_FREE_TEXT, city_code=city_code,
                field="content_md", permission="free_text",
            ))
        for em in _extract_email_candidates(content_md):
            _add(em, AogDbOccurrence(
                provenance=PROV_FREE_TEXT, city_code=city_code,
                field="content_md", permission="free_text",
            ))

        # 抽 contacts (公开 + non-public 都抽, NJX 7/31 v2 严令 "values_skipped=0")
        try:
            contacts = json.loads(row["contacts"] or "[]")
        except (json.JSONDecodeError, TypeError):
            contacts = []
        for c in contacts:
            permission = _classify_contact_permission(c)
            prov_map = {
                "public": PROV_CONTACT_PUBLIC,
                "internal": PROV_CONTACT_INTERNAL,
                "restricted": PROV_CONTACT_RESTRICTED,
                "unknown": PROV_CONTACT_UNKNOWN,
            }
            prov = prov_map[permission]
            for ph in (c.get("phone") or []):
                if isinstance(ph, str) and ph:
                    if not _is_valid_phone_pii7a(ph):
                        continue  # D-053 fail-closed
                    _add(ph, AogDbOccurrence(
                        provenance=prov, city_code=city_code,
                        field="contact.phone", permission=permission,
                    ))
            em = c.get("email")
            if isinstance(em, str) and em:
                _add(em, AogDbOccurrence(
                    provenance=prov, city_code=city_code,
                    field="contact.email", permission=permission,
                ))

    return occurrence_map


def _query_fts5_occurrences(
    fts5_db_path: Path,
    occurrence_map: dict[str, ValueAssessment],
) -> None:
    """查 FTS5 每个 value 的所有 hits (带 c2/c3/c4 source metadata), 写到 occurrence_map."""
    fts5_con = sqlite3.connect(str(fts5_db_path))
    try:
        # 检查 FTS5 是否有 chunks_fts_content
        cur = fts5_con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts_content'"
        )
        if not cur.fetchone():
            print(
                "✗ FAIL: fts5_index.db 无 chunks_fts_content 表 (NJX 7/31 D-052 严令: 严禁 SKIP)",
                file=sys.stderr,
            )
            sys.exit(4)

        for value, assessment in occurrence_map.items():
            # LIKE 查 (FTS5 c0 存原文本, LIKE 命中即泄漏)
            # 同时拿 c1/title, c2/source_path, c3/source_id, c4/source_type
            cur = fts5_con.execute(
                "SELECT id, c2, c3, c4 FROM chunks_fts_content WHERE c0 LIKE ?",
                (f"%{value}%",),
            )
            for row in cur.fetchall():
                assessment.add_fts5(Fts5Occurrence(
                    chunk_id=f"fts:{row[0]}",
                    source_id=row[2] or "",
                    source_type=row[3] or "",
                    source_path=row[1] or "",
                ))
    finally:
        fts5_con.close()


def _assess_values(occurrence_map: dict[str, ValueAssessment]) -> dict[str, int]:
    """对每个 value 分类 + 判定, 返回汇总 metrics."""
    metrics = {
        "values_checked": len(occurrence_map),
        "values_skipped": 0,  # NJX 7/31 严令: 0, 全部检查
        "allowed_public_hits": 0,
        "forbidden_hits": 0,
        "mixed_values": 0,
        "public_only_values": 0,
        "non_public_only_values": 0,
        "free_text_values": 0,
        "conflicted_values": 0,  # PR #8 严守: 跨 city public + non-public
        "no_hit_values": 0,
    }
    for assessment in occurrence_map.values():
        assessment.classification = _classify_value(assessment)
        assessment.decision = _decide_value(assessment)
        if assessment.classification == "MIXED":
            metrics["mixed_values"] += 1
        elif assessment.classification == "PUBLIC_ONLY":
            metrics["public_only_values"] += 1
        elif assessment.classification == "NON_PUBLIC_ONLY":
            metrics["non_public_only_values"] += 1
        elif assessment.classification == "FREE_TEXT":
            metrics["free_text_values"] += 1
        elif assessment.classification == "CONFLICTED":  # PR #8
            metrics["conflicted_values"] += 1
        elif assessment.classification == "NO_HIT":
            metrics["no_hit_values"] += 1
        if assessment.decision == "ALLOWED":
            metrics["allowed_public_hits"] += 1
        elif assessment.decision == "FORBIDDEN":
            metrics["forbidden_hits"] += 1
    return metrics


def _print_report(
    metrics: dict[str, int],
    release_mode: bool,
    occurrence_map: dict[str, ValueAssessment] | None = None,
) -> int:
    """打印 report, 返回 exit code (0=PASS, 4=FAIL)."""
    if metrics["forbidden_hits"] == 0:
        print(
            f"✓ PII-7a v2 PASS: values_checked={metrics['values_checked']} "
            f"allowed_public_hits={metrics['allowed_public_hits']} "
            f"forbidden_hits=0 "
            f"mixed_values={metrics['mixed_values']} "
            f"public_only={metrics['public_only_values']} "
            f"non_public_only={metrics['non_public_only_values']} "
            f"free_text={metrics['free_text_values']} "
            f"conflicted={metrics['conflicted_values']} "  # PR #8
            f"no_hit={metrics['no_hit_values']}"
        )
        return 0
    # FAIL
    print(
        f"✗ PII-7a v2 FAIL: forbidden_hits={metrics['forbidden_hits']} "
        f"(values_checked={metrics['values_checked']}, "
        f"allowed_public_hits={metrics['allowed_public_hits']}, "
        f"mixed_values={metrics['mixed_values']}, "
        f"public_only={metrics['public_only_values']}, "
        f"non_public_only={metrics['non_public_only_values']}, "
        f"free_text={metrics['free_text_values']}, "
        f"conflicted={metrics['conflicted_values']}, "  # PR #8
        f"no_hit={metrics['no_hit_values']})",
        file=sys.stderr,
    )
    # NJX 7/30 严令: log 只 hash 12 字符, 严禁明文打印. v2 沿用 v1 行为:
    # 列出 forbidden value 的 hash + classification + decision (便于审计)
    if occurrence_map:
        print("  forbidden value 详情 (hash 12 字符, 不明文):", file=sys.stderr)
        for v, a in sorted(occurrence_map.items(), key=lambda kv: -len(kv[1].fts5_occurrences)):
            if a.decision == "FORBIDDEN":
                src_types = ",".join(sorted({h.source_type or "(empty)" for h in a.fts5_occurrences}))
                print(
                    f"    {a.hash} class={a.classification} decision={a.decision} "
                    f"fts5_sources=[{src_types}]",
                    file=sys.stderr,
                )
    return 4


def main():
    parser = argparse.ArgumentParser(
        description="PII-7a v2 真实 KB FTS5 leak check (NJX 7/31 D-054 拍板: provenance-aware gate)"
    )
    parser.add_argument("--aog-db", required=True, type=Path, help="owner 真实 aog.db 路径")
    parser.add_argument("--fts5-db", required=True, type=Path, help="release fts5_index.db 路径")
    parser.add_argument(
        "--release",
        action="store_true",
        help="release 模式: 扫全部 values, 禁 max-samples (NJX 7/31 严令: 严禁 sample-only)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=100,
        help="unit test 模式: 限制 PII 抽样数 (default 100, --release 强制忽略)",
    )
    args = parser.parse_args()

    if not args.aog_db.exists():
        print(f"✗ FAIL: aog_db 不存在: {args.aog_db}", file=sys.stderr)
        return 4
    if not args.fts5_db.exists():
        print(f"✗ FAIL: fts5_db 不存在: {args.fts5_db}", file=sys.stderr)
        return 4

    # release 模式: 扫全部 values, max_samples=None
    if args.release:
        max_samples = None
    else:
        max_samples = args.max_samples

    # === 1. Build occurrence map from aog.db ===
    occurrence_map = _build_occurrence_map(args.aog_db, max_samples)

    # D-052 严令: 无 PII 抽到必须 FAIL (严禁 SKIP)
    if not occurrence_map:
        print(
            "✗ FAIL: aog.db 抽不到 PII (NJX 7/31 D-052 严令: 严禁 SKIP-on-empty, "
            "必须 FAIL 提醒 owner 数据可能有问题)",
            file=sys.stderr,
        )
        return 4

    # === 2. Query FTS5 for all occurrences ===
    _query_fts5_occurrences(args.fts5_db, occurrence_map)

    # === 3. Classify + decide each value ===
    metrics = _assess_values(occurrence_map)

    # === 4. Print report ===
    return _print_report(metrics, args.release, occurrence_map)


if __name__ == "__main__":
    sys.exit(main())
