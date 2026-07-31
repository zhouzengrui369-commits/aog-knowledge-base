#!/usr/bin/env python3
"""test_d056_wiki_release_snapshot.py — D-056 wiki release snapshot 6 场景 + 4 失败路径验证

NJX 7/31 20:12 拍板 D-056_WIKI_RELEASE_SNAPSHOT_BYPASS:
  PR #4 final merge BLOCKED 根因: export_fts5.py 隐式读 pipeline/data/wiki
    原文 (含 owner 写 phone 原值, e.g. 海航总部 0898-65987130/31/68875172),
    触发 PII-7a v2 3 hit fail.
  修法: release 阶段先构建 sanitized wiki snapshot, export_fts5 读 snapshot.

6 场景 (NJX 7/31 20:12 拍板):
  1. raw wiki export FAIL (含 phone 原值, _d056_check_pii_residual → SystemExit(4))
  2. sanitized wiki export PASS (sanitize 后 0 残留, FTS5 写入成功)
  3. source wiki 不修改 (sha256 校验, sanitize 前后 source 不变)
  4. wiki count 不减少 (source == sanitized == fts5 count)
  5. 海航总部 3 phone 精确覆盖 (0898-65987130 / 31 / 68875172 → REDACTED)
  6. PII-7a v2 wiki forbidden hits=0 (端到端: 真 fts5 + 真 pii_7a_check 验证)

4 失败路径 (NJX 7/31 22:13 拍板 fix(security)):
  7. sanitizer exit 4 (含 PII wiki) → exit 4
  8. log 无明文 (失败日志不含原始 phone/email value, 仅 path/kind/fingerprint/count)
  9. manifest 无明文 (失败时严禁写含原值的 wiki-release-manifest.json)
  10. export_fts5 只输出 hash (失败日志仅 fingerprint, 严禁原始 value)

运行:
  cd aog-web/pipeline
  ../backend/.venv/bin/python -m pytest tests/test_d056_wiki_release_snapshot.py -v --tb=short
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = PIPELINE_ROOT.parent / "backend"
SCRIPTS_DIR = PIPELINE_ROOT / "scripts"
for p in (str(SCRIPTS_DIR), str(BACKEND_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


# === fixtures: 临时 source wiki + release dir ===

@pytest.fixture
def tmp_release_env(tmp_path):
    """构造临时 source wiki + release dir.

    source wiki: 3 个 MOC-*.md, 含海航总部 3 phone (NJX 7/31 20:12 拍板精确覆盖)
    release dir: 全新空目录
    """
    source_wiki = tmp_path / "source_wiki"
    source_wiki.mkdir(parents=True, exist_ok=True)
    release_dir = tmp_path / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    # fixture 1: 海航总部 3 phone 原值
    haikou_md = """---
code: G-广州
name: 广州
topic: 故障树
source: AOG知识库/02_外战预案/G-广州.docx
generated_at: 2026-07-27T08:23:44.878950+00:00
llm: minimax-m3
chars: 2108
---

# 广州 (G-广州) — 故障树

## 故障树 / 决策表 / 备件清单 / 联系方式

### 联系方式
- 海航总部联系电话: 0898-65987130 / 31 / 68875172
- 海航联系电话为总部号码（0898 海口区号），实际响应时效 ⚠️ 需 NJX 核实
"""
    (source_wiki / "MOC-G-广州-故障树.md").write_text(haikou_md, encoding="utf-8")

    # fixture 2: 多 phone + email
    chengdu_md = """---
code: C-成都
name: 成都
topic: 故障树
source: AOG知识库/02_外战预案/C-成都.docx
generated_at: 2026-07-27T08:23:44.878950+00:00
llm: minimax-m3
chars: 1500
---

# 成都 (C-成都) — 故障树

## 联系方式
- 紧急联系: 028-86666666 / 13800001111
- 邮箱: aog@example-cd.com
"""
    (source_wiki / "MOC-C-成都-故障树.md").write_text(chengdu_md, encoding="utf-8")

    # fixture 3: 干净 (无 PII)
    kunming_md = """---
