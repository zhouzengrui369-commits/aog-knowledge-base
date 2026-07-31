"""contact_canonical.py — canonical contact identity + effective_permission (NJX 7/31 18:28 拍板)

NJX 7/31 18:28 拍板 D-054 v2 阻塞 (真实 KB 1 forbidden hit, NON_PUBLIC_ONLY class) 根因:
  owner 多个 city 跨 permission 标错 (e.g. H-惠州 / S-深圳 / Y-运城 把深航 internal contact 标 public),
  D-053 修后 phone normalization 拆 phone 出来, 进 city_contacts chunk (因为标 public), 但 aog.db
  其他 city 抽到同一 phone 是 internal (NON_PUBLIC_ONLY class), 触发 PII-7a v2 NON_PUBLIC_ONLY
  任意 hit → FORBIDDEN (NJX 拍板 4 严守, 不降安全).

修法 (PR #8 fix/pipeline-contact-permission-conflict-resolution):
  1. canonical contact identity: phone/email normalize 后聚合所有 occurrence
  2. effective_permission: 全 public → public; 全 non-public → restricted;
     public + non-public → restricted (保守原则)
  3. _build_contacts_chunk 用 effective_permission, 不使用原 permission
  4. D-054 v2 pii_7a_check 加 CONFLICTED 分类 (跨 city 出现 public + non-public 的 value)

设计原则:
  ★ canonical identity 是 ingest 阶段计算, 跟 phone normalization (D-053) 协同
  ★ effective_permission 覆盖原 permission, _build_contacts_chunk 严守
  ★ 严禁 allowlist 特定 phone/email (NJX 7/31 18:28 禁止)
  ★ 严禁手工清洗 owner 数据 (NJX 7/31 18:28 禁止)
  ★ 严禁 public 全量 redact (NJX 7/31 18:28 禁止)
  ★ 严禁修改 PII-7a 放行 (NJX 7/31 18:28 禁止)
"""
from __future__ import annotations

import re
from typing import Any

from .pii_sanitizer import is_valid_phone


def _normalize_phone(phone: str) -> str | None:
    """Normalize phone to canonical form (D-053 拆黏连 + 验证).

    跟 city_meta._extract_contacts 拆 phone 行为一致 (D-053 严令 6):
      - +86 11位 mobile → 提取后 11 位
      - +86 0XXXXXXXXX (黏连修后, 12 位) → 跳 0 提取后 11 位
      - +国际 phone → 保留 + 和数字
      - 0XX-XXXXXXX 座机 → 移除分隔符
      - 黏连 / invalid → None (fail-closed 丢弃)

    Returns:
      canonical phone string (digits + leading +), or None if invalid.
    """
    if not phone or not isinstance(phone, str):
        return None
    if not is_valid_phone(phone):
        return None  # D-053 fail-closed
    # 移除常见分隔符
    digits = re.sub(r"[\s\-\(\)\.]", "", phone)
    if not digits:
        return None
    # +86 11 位 mobile: 提取后 11 位
    if digits.startswith("+86"):
        rest = digits[3:]  # 跳过 "+86"
        # owner data 异常: 黏连 +86 后还有前导 0, e.g. `+86-018938850285` → +86018938850285
        # 跳 0 提取后 11 位
        if rest.startswith("0"):
            rest = rest[1:]
        if len(rest) == 11:
            return rest
        if 7 <= len(rest) <= 12:
            return rest  # +86 + 7-12 位 (座机/国际)
        return rest  # 11+ 接受
    if digits.startswith("+") and len(digits) > 4:
        return digits  # 国际 phone
    # 座机 0XX-XXXXXXX (10-12 digits)
    if digits.startswith("0") and 7 <= len(digits) <= 12:
        return digits
    # 11+ 连续 (中国 11 位手机)
    if len(digits) >= 11 and digits[0] in "1":
        return digits
    return None  # 不符任何已知 pattern


def _normalize_email(email: str) -> str:
    """Normalize email (lowercase + trim)."""
    if not email or not isinstance(email, str):
        return ""
    return email.strip().lower()


def _classify_contact_permission(contact: dict) -> str:
    """D-052 fail-closed 启发式: 单 contact permission 分类.

    返回 'public' / 'internal' / 'restricted' / 'unknown' (缺省 unknown, 严守 D-052 fail-closed).
    """
    if not contact or not isinstance(contact, dict):
        return "unknown"
    if bool(contact.get("redacted")) is True:
        return "unknown"
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
    return "unknown"


def _compute_effective_permission(permissions: set[str]) -> str:
    """NJX 7/31 18:28 拍板 effective_permission 计算规则.

    规则:
      - 全 public → public
      - 全 non-public (internal/restricted/unknown) → restricted
      - 混合 public + non-public → restricted (保守原则, 严守 PII 隔离)
      - 严禁: 跨 city permission 冲突时降级为 public (会触发 PII-7a v2 FORBIDDEN)
    """
    if permissions == {"public"}:
        return "public"
    return "restricted"


