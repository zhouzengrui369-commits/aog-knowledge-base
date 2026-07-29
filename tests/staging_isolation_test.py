"""staging_isolation_test.py — staging 隔离 unit tests (NJX 7/29 严令)

验证 8 个完成门:
  1. docs/STAGING_ISOLATION_SPEC.md 存在
  2. scripts/prepare-scf-staging.sh 存在 + 调用 denylist_check.py + 引用 cloudbaserc.production.json
     (NJX 7/29 严令: production value 严禁在脚本里 hardcode, 必须从 rc 读)
  3. cloudbaserc.staging.json 存在 + 不含 production 4 项
  4. cloudbaserc.production.json 存在 + 仅作 denylist reference
  5. .env.staging.example 存在 + 占位符无真凭据
  6. scripts/deploy-staging.sh 存在 + 调用 denylist_check.py + ALLOW_STAGING_DEPLOY 闸门
  7. staging-validation.yml 存在 + 含 denylist-check job
  8. NO_PRODUCTION_RESOURCE_REFERENCE: 全部 staging 脚本 grep production 4 项 → 0 命中

运行: pytest tests/staging_isolation_test.py -v
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# 4 项 denylist: NJX 7/29 严令, 这些值严禁在 staging 任何脚本里 hardcode
# 用 regex word boundary 排除合法 staging 后缀 (aog-api-staging / aog-staging.njx.com)
DENYLIST_4 = [
    "njx-copilot-d6gs7642f8fa17122",
    "aog-prod-data-1343051603",
    "aog.njx.com",
    "aog-api",  # production function name
]

# regex 版本: word boundary + negative lookahead 排除 staging 后缀
DENYLIST_4_REGEX_PATTERNS = {
    "envId": re.compile(r"njx-copilot-d6gs7642f8fa17122"),
    "bucket": re.compile(r"aog-prod-data-1343051603"),
    "domain": re.compile(r"aog\.njx\.com(?!-staging)"),  # 排除 aog-staging.njx.com
    "function": re.compile(r"\baog-api\b(?!-staging)"),  # 排除 aog-api-staging
}


def test_1_staging_isolation_spec_exists():
    """1. docs/STAGING_ISOLATION_SPEC.md 存在"""
    p = REPO_ROOT / "docs" / "STAGING_ISOLATION_SPEC.md"
    assert p.exists(), f"staging isolation spec 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    # 严禁 current head / 临时 CI run ID / 动态完成状态 (NJX 严令)
    forbidden_patterns = [
        r"current_pr_head=",
        r"commits_ahead=\d+",
        r"observed_pr_head=[a-f0-9]{40}",
        r"run \d{10,}",  # 临时 CI run ID
    ]
    for pat in forbidden_patterns:
        m = re.search(pat, content)
        assert not m, (
            f"staging isolation spec 禁止动态状态字段, 命中: {pat} → {m.group(0)!r}"
        )
    # 必须含 denylist documentation 标记 (允许 spec 描述 4 项)
    assert "_spec_denylist_documentation_only: true" in content, (
        "STAGING_ISOLATION_SPEC.md 必须含 _spec_denylist_documentation_only: true 标记"
    )
    print(f"  ✓ docs/STAGING_ISOLATION_SPEC.md ({p.stat().st_size} bytes, 无动态状态)")


def test_2_prepare_scf_staging_sh_exists_with_denylist():
    """2. scripts/prepare-scf-staging.sh 存在 + 调 denylist_check.py + 引用 cloudbaserc.production.json

    NJX 7/29 严令: production 4 项严禁在脚本里 hardcode, 必须从 rc 读
    """
    p = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
    assert p.exists(), f"prepare-scf-staging.sh 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 必须含 DENYLIST_REGEX 标识符 (跟 denylist_check.py 对齐)
    assert "DENYLIST_REGEX" in content, "prepare-scf-staging.sh 必须含 DENYLIST_REGEX 标识符"

    # 必须调 denylist_check.py (从 production rc 读 denylist, 严禁 hardcode)
    assert "denylist_check.py" in content, (
        "prepare-scf-staging.sh 必须调用 denylist_check.py (独立脚本读 production denylist, 严禁 hardcode)"
    )

    # 必须引用 cloudbaserc.production.json (denylist source)
    assert "cloudbaserc.production.json" in content, (
        "prepare-scf-staging.sh 必须引用 cloudbaserc.production.json 作为 denylist source"
    )

    # 严禁 hardcode 4 项 production 值 (NJX 7/29 严令, 避免脚本自杀)
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, (
            f"prepare-scf-staging.sh 严禁 hardcode production {label}, 命中: {m.group(0)!r}"
        )

    # preflight 函数必须存在
    assert "preflight()" in content, "prepare-scf-staging.sh 必须有 preflight 函数"
    print(f"  ✓ scripts/prepare-scf-staging.sh ({p.stat().st_size} bytes, 调 denylist_check.py)")


def test_3_cloudbaserc_staging_no_production():
    """3. cloudbaserc.staging.json 存在 + 不含 production 4 项 (regex word boundary)"""
    p = REPO_ROOT / "cloudbaserc.staging.json"
    assert p.exists(), f"cloudbaserc.staging.json 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 严禁 production 4 项 (用 regex 排除 aog-api-staging / aog-staging.njx.com)
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, (
            f"cloudbaserc.staging.json 严禁含 production {label}: {m.group(0)!r}"
        )

    # 必须含 staging 标识
    assert "staging" in content.lower(), "cloudbaserc.staging.json 必须含 staging"
    assert "aog-api-staging" in content, "function 必须是 aog-api-staging"
    assert "aog-staging.njx.com" in content, "domain 必须是 aog-staging.njx.com"
    print(f"  ✓ cloudbaserc.staging.json (独立 envId, 0 production 命中)")


def test_4_cloudbaserc_production_is_denylist_only():
    """4. cloudbaserc.production.json 存在 + 仅作 denylist reference"""
    p = REPO_ROOT / "cloudbaserc.production.json"
    assert p.exists(), f"cloudbaserc.production.json 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    # 必须含 _isolated_for_staging_denylist_only: true
    assert '"_isolated_for_staging_denylist_only": true' in content, (
        "cloudbaserc.production.json 缺 _isolated_for_staging_denylist_only: true"
    )
    # 必须含 4 项 denylist (作为 reference)
    for item in DENYLIST_4:
        assert item in content, f"cloudbaserc.production.json 缺 denylist {item!r}"
    print(f"  ✓ cloudbaserc.production.json (denylist reference, 含隔离标记)")


def test_5_env_staging_example_placeholders_only():
    """5. .env.staging.example 存在 + 占位符无真凭据 (regex 排除 staging 子串)"""
    p = REPO_ROOT / ".env.staging.example"
    assert p.exists(), f".env.staging.example 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 严禁 production 4 项 (regex 排除 aog-staging.njx.com 子串)
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, (
            f".env.staging.example 严禁含 production {label}: {m.group(0)!r}"
        )

    # 必须用占位符
    for key in ["MINIMAX_API_KEY", "COS_SECRET_ID", "COS_SECRET_KEY", "APP_COMMIT_SHA", "COS_BUCKET"]:
        m = re.search(rf"^{key}=(\S+)", content, re.MULTILINE)
        assert m, f".env.staging.example 缺 {key}="
        val = m.group(1)
        assert "xxx-" in val or "STAGING" in val.upper(), (
            f".env.staging.example {key}={val!r} 非占位符 (严禁真凭据)"
        )
    # 必须含强制 staging 模式
    assert re.search(r"^ENVIRONMENT=staging", content, re.MULTILINE), ".env.staging.example 必须 ENVIRONMENT=staging"
    assert re.search(r"^ALLOW_MOCK=false", content, re.MULTILINE), ".env.staging.example 必须 ALLOW_MOCK=false"
    assert re.search(r"^STRICT_LLM=true", content, re.MULTILINE), ".env.staging.example 必须 STRICT_LLM=true"
    assert re.search(r"^SYNC_ENABLED=false", content, re.MULTILINE), ".env.staging.example 必须 SYNC_ENABLED=false"
    print(f"  ✓ .env.staging.example (全占位符, 强制 staging 模式)")


def test_6_deploy_staging_sh_exists_with_denylist():
    """6. scripts/deploy-staging.sh 存在 + 调 denylist_check.py + ALLOW_STAGING_DEPLOY 闸门

    NJX 7/29 严令: production 4 项严禁 hardcode, 必须从 cloudbaserc.production.json 读
    """
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    assert p.exists(), f"deploy-staging.sh 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 必须含 DENYLIST_REGEX 标识符
    assert "DENYLIST_REGEX" in content, "deploy-staging.sh 必须含 DENYLIST_REGEX 标识符"

    # 必须调 denylist_check.py
    assert "denylist_check.py" in content, (
        "deploy-staging.sh 必须调用 denylist_check.py (独立脚本读 denylist)"
    )

    # 必须引用 cloudbaserc.production.json
    assert "cloudbaserc.production.json" in content, (
        "deploy-staging.sh 必须引用 cloudbaserc.production.json 作为 denylist source"
    )

    # 严禁 hardcode 4 项 production 值
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, (
            f"deploy-staging.sh 严禁 hardcode production {label}, 命中: {m.group(0)!r}"
        )

    # 必须含 ALLOW_STAGING_DEPLOY 闸门
    assert "ALLOW_STAGING_DEPLOY" in content, "deploy-staging.sh 必须含 ALLOW_STAGING_DEPLOY 闸门"
    # 必须有 preflight + auth_gate 函数
    assert "preflight()" in content, "deploy-staging.sh 必须有 preflight 函数"
    assert "auth_gate()" in content, "deploy-staging.sh 必须有 auth_gate 函数 (ALLOW_STAGING_DEPLOY 校验)"
    # 部署目标函数必须是 aog-api-staging
    assert 'STAGING_FUNCTION_NAME="aog-api-staging"' in content, (
        'deploy-staging.sh 必须 STAGING_FUNCTION_NAME="aog-api-staging" (独立 staging function)'
    )
    print(f"  ✓ scripts/deploy-staging.sh ({p.stat().st_size} bytes, 含 denylist + auth_gate)")


def test_7_staging_validation_yml_exists():
    """7. .github/workflows/staging-validation.yml 存在 + 含 denylist-check job"""
    p = REPO_ROOT / ".github" / "workflows" / "staging-validation.yml"
    assert p.exists(), f"staging-validation.yml 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    # 必须有 denylist-check job
    assert "denylist-check:" in content, "staging-validation.yml 缺 denylist-check job"
    assert "staging-prepare:" in content, "staging-validation.yml 缺 staging-prepare job"
    assert "staging-deps-isolation:" in content, "staging-validation.yml 缺 staging-deps-isolation job"
    assert "staging-validation-tests:" in content, "staging-validation.yml 缺 staging-validation-tests job"
    assert "staging-all-pass:" in content, "staging-validation.yml 缺 staging-all-pass aggregate"
    # trigger 必须含 ops/staging-isolation 分支
    assert "ops/staging-isolation" in content, "staging-validation.yml trigger 缺 ops/staging-isolation 分支"
    print(f"  ✓ .github/workflows/staging-validation.yml ({p.stat().st_size} bytes, 5 jobs)")


def test_8_no_production_resource_reference_in_staging_files():
    """8. NO_PRODUCTION_RESOURCE_REFERENCE: 全部 staging 脚本 grep production 4 项 → 0 命中

    跨 cloudbaserc.staging.json / .env.staging.example / scripts/prepare-scf-staging.sh / scripts/deploy-staging.sh
    用 regex word boundary 排除合法 staging 后缀 (aog-api-staging / aog-staging.njx.com)
    """
    staging_files = [
        "cloudbaserc.staging.json",
        ".env.staging.example",
        "aog-web/scripts/prepare-scf-staging.sh",
        "aog-web/scripts/deploy-staging.sh",
    ]
    # 注: cloudbaserc.production.json 允许含 production 4 项 (作为 denylist reference)
    #     docs/STAGING_ISOLATION_SPEC.md 允许含 4 项 (说明 denylist 是什么, 必须含 _spec_denylist_documentation_only 标记)
    error = []
    for f in staging_files:
        p = REPO_ROOT / f
        if not p.exists():
            error.append(f"{f}: 不存在")
            continue
        content = p.read_text(encoding="utf-8")
        for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
            m = regex.search(content)
            if m:
                error.append(f"{f}: 含 production {label} ({m.group(0)!r})")

    if error:
        for e in error:
            print(f"  ✗ {e}")
        pytest.fail(f"staging 文件含 production 引用: {error}")
    print(f"  ✓ NO_PRODUCTION_RESOURCE_REFERENCE: 4 staging 文件 0 production 命中")


def test_9_prepare_scf_staging_preflight_runs_clean():
    """9. prepare-scf-staging.sh --preflight 应 exit 0 (本地 verify)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
    assert p.exists(), "prepare-scf-staging.sh 不存在"
    # 跑 --preflight
    r = subprocess.run(
        ["bash", str(p), "--preflight"],
        capture_output=True, text=True, cwd=str(REPO_ROOT / "aog-web"),
    )
    if r.returncode != 0:
        print("  stdout:", r.stdout)
        print("  stderr:", r.stderr)
        pytest.fail(f"prepare-scf-staging.sh --preflight 失败 exit {r.returncode}")
    print(f"  ✓ bash scripts/prepare-scf-staging.sh --preflight exit 0")


