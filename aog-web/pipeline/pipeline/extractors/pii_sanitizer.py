"""pii_sanitizer.py — 统一 PII 脱敏 (NJX 7/30 PR #5 严令: ops/pii-content-redaction-hardening)

NJX 7/30 裁决: PR #4 真实 KB local rehearsal 触发 PII-7a FAIL — aog.db content_md 字段含
vendor info / 站点地址 / 库房电话等 phone 字符串, D-030 permission 启发式只覆盖 contacts
JSON 列表, 不覆盖 content_md. PII-7a 揭示 9 个 chunk 命中 3 个原值, 必须修.

本模块目标 (NJX 7/30 PR #5 严令 6 项):
  1. 新增统一 pii_sanitizer (phone → [PHONE_REDACTED], email → [EMAIL_REDACTED])
  2. extract_city 写入前调用 sanitizer
  3. experience / core plan / wiki ingestion 同样调用 sanitizer
  4. 增加真实 phone/email fixture regression
  5. PR #4 PII-7a 保留作为最终真实 KB Gate (本模块修后, PII-7a 应 PASS)
  6. 新增 5 个 sanitized 测试: source / sqlite / chroma / fts5 / rag result

设计原则:
  ★ Phone/Email 在 text 字段里必须 REDACTED, 严禁进:
    - aog.db content_md / summary / tags / title 字段 (Step 6 合同)
    - chunks_fts_content.c0 (FTS5 索引)
    - Chroma embeddings + metadata.text
    - RAG result 透传给 LLM 的 text
  ★ Public contact (在 contacts JSON 里 permission=public) 仍然进 _build_contacts_chunk
    (D-030 合同, 公开 AOG hotlines 是设计内)
  ★ Sanitizer 不可逆 (redact 后无法还原), 仅用于 chunk / FTS5 / chroma text;
    原始 SQLite 仍保留 permission=internal/restricted 的原值 (受控访问走 API).

匹配规则:
  - Phone: 7+ 位数字 (中国 11 位手机 + 国际 +86 + 座机 +86-xxx-xxxx-xxxx + -/. / / 空格分隔)
  - Email: 标准 email 格式 (含 . / @ 等)
  - 复合匹配: 先 email 再 phone (避免 email 里数字被 phone 误匹配)
"""
from __future__ import annotations

import re
from typing import Any

# === Phone patterns (NJX 7/30 PR #5 严令: 涵盖国际 / 中国手机 / 座机 / -/. 空格分隔) ===
# 多 pattern 联合 (任何一 match 就 redact), 减少误伤:
#   - 必须含 + / ( / 11+ 连续数字 / - 分隔 + 7+ 总数
#   - 严禁匹配 ISO 时间戳 / 件号 / π 等
PHONE_PATTERNS = [
    # 1. +国家码 + 数字 (e.g. +86 13908081935, +86-21-62690267, +852 27477069, +44 (0) 208 562 3007)
    re.compile(
        r"(?<![A-Za-z0-9_])"                # 前面不是字母/数字/_
        r"\+\d{1,3}"                        # +国家码
        r"[\s\-\(\)\.]*"                    # 可选分隔
        r"(?:\(\d{1,4}\)[\s\-\.]*)?"        # 可选 (区号)
        r"[\d\s\-\(\)\.]{6,}"               # 6+ 字符 (含数字 / 空格 / - / ( / ) / .)
        r"\d"                               # 收尾是数字
        r"(?![A-Za-z0-9_])"                 # 后面不是字母/数字/_
    ),
    # 2. (+86) 13761986774 (括号内国家码)
    re.compile(
        r"(?<![A-Za-z0-9_])"
        r"\(\+\d{1,4}\)"                   # (+国家码)
        r"[\s\-\.]*"
        r"[\d\s\-\(\)\.]{4,}"
        r"\d"
        r"(?![A-Za-z0-9_])"
    ),
    # 3. 11+ 连续数字 (中国手机 11 位, 国际 + 国家码 共 11+)
    # 严禁: 件号 "3-1531" (5 digits, 不足 11) / "18600051432" (11 digit 是手机, OK)
    re.compile(
        r"(?<!\d)\d{11,}(?!\d)"            # 11+ 连续数字, 前后非数字
    ),
    # 4. 座机 010-64537139 (10 digits, 有 - 分隔, 不被上面 11+ 覆盖)
    # 匹配: 0XX-XXXXXXX 或 0XX-XXXX-XXXX (中国座机 10-12 digits, 有 - 分隔)
    re.compile(
        r"(?<!\d)"
        r"0\d{2,3}"                         # 0XX 区号 (010 / 02X / 0XX)
        r"[\-\.]\d{7,8}"                   # -XXXXXXX (7-8 digits)
        r"(?:[\-\.]\d{1,5})?"               # 可选 -XXX 分机
        r"(?!\d)"
    ),
    # 5. 国际 00XX-XXX-XXX-XXXX (e.g. 0081-90-8144-2507 日本)
    # 匹配: 00 + 1-3 位国家码 + - + 总共 10+ 数字
    re.compile(
        r"(?<!\d)"
        r"00\d{1,3}"                        # 00国家码
        r"[\-\.]\d{2,4}"                    # -XX
        r"[\-\.]\d{3,4}"                    # -XXX
        r"[\-\.]\d{3,4}"                    # -XXXX
        r"(?!\d)"
    ),
]

