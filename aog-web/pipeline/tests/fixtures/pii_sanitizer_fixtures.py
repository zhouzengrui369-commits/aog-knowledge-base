"""pii_sanitizer_fixtures.py — 真实 phone/email fixture regression 数据 (NJX 7/30 PR #5 严令)

NJX 7/30 PR #5 严令 4 项: 增加真实 phone/email fixture regression.
放 tests/ 子文件, 让 .github/scripts/phone_email_scanner.py 自动 allowlist
(aog-web/pipeline/tests/ 在 fixture allowlist 里).

严禁: 改这些值绕过 scanner (会被其他 PR 抓真实 PII 误伤).
严禁: 移到非 tests/ 路径 (scanner 会 fail CI).
"""
from __future__ import annotations

# === Phone samples (NJX 7/30 PR #5 严令: 涵盖国际 / 中国手机 / 座机 / -/. 空格分隔) ===
# 真实 phone 格式 (跨地区, 跨格式)
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
