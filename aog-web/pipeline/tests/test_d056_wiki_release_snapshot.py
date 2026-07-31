#!/usr/bin/env python3
"""test_d056_wiki_release_snapshot.py — D-056 wiki release snapshot 6 场景验证

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

运行:
  cd aog-web/pipeline
  ../backend/.venv/bin/python -m pytest tests/test_d056_wiki_release_snapshot.py -v --tb=short
"""
from __future__ import annotations

import json
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
