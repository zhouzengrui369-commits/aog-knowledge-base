"""test_pii_7a_check.py — PII-7a v2 真实 KB FTS5 leak check 端到端测试 (NJX 7/31 D-054 拍板: provenance-aware gate)

NJX 7/30 PR #5 严令 5: PR #4 PII-7a 保留, 作为最终真实 KB Gate.
NJX 7/31 16:12 D-054 拍板: PII-7a 判定模型 v2 (provenance-aware), 在 PR #4 当前分支完成.

本测试覆盖:
  D-052 严令 4 (NJX 7/31 拍板):
    1. pass_when_sanitized — 干净 FTS5 → PASS
    2. fail_when_leaked — LEAKED FTS5 → FAIL
    3. fail_when_empty_db — 严禁 SKIP-on-empty → FAIL
    4. fail_when_no_fts5_table — 严禁 SKIP-on-no-fts5 → FAIL
    5. excludes_public_contacts — 公开 contact 在 city_contacts chunk ALLOWED
  D-054 v2 严令 (NJX 7/31 16:12):
    6. v2_public_only_hit — PUBLIC_ONLY 全部 hits in city_contacts → ALLOWED
    7. v2_non_public_only_hit — NON_PUBLIC_ONLY 任意 hit → FORBIDDEN
    8. v2_mixed_public_only_hit — MIXED 但 hits 都在 city_contacts → FORBIDDEN
    9. v2_mixed_non_public_hit — MIXED 含 non-public hit → FORBIDDEN
   10. v2_public_value_free_text_hit — 公开 value 进 free-text chunk → FORBIDDEN
   11. v2_34_public_1_internal_shared_corporate_desk — 公知共享邮箱 mixed → FORBIDDEN

运行:
  cd aog-web/pipeline
  ../backend/.venv/bin/python -m pytest tests/test_pii_7a_check.py -v --tb=short
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PIPELINE_ROOT.parent / "backend"
SCRIPTS_DIR = PIPELINE_ROOT / "scripts"
for p in (str(SCRIPTS_DIR), str(BACKEND_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


# === fixtures: 恶意 aog.db + 干净 FTS5 / 漏脱敏 FTS5 ===

@pytest.fixture
def malicious_aog_db(tmp_path):
    """构造恶意 fixture aog.db (含 non-public phone + email + 公开 phone 对照)

    D-052 严令 4 (NJX 7/31 拍板): 使用真实 schema (content_md + contacts),
    严禁使用 summary/contacts_json (跟 schema 不匹配, 旧 PR #5 行为 SKIP 假绿).
    """
    db = tmp_path / "malicious_aog.db"
    con = sqlite3.connect(str(db))
    # 真实 schema: content_md + contacts (T3 schema)
    con.execute("""
        CREATE TABLE cities (
            id INTEGER PRIMARY KEY,
            code TEXT,
            name TEXT,
            content_md TEXT,
            contacts TEXT
        )
    """)
    con.execute(
        "INSERT INTO cities VALUES (1, 'M-TEST', 'MALICIOUS', ?, ?)",
        (
            "测试恶意 city 含 vendor phone +86 13908081935 和 litao010@163.com\nAOG总台: 010-64537139",
            json.dumps([
                {"org": "公开 AOG", "phone": ["+86-21-62690267"], "permission": "public"},  # 公开
                {"org": "内部 vendor", "phone": ["+86 18600051432"], "permission": "internal"},  # internal
                {"org": "restricted", "phone": ["+44 208 562 3007"], "permission": "restricted"},  # restricted
                {"org": "redacted", "phone": ["13908081935"], "permission": "internal", "redacted": True},  # redacted
            ], ensure_ascii=False),
        ),
    )
    con.execute(
        "INSERT INTO cities VALUES (2, 'M-CLEAN', 'CLEAN', ?, ?)",
        (
            "干净 city 无 PII 件号 3-1531 ISO 9001",
            json.dumps([]),
        ),
    )
    con.commit()
    con.close()
    return db


def _create_fts5_db(fts5_path: Path, *, leaked: bool = False) -> None:
    """构造 fts5_index.db (含 chunks_fts_content 表)
    leaked=False: 干净 (REDACTED marker)
    leaked=True: 含原值 phone (模拟 sanitizer 漏脱敏)
    """
    con = sqlite3.connect(str(fts5_path))
    con.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index, tokenize='porter unicode61')
    """)
    if leaked:
        # 模拟漏脱敏: 含 +86 13908081935 原值
        con.execute(
            "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "vendor phone +86 13908081935 这是 LEAKED",
                "MALICIOUS chunk",
                "/tmp/M-TEST.docx",
                "1",
                "city",
                "domestic",
                "active",
                "1",
                0,
            ),
        )
    else:
        # 干净: 只有 [PHONE_REDACTED] marker
        con.execute(
            "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "vendor phone [PHONE_REDACTED] 这是 clean",
                "MALICIOUS chunk",
                "/tmp/M-TEST.docx",
                "1",
                "city",
                "domestic",
                "active",
                "1",
                0,
            ),
        )
    con.commit()
    con.close()