# === Email pattern (NJX 7/30 PR #5 严令: 标准 email + aog.* sub-domain) ===
EMAIL_RE = re.compile(
    r"""
    (?<![A-Za-z0-9._-])                  # 前面不是字母/数字/_/-
    [A-Za-z0-9._%+-]+                    # local part
    @                                    # @
    [A-Za-z0-9.-]+                       # domain
    \.[A-Za-z]{2,}                      # TLD (>=2 chars)
    """,
    re.VERBOSE,
)

# === 替换 marker (NJX 7/30 严令: 用全大写方括号 marker, RAG 易识别) ===
PHONE_REDACTED = "[PHONE_REDACTED]"
EMAIL_REDACTED = "[EMAIL_REDACTED]"


def sanitize_phone(text: str) -> str:
    """把 text 里所有 phone 替换为 [PHONE_REDACTED].

    严禁保留: phone 原值
    替换 marker: [PHONE_REDACTED] (RAG 易识别, 人类易理解)
    """
    if not text:
        return text
    # 多 pattern 联合, 任何一 match 就 redact
    # 顺序: 先 +国家码, 再 11+ 连续, 再 座机
    # 注: re.sub 接受 list of patterns
    for pat in PHONE_PATTERNS:
        text = pat.sub(PHONE_REDACTED, text)
    return text


def sanitize_email(text: str) -> str:
    """把 text 里所有 email 替换为 [EMAIL_REDACTED].

    严禁保留: email 原值
    替换 marker: [EMAIL_REDACTED]
    """
    if not text:
        return text
    return EMAIL_RE.sub(EMAIL_REDACTED, text)


def sanitize_text(text: str) -> str:
    """统一 PII 脱敏: 先 email 再 phone (避免 email 里数字被 phone 误匹配).

    NJX 7/30 严令: 一致行为, content_md / summary / tags / title 字段统一调.
    """
    if not text:
        return text
    # 先 email (含 . / @ 不会触发 phone)
    text = sanitize_email(text)
    # 再 phone (数字 + -/. / 空格)
    text = sanitize_phone(text)
    return text


def sanitize_dict(d: dict, fields: list[str]) -> dict:
    """对 dict 的指定 string 字段做 sanitize_text.

    严禁: 改非 string 字段 (list/dict/int 跳过)
    严禁: 改 contacts JSON 字段 (permission 合同不同, _build_contacts_chunk 自己处理)
    """
    if not d:
        return d
    out = dict(d)  # copy
    for f in fields:
        v = out.get(f)
        if isinstance(v, str) and v:
            out[f] = sanitize_text(v)
    return out


def sanitize_record(record: dict, *, content_fields: list[str]) -> dict:
    """统一 record sanitize hook (NJX 7/30 PR #5 严令: extract_* 写入前调用).

    Args:
        record: 来自 City.to_dict() / Experience.to_dict() / CorePlan.to_dict() 的 dict
        content_fields: 要 sanitize 的字段列表 (e.g. ['content_md', 'summary', 'title'])

    严禁 sanitize: contacts JSON (permission 合同不同, _build_contacts_chunk 处理)
    严禁 sanitize: id / code / source_path (技术字段, 不含 PII)
    """
    if not record:
        return record
    return sanitize_dict(record, content_fields)


# === 测试 fixture (NJX 7/30 PR #5 严令 4 项: 真实 phone/email fixture regression) ===

# 用真实 phone 格式 (跨地区, 跨格式)
FIXTURE_PHONE_SAMPLES = [
    "+86 13908081935",          # 中国 11 位手机, 空格分隔
    "+86-21-62690267",          # 国际 + 座机, - 分隔
    "+852 27477069",            # 香港
    "+44 (0) 208 562 3007",     # 英国, () + 空格 + - 分隔
    "(+86) 13761986774",        # 圆括号
    "18600051432",              # 11 位手机, 无前缀
    "010-64537139",             # 座机
    "0081-90-8144-2507",        # 日本
]

FIXTURE_EMAIL_SAMPLES = [
    "litao010@163.com",         # 163 邮箱
    "aog-desk@ceair.com",       # 航空公司
    "Supply.engg@maiair.com",   # 缅甸
    "jiewei.huang@mtuzhuhai.com",
    "info@example.org",
    "very.long.email+tag@subdomain.example.co.uk",
]

# 不应被 match (测试 sanitizer 不过度)
FIXTURE_NEGATIVE_SAMPLES = [
    "ISO 9001",            # 标准号
    "3-1531",              # 件号
    "v30-d038",            # schema version
    "ABC-12345",           # 产品号
    "1.2.3",               # 版本
    "100%",                # 百分比
    "2026-07-30T13:57:31Z",  # ISO 8601 时间戳
    "3.14159265",          # π
]
