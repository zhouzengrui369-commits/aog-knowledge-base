"""test_pii_7a_check.py — PII-7a 真实 KB FTS5 leak check 端到端测试 (NJX 7/30 PR #5 严令 5 项)

NJX 7/30 严令 5: PR #4 PII-7a 保留, 作为最终真实 KB Gate.
本测试验证 pii_7a_check.py 真实 KB 模式的正确性:
  1. 构造恶意 fixture aog.db (含 non-public phone + email)
  2. 构造 fts5_index.db (含 sanitized chunks, 不含原值)
  3. 跑 pii_7a_check → expect PASS (FTS5 0 命中)
  4. 构造 fts5_index.db (含 LEAKED 原值, 模拟 sanitizer 漏脱敏)
  5. 跑 pii_7a_check → expect FAIL (FTS5 命中)
  6. 验证 hash 12 字符 + 严禁明文

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
    """恶意 aog.db + 干净 FTS5 → PII-7a PASS (FTS5 0 命中)"""
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
    # PASS
    assert "PII-7a PASS" in combined, f"应输出 PII-7a PASS, 实际: {combined}"
    # 严禁明文
    assert "+86 13908081935" not in combined, "PII 明文泄漏到日志"
    assert "litao010@163.com" not in combined, "PII email 明文泄漏到日志"


def test_pii_7a_fail_when_leaked(malicious_aog_db, tmp_path):
    """恶意 aog.db + LEAKED FTS5 → PII-7a FAIL (FTS5 命中)"""
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
    # FAIL
    assert "PII-7a FAIL" in combined, f"应输出 PII-7a FAIL, 实际: {combined}"
    # hash 12 字符 (12 hex chars)
    assert any(len(line.split()[0]) == 12 and all(c in "0123456789abcdef" for c in line.split()[0])
               for line in combined.splitlines() if line.strip().startswith(tuple("0123456789abcdef"))), (
        f"PII-7a FAIL 应列 hash 12 字符, 实际: {combined}"
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
    """公开 AOG contact (+86-21-62690267) 不在 PII-7a 抽样 (D-030 合同)"""
    fts5 = tmp_path / "fts5_with_public.db"
    # 公开 phone 在 fts5 里 (设计内, _build_contacts_chunk 处理)
    con = sqlite3.connect(str(fts5))
    con.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index, tokenize='porter unicode61')
    """)
    con.execute(
        "INSERT INTO chunks_fts(content, title, source_path, source_id, source_type, region, status, doc_id, chunk_index) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "公开 AOG 总台: +86-21-62690267 (D-030 合同允许)",
            "M-TEST chunk",
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
    # 公开 contact phone 不算 PII, 应该 PASS (因为内部 vendor phone 已脱敏, FTS5 只含公开)
    assert result.returncode == 0, f"公开 contact 不应触发 FAIL, 实际 {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "PII-7a PASS" in combined, f"应 PASS (公开 contact 不算 PII), 实际: {combined}"