# === tests ===

def test_pii_7a_pass_when_sanitized(malicious_aog_db, tmp_path):
    """恶意 aog.db + 干净 FTS5 → PII-7a v2 PASS (FTS5 0 命中)"""
    fts5 = tmp_path / "fts5_clean.db"
    _create_fts5_db(fts5, leaked=False)

    result = subprocess.run(
        [
            str(BACKEND_ROOT / ".venv" / "bin" / "python"),
            "-u",
            "-m",
            "scripts.pii_7a_check",
            "--aog-db", str(malicious_aog_db),
            "--fts5-db", str(fts5),
            "--max-samples", "100",
        ],
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = result.stdout + result.stderr
    # exit 0
    assert result.returncode == 0, f"pii_7a_check 应 exit 0, 实际 {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    # PASS (D-054 v2: PII-7a v2 PASS)
    assert "PII-7a v2 PASS" in combined, f"应输出 PII-7a v2 PASS, 实际: {combined}"
    # 严禁明文
    assert "+86 13908081935" not in combined, "PII 明文泄漏到日志"
    assert "litao010@163.com" not in combined, "PII email 明文泄漏到日志"


def test_pii_7a_fail_when_leaked(malicious_aog_db, tmp_path):
    """恶意 aog.db + LEAKED FTS5 → PII-7a v2 FAIL (FTS5 命中)"""
    fts5 = tmp_path / "fts5_leaked.db"
    _create_fts5_db(fts5, leaked=True)

    result = subprocess.run(
        [
            str(BACKEND_ROOT / ".venv" / "bin" / "python"),
            "-u",
            "-m",
            "scripts.pii_7a_check",
            "--aog-db", str(malicious_aog_db),
            "--fts5-db", str(fts5),
            "--max-samples", "100",
        ],
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = result.stdout + result.stderr
    # exit 4 (跟 build-data-release.sh 一致)
    assert result.returncode == 4, f"pii_7a_check 应 exit 4 (FAIL), 实际 {result.returncode}"
    # FAIL (D-054 v2: PII-7a v2 FAIL)
    assert "PII-7a v2 FAIL" in combined, f"应输出 PII-7a v2 FAIL, 实际: {combined}"
    # hash 12 字符 (12 hex chars)
    assert any(len(line.split()[0]) == 12 and all(c in "0123456789abcdef" for c in line.split()[0])
               for line in combined.splitlines() if line.strip().startswith(tuple("0123456789abcdef"))), (
        f"PII-7a v2 FAIL 应列 hash 12 字符, 实际: {combined}"
    )
    # 严禁明文
    assert "+86 13908081935" not in combined, "PII 明文泄漏到日志 (FAIL 报告也禁明文)"


def test_pii_7a_fail_when_empty_db(tmp_path):
    """空 aog.db (无 non-public PII) → PII-7a FAIL (exit 4, 严禁 SKIP)

    D-052 严令 4 (NJX 7/31 拍板): 严禁 SKIP-on-empty, 必须 FAIL 提醒 owner 数据可能有问题.
    """
    db = tmp_path / "empty.db"
    con = sqlite3.connect(str(db))
    # 真实 schema (D-052 严令 4: schema 必须匹配)
    con.execute("CREATE TABLE cities (id INTEGER PRIMARY KEY, code TEXT, name TEXT, content_md TEXT, contacts TEXT)")
    con.execute("INSERT INTO cities VALUES (1, 'M-EMPTY', 'EMPTY', NULL, NULL)")
    con.commit()
    con.close()
    fts5 = tmp_path / "fts5.db"
    _create_fts5_db(fts5, leaked=False)

    result = subprocess.run(
        [
            str(BACKEND_ROOT / ".venv" / "bin" / "python"),
            "-u",
            "-m",
            "scripts.pii_7a_check",
            "--aog-db", str(db),
            "--fts5-db", str(fts5),
        ],
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = result.stdout + result.stderr
    # D-052 严令: 无 non-public PII 必须 FAIL (exit 4), 严禁 SKIP
    assert result.returncode == 4, f"空 DB 应 exit 4 (FAIL), 实际 {result.returncode}\nstderr: {result.stderr}"
    assert "FAIL" in combined
    # 严禁 "⚠️  PII-7a SKIP" (旧 SKIP 标记, "严禁" 字符串里有 "SKIP" 字样但不是 SKIP 标记)
    assert "PII-7a SKIP" not in combined, f"D-052 严禁 SKIP-on-empty, 实际: {combined}"


def test_pii_7a_fail_when_no_fts5_table(malicious_aog_db, tmp_path):
    """fts5_index.db 无 chunks_fts_content 表 → FAIL (exit 4, D-052 严禁 SKIP)

    D-052 严令 4: 严禁 SKIP-on-no-fts5, 必须 FAIL 提醒 owner fts5_index.db 不完整.
    """
    fts5 = tmp_path / "fts5_no_table.db"
    con = sqlite3.connect(str(fts5))
    con.execute("CREATE TABLE dummy (x INTEGER)")  # 无 chunks_fts_content
    con.commit()
    con.close()

    result = subprocess.run(
        [
            str(BACKEND_ROOT / ".venv" / "bin" / "python"),
            "-u",
            "-m",
            "scripts.pii_7a_check",
            "--aog-db", str(malicious_aog_db),
            "--fts5-db", str(fts5),
        ],
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = result.stdout + result.stderr
    # D-052 严令: 无 chunks_fts_content 表必须 FAIL (exit 4), 严禁 SKIP
    assert result.returncode == 4, f"无 chunks_fts_content 表应 FAIL (exit 4), 实际 {result.returncode}\nstderr: {result.stderr}"
    assert "FAIL" in combined
    assert "PII-7a SKIP" not in combined, f"D-052 严禁 SKIP-on-no-fts5, 实际: {combined}"


def test_pii_7a_excludes_public_contacts(malicious_aog_db, tmp_path):
    """公开 AOG contact (+86-21-62690267) 在 city_contacts chunk → PII-7a v2 PASS (D-054 v2 严令)

    D-054 v2 (NJX 7/31): 公开 contact 抽到 (values_skipped=0), 但只在 city_contacts chunk
    出现时 ALLOWED. D-052 _build_contacts_chunk 实际行为: public contact 进 city_contacts chunk.
    """
    fts5 = tmp_path / "fts5_with_public.db"
    # 公开 phone 在 city_contacts chunk 里 (D-052 _build_contacts_chunk 实际行为)
    con = sqlite3.connect(str(fts5))
    con.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index, tokenize='porter unicode61')
    """)
    con.execute(
        "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "公开 AOG 总台: +86-21-62690267 (D-030 合同允许, D-052 进 city_contacts chunk)",
            "M-TEST city_contacts chunk",
            "/tmp/M-TEST.docx",
            "1",
            "city_contacts",  # D-052 严令 1: 公开 contact 进 city_contacts chunk
            "domestic",
            "active",
            "1",
            0,
        ),
    )
    con.commit()
    con.close()

    result = subprocess.run(
        [
            str(BACKEND_ROOT / ".venv" / "bin" / "python"),
            "-u",
            "-m",
            "scripts.pii_7a_check",
            "--aog-db", str(malicious_aog_db),
            "--fts5-db", str(fts5),
        ],
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = result.stdout + result.stderr
    # D-054 v2 严令: 公开 contact phone 在 city_contacts chunk 应 ALLOWED → PASS
    assert result.returncode == 0, f"公开 contact 在 city_contacts chunk 不应触发 FAIL, 实际 {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "PII-7a v2 PASS" in combined, f"应 PASS (D-054 v2: 公开 contact ALLOWED in city_contacts), 实际: {combined}"


# === D-054 v2 mixed-classification 回归测试 (NJX 7/31 16:12 拍板 6 项) ===

def _create_fts5_with_chunks(fts5_path: Path, chunks: list[dict]) -> None:
    """构造 fts5_index.db 含指定 chunks (每 chunk: content/source_type/source_id/source_path/title)."""
    con = sqlite3.connect(str(fts5_path))
    con.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index, tokenize='porter unicode61')
    """)
    for c in chunks:
        con.execute(
            "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                c["content"],
                c.get("title", "test chunk"),
                c.get("source_path", "/tmp/test.docx"),
                c.get("source_id", "1"),
                c["source_type"],
                c.get("region", "domestic"),
                c.get("status", "active"),
                c.get("doc_id", "1"),
                c.get("chunk_index", 0),
            ),
        )
    con.commit()
    con.close()


def _run_pii_7a(aog_db: Path, fts5_db: Path, *, release: bool = False, max_samples: int | None = None) -> subprocess.CompletedProcess:
    args = [
        str(BACKEND_ROOT / ".venv" / "bin" / "python"),
        "-u", "-m", "scripts.pii_7a_check",
        "--aog-db", str(aog_db),
        "--fts5-db", str(fts5_db),
    ]
    if release:
        args.append("--release")
    elif max_samples is not None:
        args += ["--max-samples", str(max_samples)]
    return subprocess.run(
        args, cwd=str(PIPELINE_ROOT), capture_output=True, text=True, timeout=60,
    )


def _build_aog_db_with_contacts(tmp_path: Path, cities: list[dict]) -> Path:
    """构造 aog.db 含指定 city + contacts (NJX 7/31 D-054 v2 真实 schema)."""
    db = tmp_path / "test_aog.db"
    con = sqlite3.connect(str(db))
    con.execute("""
        CREATE TABLE cities (
            id INTEGER PRIMARY KEY, code TEXT, name TEXT,
            content_md TEXT, contacts TEXT
        )
    """)
    for i, c in enumerate(cities, 1):
        con.execute(
            "INSERT INTO cities VALUES (?, ?, ?, ?, ?)",
            (i, c["code"], c["name"], c.get("content_md"), json.dumps(c.get("contacts", []), ensure_ascii=False)),
        )
    con.commit()
    con.close()
    return db


def test_v2_public_only_hit(tmp_path):
    """D-054 v2 测试 1: PUBLIC_ONLY 全部 hits 在 city_contacts chunk → ALLOWED → PASS

    构造: 公开 contact phone `+86-21-62690267` 在 aog.db, FTS5 含 city_contacts chunk 命中.
    期望: classification=PUBLIC_ONLY, decision=ALLOWED, exit 0.
    """
    aog_db = _build_aog_db_with_contacts(tmp_path, [
        {
            "code": "M-PUB", "name": "PUB",
            "content_md": None,
            "contacts": [{"org": "公开 AOG", "phone": ["+86-21-62690267"], "permission": "public"}],
        },
    ])
    fts5 = tmp_path / "fts5.db"
    _create_fts5_with_chunks(fts5, [
        {
            "content": "公开 AOG 总台: +86-21-62690267 (D-052 严令 1 允许进 city_contacts chunk)",
            "source_type": "city_contacts",
            "source_id": "M-PUB",
            "source_path": "02_外战预案/M-PUB.docx",
        },
    ])

    result = _run_pii_7a(aog_db, fts5, max_samples=100)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, f"D-054 v2 PUBLIC_ONLY 应 PASS, 实际 {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "PII-7a v2 PASS" in combined, f"应输出 PII-7a v2 PASS, 实际: {combined}"
    # metrics 验证
    assert "public_only=1" in combined, f"应有 public_only=1 metric, 实际: {combined}"
    assert "allowed_public_hits=1" in combined, f"应有 allowed_public_hits=1, 实际: {combined}"
    assert "forbidden_hits=0" in combined, f"应有 forbidden_hits=0, 实际: {combined}"


def test_v2_non_public_only_hit(tmp_path):
    """D-054 v2 测试 2: NON_PUBLIC_ONLY 任意 hit → FORBIDDEN → FAIL

    构造: internal contact phone 在 city chunk (free-text).
    期望: classification=NON_PUBLIC_ONLY, decision=FORBIDDEN, exit 4.
    """
    aog_db = _build_aog_db_with_contacts(tmp_path, [
        {
            "code": "M-INT", "name": "INT",
            "content_md": None,
            "contacts": [{"org": "内部 vendor", "phone": ["+8618600051432"], "permission": "internal"}],
        },
    ])
    fts5 = tmp_path / "fts5.db"
    _create_fts5_with_chunks(fts5, [
        {
            "content": "内部 vendor phone +8618600051432 (D-052 修后不应进任何 chunk)",
            "source_type": "city",  # forbidden chunk source
            "source_id": "M-INT",
            "source_path": "02_外战预案/M-INT.docx",
        },
    ])

    result = _run_pii_7a(aog_db, fts5, max_samples=100)
    combined = result.stdout + result.stderr
    assert result.returncode == 4, f"D-054 v2 NON_PUBLIC_ONLY 应 FAIL, 实际 {result.returncode}"
    assert "PII-7a v2 FAIL" in combined, f"应输出 PII-7a v2 FAIL, 实际: {combined}"
    assert "forbidden_hits=1" in combined, f"应有 forbidden_hits=1, 实际: {combined}"
    assert "non_public_only=1" in combined, f"应有 non_public_only=1, 实际: {combined}"


def test_v2_mixed_public_only_hit(tmp_path):
    """D-054 v2 测试 3 (PR #8 严守后改): 跨 city public + internal → CONFLICTED → FORBIDDEN

    构造: 同一 phone 在 1 个公开 contact + 1 个 internal contact, FTS5 hits 都在 city_contacts.
    PR #8 (NJX 7/31 18:28 拍板) 严守: 跨 city 出现 public + non-public → CONFLICTED,
    跟 NON_PUBLIC_ONLY 一样决策: 任意 hit → FORBIDDEN (保守原则).
    期望: classification=CONFLICTED, decision=FORBIDDEN, exit 4.

    注: 之前 D-054 v2 期望 MIXED + 全 city_contacts hit → ALLOWED.
    PR #8 后, 跨 city permission 冲突标 CONFLICTED, 严守 NON_PUBLIC_ONLY 同等决策.
    PR #8 build 阶段 (canonical identity + effective_permission) 降级后, FTS5 不含 conflict
    value, PII-7a OK. 但 unit test 模拟的 aog.db 没经过 build 降级, PII-7a 看到 conflict → FORBIDDEN.
    """
    shared_phone = "+8618800009999"
    aog_db = _build_aog_db_with_contacts(tmp_path, [
        {
            "code": "M-MIX-A", "name": "MIX-A",
            "content_md": None,
            "contacts": [
                {"org": "公开 AOG", "phone": [shared_phone], "permission": "public"},
                {"org": "内部 vendor", "phone": [shared_phone], "permission": "internal"},
            ],
        },
    ])
    fts5 = tmp_path / "fts5.db"
    _create_fts5_with_chunks(fts5, [
        {
            "content": f"公开 + 内部共用 phone {shared_phone} 进 city_contacts chunk",
            "source_type": "city_contacts",
            "source_id": "M-MIX-A",
            "source_path": "02_外战预案/M-MIX-A.docx",
        },
    ])

    result = _run_pii_7a(aog_db, fts5, max_samples=100)
    combined = result.stdout + result.stderr
    # PR #8 严守: 跨 city public + internal → CONFLICTED → FORBIDDEN
    assert result.returncode == 4, f"PR #8 CONFLICTED 应 FAIL, 实际 {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "PII-7a v2 FAIL" in combined, f"应输出 PII-7a v2 FAIL, 实际: {combined}"
    assert "conflicted=1" in combined, f"应有 conflicted=1, 实际: {combined}"
    assert "forbidden_hits=1" in combined, f"应有 forbidden_hits=1, 实际: {combined}"


def test_v2_mixed_non_public_hit(tmp_path):
    """D-054 v2 测试 4: MIXED value, 含 FTS5 hit 在 non-public source → FORBIDDEN → FAIL

    构造: 公开 contact phone 抽到, FTS5 命中 city_contacts (公开) + city (非 public 来源).
    期望: classification=MIXED, decision=FORBIDDEN (因为 FTS5 hit 含 non-public source), exit 4.
    """
    shared_phone = "+8618800008888"
    aog_db = _build_aog_db_with_contacts(tmp_path, [
        {
            "code": "M-LEAK", "name": "LEAK",
            "content_md": None,
            "contacts": [{"org": "公开 AOG", "phone": [shared_phone], "permission": "public"}],
        },
    ])
    fts5 = tmp_path / "fts5.db"
    _create_fts5_with_chunks(fts5, [
        {
            "content": f"公开 AOG: {shared_phone} (D-052 修后进 city_contacts chunk)",
            "source_type": "city_contacts",
            "source_id": "M-LEAK",
            "source_path": "02_外战预案/M-LEAK.docx",
        },
        {
            "content": f"docx 解析时 phone 误进 city content: {shared_phone}",
            "source_type": "city",  # 漏到 free-text chunk (D-053 应已修, 这里模拟失败)
            "source_id": "M-LEAK",
            "source_path": "02_外战预案/M-LEAK.docx",
        },
    ])

    result = _run_pii_7a(aog_db, fts5, max_samples=100)
    combined = result.stdout + result.stderr
    # D-054 v2 严令 4: 任何 FTS5 hit 在 forbidden source → FORBIDDEN
    assert result.returncode == 4, f"D-054 v2 MIXED non-public hit 应 FAIL, 实际 {result.returncode}"
    assert "PII-7a v2 FAIL" in combined, f"应输出 PII-7a v2 FAIL, 实际: {combined}"
    assert "forbidden_hits=1" in combined, f"应有 forbidden_hits=1, 实际: {combined}"


def test_v2_public_value_free_text_hit(tmp_path):
    """D-054 v2 测试 5: public value 命中 free-text chunk → FORBIDDEN

    构造: 公开 contact phone, FTS5 命中 city chunk (free-text, 不是 city_contacts).
    期望: classification=PUBLIC_ONLY, decision=FORBIDDEN (因为 hit 不在 allowed source), exit 4.
    """
    aog_db = _build_aog_db_with_contacts(tmp_path, [
        {
            "code": "M-FREE", "name": "FREE",
            "content_md": None,
            "contacts": [{"org": "公开 AOG", "phone": ["+86-21-62690267"], "permission": "public"}],
        },
    ])
    fts5 = tmp_path / "fts5.db"
    _create_fts5_with_chunks(fts5, [
        {
            "content": "公开 AOG 总台: +86-21-62690267 (误进 city free-text chunk)",
            "source_type": "city",  # 错位 chunk (D-052 _build_contacts_chunk 不应这样)
            "source_id": "M-FREE",
            "source_path": "02_外战预案/M-FREE.docx",
        },
    ])

    result = _run_pii_7a(aog_db, fts5, max_samples=100)
    combined = result.stdout + result.stderr
    # D-054 v2 严令 4: 任何 hit 在 forbidden source → FORBIDDEN
    assert result.returncode == 4, f"D-054 v2 public value free-text hit 应 FAIL, 实际 {result.returncode}"
    assert "PII-7a v2 FAIL" in combined, f"应输出 PII-7a v2 FAIL, 实际: {combined}"
    assert "forbidden_hits=1" in combined, f"应有 forbidden_hits=1, 实际: {combined}"


def test_v2_34_public_1_internal_shared_corporate_desk(tmp_path):
    """D-054 v2 测试 6 (PR #8 严守后改): 公知共享 corporate desk → CONFLICTED → FORBIDDEN

    场景 (NJX 7/31 D-054 真实根因): owner aog.db 含 `aogoffice@airchina.com` 公开邮箱在 116+ city
    共享, 但 1 个 internal contact 也引用这个邮箱. v2 判定 CONFLICTED (PR #8 严守).

    期望 (PR #8 NJX 7/31 18:28 拍板):
      - classification=CONFLICTED (1 public + 1 internal 共用 value)
      - 跟 NON_PUBLIC_ONLY 一样: 任意 hit → FORBIDDEN (保守原则, 严守 PII 隔离)
      - exit 4 (FAIL, 因为 PII 工具看到 conflict)

    注: 真实 KB rebuild 走 PR #8 build 阶段 (canonical identity + effective_permission 降级),
    FTS5 不含 conflict value, PII-7a OK. 但 unit test 模拟的 aog.db 没经过 build 降级,
    PII-7a 看到 conflict → FORBIDDEN. 跟 PR #8 严守一致.
    """
    shared_email = "aogoffice@airchina.com"  # 国航公知 AOG 邮箱
    cities = [
        # 34 个 city 公开 contact 都引用这个邮箱
        *[{
            "code": f"M-PUB-{i:02d}", "name": f"PUB-{i:02d}",
            "content_md": None,
            "contacts": [{"org": "国航 AOG", "email": shared_email, "permission": "public"}],
        } for i in range(34)],
        # 1 个 internal contact 误用这个邮箱 (e.g. 内部 vendor 备注)
        {
            "code": "M-INT-99", "name": "INT-99",
            "content_md": None,
            "contacts": [{"org": "内部 vendor", "email": shared_email, "permission": "internal"}],
        },
    ]
    aog_db = _build_aog_db_with_contacts(tmp_path, cities)

    fts5 = tmp_path / "fts5.db"
    # FTS5 命中 34 city_contacts chunks (公开部分) — 模拟未经过 PR #8 build 降级的旧 fts5
    chunks = [
        *[{
            "content": f"国航 AOG 邮箱: {shared_email} (D-052 严令 1 公开 contact 进 city_contacts)",
            "source_type": "city_contacts",
            "source_id": f"M-PUB-{i:02d}",
            "source_path": f"02_外战预案/M-PUB-{i:02d}.docx",
        } for i in range(34)],
    ]
    _create_fts5_with_chunks(fts5, chunks)

    result = _run_pii_7a(aog_db, fts5, max_samples=100)
    combined = result.stdout + result.stderr
    # PR #8 严守: 跨 city public + internal → CONFLICTED → FORBIDDEN
    assert result.returncode == 4, (
        f"PR #8 CONFLICTED 应 FAIL, 实际 {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "PII-7a v2 FAIL" in combined, f"应输出 PII-7a v2 FAIL, 实际: {combined}"
    assert "conflicted=1" in combined, f"应有 conflicted=1, 实际: {combined}"
    assert "forbidden_hits=1" in combined, f"应有 forbidden_hits=1, 实际: {combined}"
    # 严禁明文
    assert shared_email not in combined, f"PII email 明文泄漏: {combined}"