def test_10_deploy_staging_requires_explicit_authorization():
    """10. deploy-staging.sh 无 ALLOW_STAGING_DEPLOY=1 时必须 fail (auth gate)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    assert p.exists(), "deploy-staging.sh 不存在"
    # 跑 deploy-staging.sh 不带 ALLOW_STAGING_DEPLOY → 应 fail
    r = subprocess.run(
        ["bash", str(p)],
        capture_output=True, text=True, cwd=str(REPO_ROOT / "aog-web"),
        env={**os.environ, "ALLOW_STAGING_DEPLOY": ""},  # 显式 unset
    )
    if r.returncode == 0:
        pytest.fail(
            f"deploy-staging.sh 不带 ALLOW_STAGING_DEPLOY=1 应 fail, 但 exit 0\n"
            f"stdout: {r.stdout}\nstderr: {r.stderr}"
        )
    # 应含 auth_gate 错误信息 (同时 preflight fail 时也提示 ALLOW_STAGING_DEPLOY)
    if "ALLOW_STAGING_DEPLOY" not in r.stderr and "ALLOW_STAGING_DEPLOY" not in r.stdout:
        pytest.fail(
            f"deploy-staging.sh 失败信息应含 ALLOW_STAGING_DEPLOY\n"
            f"stdout: {r.stdout}\nstderr: {r.stderr}"
        )
    print(f"  ✓ deploy-staging.sh 无授权时 fail (auth gate 生效)")


# 测试 runner 入口
if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
