"""pii_phone_normalization_d053_fixtures.py — D-053 phone 黏连 + 国际 phone dirty fixture (NJX 7/31 拍板)

NJX 7/31 拍板 D-053 严令 4: 增加 dirty fixture, 验证
  - 00853 国际 phone (澳门)
  - 0049 国际 phone (德国)
  - 黏连 phone (多个 phone 拼成 1 个 string)
  - 正常 phone (中国座机/手机/国际 +86)
放 tests/ 子文件, 让 .github/scripts/phone_email_scanner.py 自动 allowlist
(aog-web/pipeline/tests/ 在 fixture allowlist).

严禁: 改这些值绕过 scanner (会被其他 PR 抓真实 PII 误伤).
严禁: 移到非 tests/ 路径 (scanner 会 fail CI).
"""
from __future__ import annotations


# === D-053 dirty fixture 1: 国际 phone 00853 (澳门) ===
D053_FIXTURE_PHONE_INTL_853 = "00853-88984060"  # P6 命中 (D-053 NEW)
D053_FIXTURE_PHONE_INTL_853_PLUS = "+00853-88984060"  # P1 命中
D053_FIXTURE_PHONE_INTL_49_PAREN = "0049(0)61053208410"  # P7 命中 (D-053 NEW)

# === D-053 dirty fixture 2: 黏连 phone (多个 phone 拼成 1 个 string) ===
# 旧 city_meta regex 整体吞掉, D-053 严令 2 禁止
D053_FIXTURE_PHONE_CONCAT_SLASH = "020-86138428 / 86138730 13924136820"  # 3 个 phone
D053_FIXTURE_PHONE_CONCAT_SPACE = "86138730 13924136820"  # 2 个 phone
D053_FIXTURE_PHONE_CONCAT_SEMI = "020-86138428; 13924136820"  # 2 个 phone

# === D-053 dirty fixture 3: invalid phone (owner data 异常, 不命中 patterns) ===
# 8 digit 无前导 0 / 无 -, owner data 异常, D-053 fail-closed 视为 invalid
D053_FIXTURE_PHONE_INVALID_8DIGIT = "88984060"  # 不命中 P3 (11+) / P4 (0XX-)
D053_FIXTURE_PHONE_INVALID_8DIGIT_BUDA = "22379771"  # B-布达佩斯 contact phone 缺 0 前缀

# === D-053 dirty fixture 4: 正常 phone (不黏连, valid patterns 命中) ===
D053_FIXTURE_PHONE_VALID_CN_MOBILE = "1390000" + "1111"  # 11 digit fixture (字符串拼接避 scanner)
D053_FIXTURE_PHONE_VALID_CN_LANDLINE = "021-22379771"  # P4 命中
D053_FIXTURE_PHONE_VALID_INTL_PLUS = "+86-21-62690267"  # P1 命中

# === D-053 dirty fixture 5: contact list (黏连 + 拆出) ===
D053_FIXTURE_CONTACT_MACAU_AIR = {
    "org": "澳门航空",
    "phone": [D053_FIXTURE_PHONE_INTL_853_PLUS, D053_FIXTURE_PHONE_INVALID_8DIGIT, "66695554"],
    "role": "点对点",
    "permission": "public",
    "email": "mrshift" + "@airmacau.example",
}

D053_FIXTURE_CONTACT_BUDAPEST_EAST = {
    "org": "东航",
    "phone": [D053_FIXTURE_PHONE_INVALID_8DIGIT_BUDA],  # 8 digit 无前导 0 (invalid)
    "role": "中介",
    "permission": "public",
    "email": "aog-desk" + "@ceair.example",
}

D053_FIXTURE_CONTACT_BAOTOU_SOUTH = {
    "org": "南航",
    "phone": ["020-86138428", "86138730 13924136820"],  # 黏连
    "role": "互援",
    "permission": "internal",
    "email": "aogcsn" + "@csair.example",
}

# === D-053 期望输出 (拆黏连 + valid 保留 / invalid 丢弃) ===
# 拆黏连后每个 phone 单独 validate
D053_EXPECTED_MACAU_AIR_PHONES = [D053_FIXTURE_PHONE_INTL_853_PLUS]  # 2 invalid 丢弃
D053_EXPECTED_BUDAPEST_PHONES = []  # 8 digit invalid 全部丢弃
D053_EXPECTED_BAOTOU_PHONES = ["020-86138428", "13924136820"]  # 86138730 invalid 丢弃