def build_canonical_identity(cities: list[dict]) -> dict[str, dict]:
    """Build canonical contact identity index from all cities' contacts.

    聚合所有 city 的 contact phone/email, normalize 后建索引.
    每个 canonical key 对应一个 value, 记录所有 occurrence + effective_permission.

    Returns:
      {
        "phone:18938850285": {
          'type': 'phone',
          'value': '18938850285',
          'occurrences': [
            {'city_code': 'B-北京', 'contact_idx': 3, 'original_permission': 'internal', 'field': 'phone'},
            {'city_code': 'H-惠州', 'contact_idx': 1, 'original_permission': 'public', 'field': 'phone'},
            ...
          ],
          'effective_permission': 'restricted',  # 跨 city 混合 → restricted
          'is_conflicted': True,  # public + non-public 共存
        },
        "email:aogoffice@airchina.com": {
          'type': 'email',
          'value': 'aogoffice@airchina.com',
          'occurrences': [...],
          'effective_permission': 'public',  # 全 public → public
          'is_conflicted': False,
        },
      }
    """
    identity: dict[str, dict] = {}

    for city in cities:
        contacts = city.get("contacts", []) or []
        for idx, ct in enumerate(contacts):
            original_perm = _classify_contact_permission(ct)
            # 处理 phone
            for ph in (ct.get("phone") or []):
                if not isinstance(ph, str) or not ph:
                    continue
                canonical = _normalize_phone(ph)
                if not canonical:
                    continue  # D-053 fail-closed: invalid phone 丢弃
                key = f"phone:{canonical}"
                if key not in identity:
                    identity[key] = {
                        "type": "phone",
                        "value": canonical,
                        "occurrences": [],
                        "effective_permission": None,
                        "is_conflicted": False,
                    }
                identity[key]["occurrences"].append({
                    "city_code": city.get("code", "?"),
                    "contact_idx": idx,
                    "original_permission": original_perm,
                    "field": "phone",
                })
            # 处理 email
            em = ct.get("email")
            if isinstance(em, str) and em:
                canonical = _normalize_email(em)
                if canonical:
                    key = f"email:{canonical}"
                    if key not in identity:
                        identity[key] = {
                            "type": "email",
                            "value": canonical,
                            "occurrences": [],
                            "effective_permission": None,
                            "is_conflicted": False,
                        }
                    identity[key]["occurrences"].append({
                        "city_code": city.get("code", "?"),
                        "contact_idx": idx,
                        "original_permission": original_perm,
                        "field": "email",
                    })

    # 计算 effective_permission
    for entry in identity.values():
        perms = {occ["original_permission"] for occ in entry["occurrences"]}
        entry["effective_permission"] = _compute_effective_permission(perms)
        # is_conflicted 强转 bool (避免 set() truthy 误判)
        entry["is_conflicted"] = bool(
            "public" in perms and bool(perms - {"public"})
        )

    return identity


def annotate_contacts_with_effective_permission(
    cities: list[dict],
    identity: dict[str, dict],
) -> list[dict]:
    """给每个 city 的 contact 加 effective_permission 字段 (覆盖原 permission).

    NJX 7/31 18:28 拍板: _build_contacts_chunk 用 effective_permission, 不使用原 permission.
    算法: contact 的 phone + email 查 identity, 取最严的 effective_permission.
      - 全 public → public
      - 含 restricted → restricted
    同时: 如果 contact 任意 phone/email 跨 city conflict, 标 is_conflicted=True
    (供 _build_contacts_chunk 显示标签, 不改 chunk 内容决定).
    """
    for city in cities:
        for ct in city.get("contacts", []) or []:
            contact_effective: set[str] = set()
            contact_conflicted = False
            # 查 phone
            for ph in (ct.get("phone") or []):
                if not isinstance(ph, str) or not ph:
                    continue
                canonical = _normalize_phone(ph)
                if canonical:
                    key = f"phone:{canonical}"
                    if key in identity:
                        contact_effective.add(identity[key]["effective_permission"])
                        if identity[key]["is_conflicted"]:
                            contact_conflicted = True
            # 查 email
            em = ct.get("email")
            if isinstance(em, str) and em:
                canonical = _normalize_email(em)
                if canonical:
                    key = f"email:{canonical}"
                    if key in identity:
                        contact_effective.add(identity[key]["effective_permission"])
                        if identity[key]["is_conflicted"]:
                            contact_conflicted = True
            # 取最严: 单一 public → public, 任何 restricted → restricted
            if contact_effective == {"public"}:
                ct["effective_permission"] = "public"
            else:
                ct["effective_permission"] = "restricted"
            ct["is_conflicted"] = contact_conflicted
    return cities


def get_conflicted_values(identity: dict[str, dict]) -> list[dict]:
    """返回所有 conflicted value (跨 city 出现 public + non-public).

    供 PII-7a v2 CONFLICTED 分类用.
    """
    return [
        {
            "key": key,
            "type": entry["type"],
            "value": entry["value"],
            "occurrences": entry["occurrences"],
            "effective_permission": entry["effective_permission"],
        }
        for key, entry in identity.items()
        if entry["is_conflicted"]
    ]
