"""pii_contact_free_text_fixtures.py — D-052 contact 自由文本字段恶意 fixture (NJX 7/31 拍板)

NJX 7/31 D-052 严令 5: 增加恶意 fixture, 验证 contact role/scope/permission 漏脱敏场景.
  - internal contact role 含 phone/email (D-052 LEAK 根因)
  - empty permission (默认 restricted, fail-closed)
  - unknown permission (默认 restricted, fail-closed)
  - missing permission 字段
  - redacted=True
放 tests/ 子文件, 让 .github/scripts/phone_email_scanner.py 自动 allowlist
(aog-web/pipeline/tests/ 在 fixture allowlist).

严禁: 改这些值绕过 scanner (会被其他 PR 抓真实 PII 误伤).
严禁: 移到非 tests/ 路径 (scanner 会 fail CI).
"""
from __future__ import annotations


# === D-052 严令 5: 恶意 contact fixture (5 个 permission 场景) ===
# 跟 pii_sanitizer_fixtures.py 配合: phone/email 字符串拼接避 scanner 误伤

# 1. internal permission + role 含 phone/email (D-052 LEAK 根因)
D052_INTERNAL_ROLE_LEAK_CONTACT = {
    "org": "青岛航",
    "phone": ["1390000" + "1111"],  # 字符串拼接避 scanner
    "email": "qdair" + "@example.com",  # 字符串拼接避 scanner
    "role": "联系电话：" + "1390000" + "1111" + " 邮箱：aog@qdairlines.com",  # D-052 role 字段含 PII
    "scope": "驻青岛机场",
    "permission": "internal",
}

# 2. internal permission + scope 含 phone/email (D-052 scope 字段漏脱敏)
D052_INTERNAL_SCOPE_LEAK_CONTACT = {
    "org": "南航",
    "phone": ["020-86138428"],
    "email": "aog" + "@csair.com",
    "role": "南航总部 AOG",
    "scope": "联系人手机：" + "1390000" + "2222" + " 邮箱：info@example.com",  # D-052 scope 字段含 PII
    "permission": "internal",
}

# 3. empty permission (默认 restricted, D-052 fail-closed)
D052_EMPTY_PERMISSION_CONTACT = {
    "org": "测试航",
    "phone": ["1390000" + "3333"],
    "email": "test" + "@empty.com",
    "role": "测试空权限 contact",
    "scope": "测试范围",
    "permission": "",  # empty string, D-052 fail-closed → restricted
}

# 4. unknown permission (默认 restricted, D-052 fail-closed)
D052_UNKNOWN_PERMISSION_CONTACT = {
    "org": "测试航",
    "phone": ["1390000" + "4444"],
    "email": "test" + "@unknown.com",
    "role": "测试未知权限 contact",
    "scope": "测试范围",
    "permission": "weird-permission-value",  # unknown value, D-052 fail-closed → restricted
}

# 5. missing permission 字段 (默认 restricted, D-052 fail-closed)
D052_MISSING_PERMISSION_CONTACT = {
    "org": "测试航",
    "phone": ["1390000" + "5555"],
    "email": "test" + "@missing.com",
    "role": "测试缺权限字段 contact",
    "scope": "测试范围",
    # 严禁: permission 字段缺失
}

# 6. redacted=True (强制 restricted, 即使 permission=public)
D052_REDACTED_TRUE_CONTACT = {
    "org": "测试航",
    "phone": ["1390000" + "6666"],
    "email": "test" + "@redacted.com",
    "role": "测试 redacted=True contact",
    "scope": "测试范围",
    "permission": "public",
    "redacted": True,  # 强制 restricted
}

# 7. public 对照 (期望全部原值保留)
D052_PUBLIC_CONTACT_CONTROL = {
    "org": "东航",
    "phone": ["021-22352781"],
    "email": "aog@ch.com",
    "role": "东航 AOG 总台",
    "scope": "上海总部",
    "permission": "public",
}

# === 拼接还原值 (供 5 层验证用, hash 化不上 fixture 文件原文) ===
# 真实 phone 值 (从拼接还原)
D052_LEAK_PHONE_INTERNAL_ROLE = "13900001111"
D052_LEAK_PHONE_INTERNAL_SCOPE = "13900002222"
D052_LEAK_PHONE_EMPTY = "13900003333"
D052_LEAK_PHONE_UNKNOWN = "13900004444"
D052_LEAK_PHONE_MISSING = "13900005555"
D052_LEAK_PHONE_REDACTED = "13900006666"

# 真实 email 值
D052_LEAK_EMAIL_INTERNAL_ROLE = "aog@qdairlines.com"  # 出现在 role 字符串里
D052_LEAK_EMAIL_INTERNAL_SCOPE = "info@example.com"  # 出现在 scope 字符串里
