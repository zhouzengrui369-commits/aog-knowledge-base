"""test_contact_canonical.py — PR #8 canonical contact identity + effective_permission 测试

NJX 7/31 18:28 拍板 PR #8 测试覆盖:
  1. effective_permission 计算 (4 个场景: pure_public / pure_non_public / conflict / concat)
  2. canonical identity 聚合 (跨 city occurrence)
  3. _build_contacts_chunk 用 effective_permission (D-054 真实场景: H-惠州 / S-深圳 / Y-运城
     把深航 internal 标 public, 期望 effective_permission=restricted 不进 phone)
  4. pii_7a_check v2 CONFLICTED 分类 (跟 NON_PUBLIC_ONLY 一样决策)

运行:
  cd aog-web/pipeline
  ../backend/.venv/bin/python -m pytest tests/test_contact_canonical.py -v --tb=short
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT))

from pipeline.extractors.contact_canonical import (
    _compute_effective_permission,
    annotate_contacts_with_effective_permission,
    build_canonical_identity,
    get_conflicted_values,
)
from pipeline.build_index import _build_contacts_chunk
from tests.fixtures.contact_canonical_conflict_fixtures import (
    SCENARIO_1_PUBLIC_1_INTERNAL,
    SCENARIO_2_D054_REAL_ROOT_CAUSE,
    SCENARIO_3_PURE_PUBLIC,
    SCENARIO_4_PURE_NON_PUBLIC,
    SCENARIO_5_CONCAT_NORMALIZATION,
)


# === PR #8 单元测试 ===

def test_pr8_effective_permission_pure_public():
    """SCENARIO_3 全 public → effective_permission=public"""
    identity = build_canonical_identity(SCENARIO_3_PURE_PUBLIC)
    for key, entry in identity.items():
        assert entry["effective_permission"] == "public", f"{key} 应 public, 实际 {entry['effective_permission']}"
        assert entry["is_conflicted"] is False


def test_pr8_effective_permission_pure_non_public():
    """SCENARIO_4 全 internal → effective_permission=restricted"""
    identity = build_canonical_identity(SCENARIO_4_PURE_NON_PUBLIC)
    for key, entry in identity.items():
        assert entry["effective_permission"] == "restricted", f"{key} 应 restricted"
        assert entry["is_conflicted"] is False


def test_pr8_effective_permission_conflict_downgrades_to_restricted():
    """SCENARIO_1 1 public + 1 internal 同 phone → effective_permission=restricted (保守)"""
    identity = build_canonical_identity(SCENARIO_1_PUBLIC_1_INTERNAL)
    # 应该只有 1 个 phone value (010-64537139 跨 2 city 共享)
    assert len(identity) == 1
    entry = list(identity.values())[0]
    # 跨 city 出现 public + non-public → restricted (NJX 拍板 保守原则)
    assert entry["effective_permission"] == "restricted", f"应 restricted, 实际 {entry['effective_permission']}"
    assert entry["is_conflicted"] is True
    # occurrences 应该有 2 个 (1 public city + 1 internal city)
    assert len(entry["occurrences"]) == 2


def test_pr8_d054_real_root_cause_3_public_15_internal():
    """SCENARIO_2 D-054 真实根因: 3 public + 15 internal 共用 `18938850285` → restricted

    模拟 owner data 标错: H-惠州 / S-深圳 / Y-运城 把深航 internal 标 public,
    跟 15 个其他 internal city 共用同一 phone.
    PR #8 期望: canonical identity 聚合, effective_permission=restricted.
    """
    identity = build_canonical_identity(SCENARIO_2_D054_REAL_ROOT_CAUSE)
    # 18 city 共用同一 phone `18938850285`, 应该只有 1 个 entry
    assert len(identity) == 1
    entry = list(identity.values())[0]
    # 跨 city public + non-public → restricted (保守)
    assert entry["effective_permission"] == "restricted"
    assert entry["is_conflicted"] is True
    # occurrences 应该有 18 (3 public + 15 internal)
    assert len(entry["occurrences"]) == 18
    public_count = sum(1 for occ in entry["occurrences"] if occ["original_permission"] == "public")
    non_public_count = sum(1 for occ in entry["occurrences"] if occ["original_permission"] != "public")
    assert public_count == 3
    assert non_public_count == 15


def test_pr8_concat_phone_normalization_d053_compat():
    """SCENARIO_5 D-053 黏连 phone + PR #8 conflict 协同"""
    identity = build_canonical_identity(SCENARIO_5_CONCAT_NORMALIZATION)
    # 黏连 `+86-018938850285` 拆出 `18938850285` (D-053), 跟 1 internal `18938850285` 共用
    # 1 public + 1 internal → restricted (conflict)
    phone_entries = [e for e in identity.values() if e["type"] == "phone"]
    assert len(phone_entries) == 1
    entry = phone_entries[0]
    assert entry["value"] == "18938850285"
    assert entry["effective_permission"] == "restricted"
    assert entry["is_conflicted"] is True


# === PR #8 + _build_contacts_chunk 集成测试 ===

