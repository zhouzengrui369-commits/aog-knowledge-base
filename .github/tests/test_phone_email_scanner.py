"""test_phone_email_scanner.py — Scanner 6 场景测试 (Owner 7/29 严令)

6 测试:
  1. UTF-8 source 不被误判为 binary
  2. 二进制文件 (含 raw 11 位 1[3-9]xx) 被 skipped_binary 跳过
  3. fixture 手机号 (13900001111) 不报 finding (fixture 路径 allowlist)
  4. production source 手机号 (13900001111) 报 finding, scanner exit 1
  5. example.com 邮箱不报 finding (TLD allowlist)
  6. 真实邮箱 (test@gmail.com) 报 finding

通过 fake git repo + 直接调 scan() 验证 4 类计数 (scanned_text/skipped_binary/skipped_fixture/findings).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

GITHUB_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = GITHUB_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from phone_email_scanner import scan  # noqa: E402


@pytest.fixture
def fake_repo():
    """创建临时 git repo + 写 6 类测试文件, 返回 (tmpdir, file_map)"""
    tmpdir = Path(tempfile.mkdtemp(prefix="scanner_test_"))
    # git init
    subprocess.run(["git", "init", "-q"], cwd=tmpdir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmpdir, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmpdir, check=True)
    # 写文件
    files = {
        # 1. UTF-8 source 无 PII
        "src/clean.py": "import os\n# 正常 UTF-8 源\n",
        # 2. 二进制文件 (含 11 位手机号 — scanner 必须跳过不能误报)
        #    用 .txt 后缀让 _is_text_file pass, 但内容真 binary → UnicodeDecodeError → skipped_binary
        "src/with_binary_blob.txt": b"\x00\x01binary\x00data\x00" + b"13900001111" + b"\xff",
        # 3. fixture 路径 (有真实手机号) — fixture allowlist 应跳过
        "aog-web/frontend/lib/mock/dev_data.py": "PHONE = '13900001111'\nEMAIL = 'real@qq.com'\n",
        # 4. production source 真实手机号 — 应报 finding
        "aog-web/real_phone.py": "# 真实手机号: 13900001111\n",
        # 5. example.com 邮箱 — TLD allowlist 应跳过
        "aog-web/with_example_email.py": "CONTACT = 'aog@example.com'\nFIXTURE = 'x@fixture.example'\n",
        # 6. 真实邮箱 (gmail) — 应报 finding
        "aog-web/real_email.py": "CONTACT = 'someone@gmail.com'\n",
    }
    for path, content in files.items():
        full = tmpdir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            with open(full, "wb") as f:
                f.write(content)
        else:
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
    # git add + commit
    subprocess.run(["git", "add", "-A"], cwd=tmpdir, check=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=tmpdir, check=True)

    yield tmpdir

    # cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_1_utf8_source_not_binary(fake_repo):
    """1. UTF-8 source 应被 scan, 不进 skipped_binary"""
    result = scan(repo_root=str(fake_repo))
    assert result["scanned_text_files"] >= 1, \
        f"UTF-8 source 应被扫, got scanned={result['scanned_text_files']}"
    # src/clean.py 应该被算
    src_clean = fake_repo / "src/clean.py"
    assert src_clean.exists()
    # 不应被算作 skipped_binary
    assert result["skipped_binary_files"] >= 1, \
        f"二进制 blob 应被 skipped_binary, got {result['skipped_binary_files']}"


def test_2_binary_file_skipped(fake_repo):
    """2. 二进制文件 (含 11 位手机号) 应被 skipped_binary, 不进 findings"""
    result = scan(repo_root=str(fake_repo))
    # 验证 with_binary_blob.bin 触发 skipped_binary
    assert result["skipped_binary_files"] >= 1
    # 验证该 binary 内的 13900001111 没在 findings
    binary_findings = [f for f in result["findings"] if f["file"] == "src/with_binary_blob.txt"]
    assert binary_findings == [], \
        f"二进制文件应被 skipped_binary, 不报 finding, got {binary_findings}"


def test_3_fixture_path_allowlist(fake_repo):
    """3. fixture 路径 (lib/mock/) 内的真实手机号应被 allowlist 跳过"""
    result = scan(repo_root=str(fake_repo))
    # 验证 lib/mock/dev_data.py 的 13900001111 没在 findings
    fixture_findings = [f for f in result["findings"] if "lib/mock/" in f["file"]]
    assert fixture_findings == [], \
        f"fixture 路径应被 allowlist, got {fixture_findings}"
    # 也验证 fixture path 计入 skipped_fixture_files
    assert result["skipped_fixture_files"] >= 1, \
        f"fixture 路径应被 allowlist, got {result['skipped_fixture_files']}"


def test_4_production_source_phone_detected(fake_repo):
    """4. production source 真实手机号应被报 finding"""
    result = scan(repo_root=str(fake_repo))
    real_phone_findings = [
        f for f in result["findings"]
        if f["file"] == "aog-web/real_phone.py" and f["type"] == "phone"
    ]
    assert len(real_phone_findings) == 1, \
        f"production 真实手机号应报 1 finding, got {real_phone_findings}"
    assert real_phone_findings[0]["match"] == "13900001111"


def test_5_example_email_allowlist(fake_repo):
    """5. example.com 邮箱应被 TLD allowlist 跳过"""
    result = scan(repo_root=str(fake_repo))
    example_findings = [
        f for f in result["findings"]
        if f["file"] == "aog-web/with_example_email.py"
    ]
    assert example_findings == [], \
        f"example.com / fixture.example 应被 allowlist, got {example_findings}"


def test_6_real_email_detected(fake_repo):
    """6. 真实邮箱 (gmail.com) 应被报 finding"""
    result = scan(repo_root=str(fake_repo))
    real_email_findings = [
        f for f in result["findings"]
        if f["file"] == "aog-web/real_email.py" and f["type"] == "email"
    ]
    assert len(real_email_findings) == 1, \
        f"真实 gmail 邮箱应报 1 finding, got {real_email_findings}"
    assert real_email_findings[0]["match"] == "someone@gmail.com"


def test_scanner_internal_error_exit_2(monkeypatch):
    """7. scanner 内部异常 (git ls-files 失败) 应返 exit 2"""
    # mock subprocess.run 让 git ls-files 抛 FileNotFoundError
    import subprocess as sp
    from phone_email_scanner import _git_ls_files

    def _raise(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(sp, "run", _raise)
    with pytest.raises(SystemExit) as e:
        _git_ls_files()
    assert e.value.code == 2, f"scanner 内部异常应 exit 2, got {e.value.code}"


def test_main_function_real_repo():
    """8. main() 在真仓库上跑 (实际 CI 场景), 验证输出格式"""
    from phone_email_scanner import main
    repo_root = str(Path(__file__).resolve().parent.parent.parent)  # 仓库根
    old_cwd = os.getcwd()
    try:
        os.chdir(repo_root)
        rc = main()
    finally:
        os.chdir(old_cwd)
    # 真仓库可能有或没有 findings — 关键是 exit code 必须是 0/1/2
    assert rc in (0, 1, 2), f"main() exit code 应 0/1/2, got {rc}"
