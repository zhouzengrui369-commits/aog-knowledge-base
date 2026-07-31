"""contact_canonical_conflict_fixtures.py — PR #8 conflict fixture (NJX 7/31 18:28 拍板)

PR #8 (NJX 7/31 18:28 拍板) 修法:
  1. canonical contact identity: phone/email normalize 后聚合所有 occurrence
  2. effective_permission: 全 public → public; 混合 public + non-public → restricted
  3. _build_contacts_chunk 用 effective_permission, 不使用原 permission
  4. D-054 v2 加 CONFLICTED 分类
  5. 增加 conflict fixture: public + internal 同 phone (D-054 真实场景)

本 fixture 模拟 owner data 标错: 同一 phone 在多个 city 不同 permission 标.
PR #8 期望: effective_permission=restricted (保守), 不进 chunk.
"""
from __future__ import annotations


# 冲突场景 1: 1 city public + 1 city internal, 同 phone
SCENARIO_1_PUBLIC_1_INTERNAL = [
    {
        "code": "M-CONFLICT-A",
        "name": "CONFLICT-A",
        "contacts": [
            {"org": "公开 AOG", "phone": ["010-64537139"], "permission": "public"},
        ],
    },
    {
        "code": "M-CONFLICT-B",
        "name": "CONFLICT-B",
        "contacts": [
            {"org": "内部 vendor", "phone": ["010-64537139"], "permission": "internal"},
        ],
    },
]


# 冲突场景 2: 1 city public + 多 city internal, 同 phone (D-054 真实根因)
# H-惠州 / S-深圳 / Y-运城 public + 15+ city internal, 共用 `18938850285`
SCENARIO_2_D054_REAL_ROOT_CAUSE = [
    *[{
        "code": f"M-PUB-{i:02d}",
        "name": f"PUB-{i:02d}",
        "contacts": [
            {"org": "深航", "phone": ["18938850285"], "permission": "public"},  # 3 public city
        ],
    } for i in range(3)],
    *[{
        "code": f"M-INT-{i:02d}",
        "name": f"INT-{i:02d}",
        "contacts": [
            {"org": "深航", "phone": ["18938850285"], "permission": "internal"},  # 15 internal city
        ],
    } for i in range(15)],
]


# 场景 3: 纯 public (无冲突)
SCENARIO_3_PURE_PUBLIC = [
    {
        "code": "M-PUB-1",
        "name": "PUB-1",
        "contacts": [
            {"org": "国航", "email": "aogoffice@airchina.com", "permission": "public"},
        ],
    },
    {
        "code": "M-PUB-2",
        "name": "PUB-2",
        "contacts": [
            {"org": "国航", "email": "aogoffice@airchina.com", "permission": "public"},
        ],
    },
]


# 场景 4: 纯 non-public (无冲突)
SCENARIO_4_PURE_NON_PUBLIC = [
    {
        "code": "M-INT-1",
        "name": "INT-1",
        "contacts": [
            {"org": "内部 vendor", "phone": ["13908081935"], "permission": "internal"},
        ],
    },
    {
        "code": "M-INT-2",
        "name": "INT-2",
        "contacts": [
            {"org": "内部 vendor", "phone": ["13908081935"], "permission": "internal"},
        ],
    },
]


# 场景 5: 黏连 phone normalization (D-053 严令 6 + PR #8)
# 黏连 phone `+86-018938850285` 拆出 `18938850285`, 跨 1 public + 1 internal 共用
SCENARIO_5_CONCAT_NORMALIZATION = [
    {
        "code": "M-NORM-A",
        "name": "NORM-A",
        "contacts": [
            {"org": "深航", "phone": ["+86-018938850285"], "permission": "public"},  # 黏连
        ],
    },
    {
        "code": "M-NORM-B",
        "name": "NORM-B",
        "contacts": [
            {"org": "深航", "phone": ["18938850285"], "permission": "internal"},  # 已 normalized
        ],
    },
]