def test_pr8_build_contacts_chunk_uses_effective_permission():
    """PR #8: _build_contacts_chunk 用 effective_permission, 不使用原 permission

    模拟 D-054 真实场景: H-惠州 (标 public) + 1 internal 共用 `010-64537139`,
    期望 contact 标注 `→ RESTRICTED (PR#8 conflict)`, 不进 phone/email 字段.
    """
    cities = [
        {**c, "iata": c["code"][:3].upper(), "content_md": ""}  # _build_contacts_chunk 需要 iata + content_md
        for c in SCENARIO_1_PUBLIC_1_INTERNAL
    ]
    # 模拟 build 阶段 canonical identity 计算
    identity = build_canonical_identity(cities)
    cities = annotate_contacts_with_effective_permission(cities, identity)

    # 验证 2 city 的 contact 都被标 restricted
    for city in cities:
        for ct in city["contacts"]:
            assert ct["effective_permission"] == "restricted", f"city {city['code']} 应 restricted, 实际 {ct['effective_permission']}"

    # 验证 _build_contacts_chunk 输出
    for city in cities:
        chunk = _build_contacts_chunk(city)
        assert chunk is not None
        # 严禁 phone 原值进 chunk
        assert "010-64537139" not in chunk, f"PR #8 严禁 phone 进 chunk (city {city['code']})"
        # 应该有 RESTRICTED 标签 + 联系方式 REDACTED
        assert "RESTRICTED" in chunk, f"PR #8 应标 RESTRICTED, chunk: {chunk}"
        assert "[已脱敏/受限, 详情见 city detail API 权限检查]" in chunk


def test_pr8_build_contacts_chunk_pure_public_keeps_phone():
    """PR #8: 全 public → effective_permission=public, 保留 phone 进 chunk"""
    cities = [
        {**c, "iata": c["code"][:3].upper(), "content_md": ""}
        for c in SCENARIO_3_PURE_PUBLIC
    ]
    identity = build_canonical_identity(cities)
    cities = annotate_contacts_with_effective_permission(cities, identity)

    for city in cities:
        for ct in city["contacts"]:
            assert ct["effective_permission"] == "public", f"city {city['code']} 应 public"
        chunk = _build_contacts_chunk(city)
        assert chunk is not None
        # 公开 email 保留
        assert "aogoffice@airchina.com" in chunk, f"全 public 应保留 email, chunk: {chunk}"
        # 不应有 RESTRICTED 标签
        assert "RESTRICTED" not in chunk


# === PR #8 + pii_7a_check v2 CONFLICTED 分类测试 ===

def test_pr8_pii7a_v2_conflicted_classification(tmp_path):
    """PR #8: pii_7a_check v2 加 CONFLICTED 分类

    aog.db 含 1 public + 1 internal 共用同 phone, 但 build 阶段用 effective_permission=restricted
    (PR #8), 所以 FTS5 不应含 phone → PII-7a PASS (forbidden_hits=0).
    """
    import subprocess
    backend_root = PIPELINE_ROOT.parent / "backend"

    # 构造 aog.db (跟 SCENARIO_1 一致: 1 public + 1 internal 共用 010-64537139)
    db = tmp_path / "test_aog.db"
    import sqlite3
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE cities (id INTEGER PRIMARY KEY, code TEXT, name TEXT, content_md TEXT, contacts TEXT)")
    con.execute("INSERT INTO cities VALUES (1, 'M-CONFLICT-A', 'A', NULL, ?)",
                (json.dumps([{"org": "公开 AOG", "phone": ["010-64537139"], "permission": "public"}], ensure_ascii=False),))
    con.execute("INSERT INTO cities VALUES (2, 'M-CONFLICT-B', 'B', NULL, ?)",
                (json.dumps([{"org": "内部 vendor", "phone": ["010-64537139"], "permission": "internal"}], ensure_ascii=False),))
    con.commit()
    con.close()

    # 构造 fts5 (PR #8 build 阶段: effective_permission=restricted, phone 不进 chunk)
    fts5 = tmp_path / "fts5.db"
    con = sqlite3.connect(str(fts5))
    con.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index, tokenize='porter unicode61')
    """)
    # 不插入任何含 010-64537139 的 chunk (PR #8 build 阶段 effective_permission=restricted 不进)
    con.execute(
        "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "PR #8 严守: conflict phone 不进 chunk",
            "M-CONFLICT-A city_contacts",
            "/tmp/M-CONFLICT-A.docx",
            "M-CONFLICT-A",
            "city_contacts",
            "domestic", "active", "1", 0,
        ),
    )
    con.commit()
    con.close()

    # 跑 pii_7a_check v2 release mode
    result = subprocess.run(
        [
            str(backend_root / ".venv" / "bin" / "python"),
            "-u", "-m", "scripts.pii_7a_check",
            "--aog-db", str(db),
            "--fts5-db", str(fts5),
            "--release",
        ],
        cwd=str(PIPELINE_ROOT), capture_output=True, text=True, timeout=60,
    )
    combined = result.stdout + result.stderr
    # PR #8 期望: PII-7a PASS (FTS5 0 hit, 因为 build 阶段已降级)
    assert result.returncode == 0, (
        f"PR #8 期望 PII-7a PASS (FTS5 0 hit), 实际 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "PII-7a v2 PASS" in combined
    assert "forbidden_hits=0" in combined


def test_pr8_get_conflicted_values_helper():
    """PR #8: get_conflicted_values helper 返回跨 city conflict"""
    identity = build_canonical_identity(SCENARIO_1_PUBLIC_1_INTERNAL)
    conflicted = get_conflicted_values(identity)
    assert len(conflicted) == 1
    # canonical value 移除 dash (跟 _normalize_phone 一致)
    assert conflicted[0]["value"] == "01064537139"
    assert conflicted[0]["effective_permission"] == "restricted"