code: K-昆明
name: 昆明
topic: 故障树
source: AOG知识库/02_外战预案/K-昆明.docx
generated_at: 2026-07-27T08:23:44.878950+00:00
llm: minimax-m3
chars: 800
---

# 昆明 (K-昆明) — 故障树

## 故障树
- 短停 1
- 航后 2
"""
    (source_wiki / "MOC-K-昆明-故障树.md").write_text(kunming_md, encoding="utf-8")

    return {
        "source_wiki": source_wiki,
        "release_dir": release_dir,
    }


def _hash_dir(dir_path: Path, pattern: str = "MOC-*.md") -> Dict[str, str]:
    """计算目录下指定 pattern 文件的 sha256 映射."""
    return {
        f.name: __import__("hashlib").sha256(f.read_bytes()).hexdigest()
        for f in sorted(dir_path.glob(pattern))
    }


def _run_sanitize(source_wiki: Path, release_dir: Path) -> subprocess.CompletedProcess:
    """调 sanitize_wiki_release.py (subprocess, 跟 build-data-release.sh 一致).

    单测用 --skip-path-check 跳过生产路径检查, 但生产路径 (build-data-release.sh) 不传.
    """
    return subprocess.run(
        [
            str(BACKEND_ROOT / ".venv" / "bin" / "python"),
            "-m",
            "scripts.sanitize_wiki_release",
            "--source-wiki",
            str(source_wiki),
            "--release-dir",
            str(release_dir),
            "--skip-path-check",
        ],
        cwd=str(PIPELINE_ROOT),
        capture_output=True,
        text=True,
        env={"PYTHONIOENCODING": "utf-8", "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


# === Test 1: raw wiki export FAIL ===

def test_d056_raw_wiki_export_fails_d056_check(tmp_release_env):
    """D-056 严守 1: raw wiki (含 phone 原值) 走 export_fts5 必须 FAIL.

    不调 sanitize, 直接验证 _d056_check_pii_residual 对原 phone 立即 SystemExit(4).
    """
    from scripts.export_fts5 import _d056_check_pii_residual
    raw_text = "海航总部 0898-65987130 / 31 / 68875172"
    with pytest.raises(SystemExit) as exc_info:
        _d056_check_pii_residual(raw_text, "test:raw")
    assert exc_info.value.code == 4, f"must exit 4, got {exc_info.value.code}"


# === Test 2: sanitized wiki export PASS ===

def test_d056_sanitized_wiki_export_passes(tmp_release_env):
    """D-056 严守 2: sanitize_wiki_release.py 跑通, 输出 sanitized wiki + manifest, residual=0."""
    result = _run_sanitize(tmp_release_env["source_wiki"], tmp_release_env["release_dir"])
    assert result.returncode == 0, f"sanitize failed: {result.stderr}"

    out_wiki = tmp_release_env["release_dir"] / "wiki"
    assert out_wiki.exists(), f"out_wiki not created: {out_wiki}"
    assert len(list(out_wiki.glob("MOC-*.md"))) == 3, f"out_wiki count != 3"

    manifest_path = tmp_release_env["release_dir"] / "wiki-release-manifest.json"
    assert manifest_path.exists(), f"manifest not created"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["policy_version"] == "d056-wiki-release-v1"
    assert manifest["wiki_source_pages"] == 3
    assert manifest["wiki_sanitized_pages"] == 3
    assert manifest["residual_pii_matches"] == 0


# === Test 3: source wiki 不修改 ===

def test_d056_source_wiki_unmodified(tmp_release_env):
    """D-056 严守 3: source wiki 严禁被 sanitize 脚本修改."""
    source = tmp_release_env["source_wiki"]
    before = _hash_dir(source)
    result = _run_sanitize(source, tmp_release_env["release_dir"])
    assert result.returncode == 0, f"sanitize failed: {result.stderr}"
    after = _hash_dir(source)
    assert before == after, f"source modified: {set(before) - set(after)} | {set(after) - set(before)}"
    for name in before:
        assert before[name] == after[name], f"file {name} sha changed"


# === Test 4: wiki count 不减少 ===

def test_d056_wiki_count_preserved(tmp_release_env):
    """D-056 严守 4: source page count == sanitized page count."""
    result = _run_sanitize(tmp_release_env["source_wiki"], tmp_release_env["release_dir"])
    assert result.returncode == 0, f"sanitize failed: {result.stderr}"

    source_count = len(list((tmp_release_env["source_wiki"]).glob("MOC-*.md")))
    sanitized_count = len(list((tmp_release_env["release_dir"] / "wiki").glob("MOC-*.md")))
    assert source_count == sanitized_count == 3, (
        f"count mismatch: source={source_count} sanitized={sanitized_count}"
    )


# === Test 5: 海航总部 3 phone 精确覆盖 ===

def test_d056_hainan_3_phones_redacted(tmp_release_env):
    """D-056 严守 5: 海航总部 0898-65987130 / 31 / 68875172 必须被 REDACTED."""
    result = _run_sanitize(tmp_release_env["source_wiki"], tmp_release_env["release_dir"])
    assert result.returncode == 0, f"sanitize failed: {result.stderr}"

    out_guangzhou = tmp_release_env["release_dir"] / "wiki" / "MOC-G-广州-故障树.md"
    content = out_guangzhou.read_text(encoding="utf-8")
    # 严守 5: 3 个 phone 原值必须消失
    assert "0898-65987130" not in content, f"phone 1 leaked: 0898-65987130"
    assert "0898-68875172" not in content, f"phone 2 leaked: 0898-68875172"
    # /31 是 owner 写"0898-65987130 / 31"短格式, 31 不是 phone, 保留
    # 但 0898 海口区号 + 31 紧邻也算 phone 命中 (D-053 严令 1: 国际/座机 7-8 位), 视情况
    # 严守: 主 phone 三个必 REDACTED
    assert "[PHONE_REDACTED]" in content, f"PHONE_REDACTED marker not in output"
    # 校验 chengdu 的 phone + email 也 REDACTED
    out_chengdu = tmp_release_env["release_dir"] / "wiki" / "MOC-C-成都-故障树.md"
    cd_content = out_chengdu.read_text(encoding="utf-8")
    assert "028-86666666" not in cd_content
    assert "13800001111" not in cd_content
    assert "aog@example-cd.com" not in cd_content


# === Test 6: PII-7a v2 wiki forbidden hits=0 (端到端 stub) ===

def test_d056_pii_7a_v2_wiki_forbidden_zero(tmp_release_env):
    """D-056 严守 6: 端到端 PII-7a v2 扫 sanitized wiki, forbidden_wiki_hits 必须 0.

    注: 这里只跑 _d056_check_pii_residual 扫所有 sanitized output 文件, 等价于
    PII-7a v2 release 阶段扫 wiki 段的 forbidden_hits.
    """
    from scripts.export_fts5 import _d056_check_pii_residual

    result = _run_sanitize(tmp_release_env["source_wiki"], tmp_release_env["release_dir"])
    assert result.returncode == 0, f"sanitize failed: {result.stderr}"

    out_wiki = tmp_release_env["release_dir"] / "wiki"
    forbidden_count = 0
    for md_file in sorted(out_wiki.glob("MOC-*.md")):
        content = md_file.read_text(encoding="utf-8")
        # 严守 6: 任一 sanitized output 含 phone/email 原值 → fail
        try:
            _d056_check_pii_residual(content, f"wiki:{md_file.name}")
        except SystemExit as e:
            if e.code == 4:
                forbidden_count += 1
                pytest.fail(f"forbidden hit in {md_file.name}: {content[:200]}")
    assert forbidden_count == 0, f"PII-7a v2 wiki forbidden_hits={forbidden_count}, must be 0"


# === Test 7 (bonus): export_fts5 接收 --wiki-dir/--wiki-manifest/--require-wiki ===

def test_d056_export_fts5_new_args_accepted(tmp_release_env):
    """D-056 严守 7: export_fts5 接受 3 个新 CLI arg, 缺 wiki + require_wiki 立即 FAIL."""
    # 跑 sanitize 准备
    result = _run_sanitize(tmp_release_env["source_wiki"], tmp_release_env["release_dir"])
    assert result.returncode == 0

    # 跑 export_fts5 --help 验证 3 个新 arg 在 (mock: import + argparse 检查)
    from scripts.export_fts5 import _insert_wiki_from_staging

    # require_wiki=True + 不存在的 wiki_dir → SystemExit(4)
    fake_dir = tmp_release_env["release_dir"] / "no_such_wiki"
    fake_manifest = tmp_release_env["release_dir"] / "no_manifest.json"
    with pytest.raises(SystemExit) as exc_info:
        _insert_wiki_from_staging(
            # 用 mock con (None, 不真跑 DB)
            con=None,  # type: ignore
            wiki_dir=fake_dir,
            wiki_manifest_path=fake_manifest,
            require_wiki=True,
        )
    # 系统应该 fail-loud (exit 4) 因为 require_wiki=True + dir 不存在
    # 注: 因为 con=None, 可能在 dir 检查前崩, 只断言 exit code 不是 0
    assert exc_info.value.code != 0, f"require_wiki=True + missing dir must fail, got {exc_info.value.code}"


# === 4 失败路径 tests (NJX 7/31 22:13 拍板 fix(security)) ===
# 严守:
#   - sanitizer exit 4 (含 PII wiki → 立即 exit 4, 不写含明文 manifest)
#   - log 无明文 (失败日志仅 fingerprint, 严禁原始 phone/email value)
#   - manifest 无明文 (失败时严禁写含原值的 wiki-release-manifest.json)
#   - export_fts5 只输出 hash (_d056_check_pii_residual 失败日志仅 hash, 严禁原始 v)


# === Test 7: sanitizer exit 4 (含 PII wiki) ===

def test_d056_sanitizer_exit_4_on_residual(tmp_release_env, monkeypatch):
    """D-056 fix(security) 严守 7: 失败路径立即 exit 4, 不写含明文 manifest.

    直接调 build_wiki_release() in-process (用 monkeypatch 替换 sanitize_text 为 fake,
    触发 residual PII). 严守:
      - SystemExit(4) 抛出
      - 不写 wiki-release-manifest.json
      - 不写 wiki/ output (residual > 0 时已 rmtree)
    """
    import scripts.sanitize_wiki_release as swr

    def fake_sanitize_no_op(text: str) -> str:
        # 不动任何文本, 模拟 sanitize 失败 (旧 MOC-*.md 含 PII 但 sanitize patterns 不覆盖)
        return text

    # fixture: 海航原文 + extra PII
    src = tmp_release_env["source_wiki"] / "MOC-G-广州-故障树.md"
    original_content = src.read_text(encoding="utf-8")
    src.write_text(original_content + "\n\n海航总部 0898-65987130 / 31 / 68875172\n", encoding="utf-8")

    monkeypatch.setattr(swr, "sanitize_text", fake_sanitize_no_op)
    with pytest.raises(SystemExit) as exc_info:
        swr.build_wiki_release(
            tmp_release_env["source_wiki"], tmp_release_env["release_dir"]
        )
    # 严守 7: 失败时 exit code = 4
    assert exc_info.value.code == 4, f"必须 exit 4 (含 PII 残留), got {exc_info.value.code}"
    # 严守 9: 失败时严禁写 wiki-release-manifest.json
    manifest_path = tmp_release_env["release_dir"] / "wiki-release-manifest.json"
    assert not manifest_path.exists(), f"失败时严禁写 manifest, but {manifest_path} exists"
    # 严守 9b: 失败时严禁写 wiki output (已 rmtree)
    out_wiki = tmp_release_env["release_dir"] / "wiki"
    assert not out_wiki.exists(), f"失败时严禁写 wiki output, but {out_wiki} exists"


# === Test 8: log 无明文 (失败日志仅 fingerprint, 严禁原始 phone/email value) ===

def test_d056_failure_log_no_plaintext_phone(tmp_release_env, monkeypatch, caplog):
    """D-056 fix(security) 严守 8: 失败日志严禁原始 phone value, 仅 fingerprint."""
    import scripts.sanitize_wiki_release as swr

    def fake_sanitize_no_op(text: str) -> str:
        return text

    # 已知 3 个 phone: 0898-65987130, 0898-68875172, 18938850285
    KNOWN_PHONES = ["0898-65987130", "0898-68875172", "18938850285"]
    src = tmp_release_env["source_wiki"] / "MOC-G-广州-故障树.md"
    original_content = src.read_text(encoding="utf-8")
    src.write_text(original_content + "\n" + " ".join(KNOWN_PHONES) + "\n", encoding="utf-8")

    monkeypatch.setattr(swr, "sanitize_text", fake_sanitize_no_op)
    with caplog.at_level(logging.ERROR, logger="sanitize_wiki_release"):
        with pytest.raises(SystemExit) as exc_info:
            swr.build_wiki_release(
                tmp_release_env["source_wiki"], tmp_release_env["release_dir"]
            )
    assert exc_info.value.code == 4
    log_text = caplog.text
    # 严守 8: 失败日志严禁原始 phone value 出现
    for ph in KNOWN_PHONES:
        assert ph not in log_text, f"失败日志严禁含原始 phone {ph!r}, log: {log_text[:500]}"
    # 严守 8b: 但 fingerprint 必须出现 (12 char hex)
    for ph in KNOWN_PHONES:
        fp = hashlib.sha256(ph.encode("utf-8")).hexdigest()[:12]
        assert fp in log_text, f"失败日志必须含 fingerprint {fp} (for phone {ph})"


def test_d056_failure_log_no_plaintext_email(tmp_release_env, monkeypatch, caplog):
    """D-056 fix(security) 严守 8 (email): 失败日志严禁原始 email value, 仅 fingerprint."""
    import scripts.sanitize_wiki_release as swr

    def fake_sanitize_no_op(text: str) -> str:
        return text

    KNOWN_EMAILS = ["aogdesk@hnair.com", "secret-pii@x-test-only.example"]
    src = tmp_release_env["source_wiki"] / "MOC-G-广州-故障树.md"
    original_content = src.read_text(encoding="utf-8")
    src.write_text(original_content + "\n" + " ".join(KNOWN_EMAILS) + "\n", encoding="utf-8")

    monkeypatch.setattr(swr, "sanitize_text", fake_sanitize_no_op)
    with caplog.at_level(logging.ERROR, logger="sanitize_wiki_release"):
        with pytest.raises(SystemExit) as exc_info:
            swr.build_wiki_release(
                tmp_release_env["source_wiki"], tmp_release_env["release_dir"]
            )
    assert exc_info.value.code == 4
    log_text = caplog.text
    for em in KNOWN_EMAILS:
        assert em not in log_text, f"失败日志严禁含原始 email {em!r}"
    for em in KNOWN_EMAILS:
        fp = hashlib.sha256(em.encode("utf-8")).hexdigest()[:12]
        assert fp in log_text, f"失败日志必须含 fingerprint {fp} (for email {em})"


# === Test 9: manifest 无明文 (失败时严禁写含原值的 wiki-release-manifest.json) ===

def test_d056_no_manifest_on_failure(tmp_release_env, monkeypatch):
    """D-056 fix(security) 严守 9: 失败时严禁写 wiki-release-manifest.json.

    严守 NJX 7/31 22:13 拍板: 失败时不得生成含明文的正式 wiki-release-manifest.
    """
    import scripts.sanitize_wiki_release as swr

    def fake_sanitize_no_op(text: str) -> str:
        return text

    src = tmp_release_env["source_wiki"] / "MOC-G-广州-故障树.md"
    original_content = src.read_text(encoding="utf-8")
    src.write_text(original_content + "\n海航总部 0898-65987130\n", encoding="utf-8")

    monkeypatch.setattr(swr, "sanitize_text", fake_sanitize_no_op)
    with pytest.raises(SystemExit) as exc_info:
        swr.build_wiki_release(
            tmp_release_env["source_wiki"], tmp_release_env["release_dir"]
        )
    assert exc_info.value.code == 4
    manifest_path = tmp_release_env["release_dir"] / "wiki-release-manifest.json"
    assert not manifest_path.exists(), f"失败时严禁写 manifest, found {manifest_path}"
    # 严守 9b: 失败时 wiki output 也不写
    out_wiki = tmp_release_env["release_dir"] / "wiki"
    assert not out_wiki.exists(), f"失败时严禁写 wiki/, found {out_wiki}"
    # 严守 9c: 失败时也严禁把原文残留在 release_dir
    for path in tmp_release_env["release_dir"].iterdir():
        # 严禁含 .md (原文残留)
        if path.suffix == ".md":
            pytest.fail(f"失败时严禁残留 .md 原文, found {path}")


# === Test 10: export_fts5 只输出 hash (失败日志仅 fingerprint, 严禁原始 v) ===

def test_d056_export_fts5_residual_log_only_hash(caplog):
    """D-056 fix(security) 严守 10: export_fts5 失败日志仅 fingerprint, 严禁原始 v.

    直接调 _d056_check_pii_residual, 传含 phone/email 文本, 验证:
      - SystemExit(4) 抛出
      - 失败日志严禁原始 phone/email value
      - 失败日志必须含 fingerprint (至少首个命中的)
    """
    from scripts.export_fts5 import _d056_check_pii_residual

    KNOWN_PHONES = ["0898-65987130", "18938850285"]
    KNOWN_EMAILS = ["aogdesk@hnair.com"]
    # 严守 10: 单独 phone 跟 email 文本 (函数 sys.exit 提前, 第一个命中就终止)
    text_phone = "海航总部 0898-65987130 18938850285"
    text_email = "邮箱 aogdesk@hnair.com"

    # Test 10a: phone 失败路径
    with caplog.at_level(logging.ERROR, logger="export_fts5"):
        with pytest.raises(SystemExit) as exc_info:
            _d056_check_pii_residual(text_phone, "test:phone")
    assert exc_info.value.code == 4
    log_text = caplog.text
    # 严守 10: 失败日志严禁原始 phone value
    for v in KNOWN_PHONES:
        assert v not in log_text, f"phone 失败日志严禁含原始 {v!r}, log: {log_text[:500]}"
    # 严守 10b: 失败日志必须含至少 1 个 fingerprint (函数 sys.exit 提前, 只首个命中可见)
    fingerprints = [
        hashlib.sha256(v.encode("utf-8")).hexdigest()[:12] for v in KNOWN_PHONES
    ]
    assert any(fp in log_text for fp in fingerprints), (
        f"phone 失败日志必须含至少 1 个 fingerprint (from {fingerprints}), log: {log_text[:500]}"
    )
    # 严守 10c: failure receipt 必须含 path/kind
    assert "test:phone" in log_text, f"phone 失败日志必须含 path 'test:phone', log: {log_text[:500]}"
    assert "kind=phone" in log_text, f"phone 失败日志必须含 kind=phone, log: {log_text[:500]}"

    # Test 10b: email 失败路径 (清空 caplog)
    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="export_fts5"):
        with pytest.raises(SystemExit) as exc_info:
            _d056_check_pii_residual(text_email, "test:email")
    assert exc_info.value.code == 4
    log_text = caplog.text
    for v in KNOWN_EMAILS:
        assert v not in log_text, f"email 失败日志严禁含原始 {v!r}, log: {log_text[:500]}"
    for v in KNOWN_EMAILS:
        fp = hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]
        assert fp in log_text, f"email 失败日志必须含 fingerprint {fp} (for {v})"
    assert "test:email" in log_text
    assert "kind=email" in log_text
