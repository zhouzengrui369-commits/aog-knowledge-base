"""staging_isolation_test.py — staging 隔离 unit tests (NJX 7/29 严令)

验证 12 个完成门 (STAGING_ISOLATION_PR_GREEN):
  1.  docs/STAGING_ISOLATION_SPEC.md 存在 + 含 _spec_denylist_documentation_only 标记
  2.  scripts/prepare-scf-staging.sh 存在 + 调 denylist_check.py + 读 ops/production-resource-denylist.json
  3.  cloudbaserc.staging.json 是 CloudBase v2 schema + 含 {{env.*}} 占位符 + 0 production 命中
  4.  ops/production-resource-denylist.json 存在 + 含 _isolated_for_staging_denylist_only 标记
  5.  .env.staging.example 全占位符 + 强制 staging 模式 + 不含 aog-staging.njx.com 字面量
  6.  scripts/deploy-staging.sh 存在 + 调 denylist_check.py + ALLOW_STAGING_DEPLOY 闸门
  7.  deploy-staging.sh 不含老命令 tcb env switch + 不含老 flag -e APP_COMMIT_SHA= + 含正确 CloudBase v2 命令
  8.  staging-validation.yml 存在 + 含 5 jobs
  9.  NO_PRODUCTION_RESOURCE_REFERENCE: 4 staging 文件 0 production 命中 (regex word boundary)
 10.  prepare-scf-staging.sh --preflight exit 0
 11.  deploy-staging.sh 无授权时 fail (auth gate)
 12.  denylist_check.py 读 ops/production-resource-denylist.json (不是 cloudbaserc.production.json)

NJX 7/29 严令:
- production 4 项严禁 hardcode (必须从 ops/production-resource-denylist.json 读, DENYLIST_REGEX 策略)
- 第一轮 staging 用 CloudBase 默认域名, 不配 aog-staging.njx.com CNAME
- 严禁 staging 任何代码 hardcode production 4 项 (envId / function / bucket / domain)

运行: pytest tests/staging_isolation_test.py -v
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# regex 版本: word boundary + negative lookahead 排除 staging 后缀
DENYLIST_4_REGEX_PATTERNS = {
    "envId": re.compile(r"njx-copilot-d6gs7642f8fa17122"),
    "bucket": re.compile(r"aog-prod-data-1343051603"),
    "domain": re.compile(r"aog\.njx\.com(?!-staging)"),  # 排除合法 aog-staging.njx.com (但当前 PR 也不用)
    "function": re.compile(r"\baog-api\b(?!-staging)"),  # 排除合法 aog-api-staging
}


def test_1_staging_isolation_spec_exists():
    """1. docs/STAGING_ISOLATION_SPEC.md 存在 + 含 denylist documentation 标记"""
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
    # 必须含 denylist documentation 标记
    assert "_spec_denylist_documentation_only: true" in content, (
        "STAGING_ISOLATION_SPEC.md 必须含 _spec_denylist_documentation_only: true 标记"
    )
    print(f"  ✓ docs/STAGING_ISOLATION_SPEC.md ({p.stat().st_size} bytes, 无动态状态)")


def test_2_prepare_scf_staging_sh_exists_with_denylist():
    """2. scripts/prepare-scf-staging.sh 存在 + 调 denylist_check.py + 读 ops/production-resource-denylist.json"""
    p = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
    assert p.exists(), f"prepare-scf-staging.sh 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 必须含 DENYLIST_REGEX 标识符
    assert "DENYLIST_REGEX" in content, "prepare-scf-staging.sh 必须含 DENYLIST_REGEX 标识符"
    # 必须调 denylist_check.py
    assert "denylist_check.py" in content, (
        "prepare-scf-staging.sh 必须调用 denylist_check.py (独立脚本读 denylist)"
    )
    # 必须引用 ops/production-resource-denylist.json (新 denylist 路径)
    assert "ops/production-resource-denylist.json" in content, (
        "prepare-scf-staging.sh 必须引用 ops/production-resource-denylist.json (新 denylist 路径)"
    )
    # 严禁 hardcode 4 项 production 值
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, (
            f"prepare-scf-staging.sh 严禁 hardcode production {label}, 命中: {m.group(0)!r}"
        )
    # preflight 函数必须存在
    assert "preflight()" in content, "prepare-scf-staging.sh 必须有 preflight 函数"
    print(f"  ✓ scripts/prepare-scf-staging.sh ({p.stat().st_size} bytes, 调 denylist_check.py)")


def test_3_cloudbaserc_staging_is_v2_schema():
    """3. cloudbaserc.staging.json 是 CloudBase v2 schema + 含 {{env.*}} 占位符 + 0 production 命中

    NJX 7/29 严令 v2 schema:
      - version: "2.0"
      - envId: "{{env.TCB_ENV_ID}}"
      - functionRoot: "./aog-web/functions"
      - functions[]: 含 aog-api-staging
      - envVariables[]: 含 {{env.*}} 占位符
    """
    p = REPO_ROOT / "cloudbaserc.staging.json"
    assert p.exists(), f"cloudbaserc.staging.json 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    data = json.loads(content)

    # v2 schema 字段
    assert data.get("version") == "2.0", "cloudbaserc.staging.json 必须 version='2.0' (CloudBase v2 schema)"
    assert data.get("envId") == "{{env.TCB_ENV_ID}}", (
        "cloudbaserc.staging.json envId 必须 '{{env.TCB_ENV_ID}}' 占位符 (NJX 7/29 严令)"
    )
    assert "functionRoot" in data, "cloudbaserc.staging.json 必须含 functionRoot"
    assert isinstance(data.get("functions"), list) and len(data["functions"]) > 0, (
        "cloudbaserc.staging.json 必须含 functions[] 数组"
    )
    # function 必须是 aog-api-staging
    fn_names = [f.get("name") for f in data["functions"]]
    assert "aog-api-staging" in fn_names, (
        f"cloudbaserc.staging.json functions[] 必须含 aog-api-staging, 实际: {fn_names}"
    )
    # envVariables 必须含 {{env.*}} 占位符
    for fn in data["functions"]:
        env_vars = fn.get("envVariables", [])
        assert isinstance(env_vars, list), f"function {fn.get('name')} envVariables 必须是数组"
        # 至少 5 个 env var 用 {{env.*}} 占位符
        placeholder_count = sum(1 for ev in env_vars if isinstance(ev.get("value", ""), str) and ev["value"].startswith("{{env."))
        assert placeholder_count >= 5, (
            f"function {fn.get('name')} envVariables 至少 5 个用 {{env.*}} 占位符, 实际: {placeholder_count}"
        )

    # 严禁 production 4 项 (regex word boundary 排除合法 staging 后缀)
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, (
            f"cloudbaserc.staging.json 严禁含 production {label}: {m.group(0)!r}"
        )
    # NJX 7/29 严令: 第一轮 staging 用 CloudBase 默认域名, 不配 aog-staging.njx.com CNAME
    assert "aog-staging.njx.com" not in content, (
        "cloudbaserc.staging.json 严禁含 'aog-staging.njx.com' 字面量 (CNAME 是远端验收后可选项, 当前 PR 不要求)"
    )
    print(f"  ✓ cloudbaserc.staging.json (v2 schema, 0 production 命中, 0 CNAME 字面量)")


def test_4_ops_production_resource_denylist_exists():
    """4. ops/production-resource-denylist.json 存在 + 含 _isolated_for_staging_denylist_only 标记"""
    p = REPO_ROOT / "ops" / "production-resource-denylist.json"
    assert p.exists(), f"ops/production-resource-denylist.json 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    data = json.loads(content)

    # 必须含 _isolated_for_staging_denylist_only: true
    assert data.get("_isolated_for_staging_denylist_only") is True, (
        "ops/production-resource-denylist.json 缺 _isolated_for_staging_denylist_only: true 标记"
    )
    # 必须含 4 项 denylist (envId / function_name / bucket / domain)
    for key in ["envId", "function_name", "bucket", "domain"]:
        assert key in data, f"ops/production-resource-denylist.json 缺 {key!r}"
        assert isinstance(data[key], str) and len(data[key]) > 0, (
            f"ops/production-resource-denylist.json {key} 必须非空字符串"
        )
    # 严禁 cloudbaserc.production.json 路径 (已重命名)
    cloudbaserc_prod = REPO_ROOT / "cloudbaserc.production.json"
    assert not cloudbaserc_prod.exists(), (
        f"cloudbaserc.production.json 必须删除 (NJX 7/29 严令: 严禁伪装为可部署 rc, 改用 ops/production-resource-denylist.json): {cloudbaserc_prod}"
    )
    print(f"  ✓ ops/production-resource-denylist.json (denylist reference, 含隔离标记)")


def test_5_env_staging_example_placeholders_only():
    """5. .env.staging.example 全占位符 + 强制 staging 模式 + 不含 aog-staging.njx.com 字面量"""
    p = REPO_ROOT / ".env.staging.example"
    assert p.exists(), f".env.staging.example 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 严禁 production 4 项 (regex 排除合法 staging 后缀)
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, (
            f".env.staging.example 严禁含 production {label}: {m.group(0)!r}"
        )
    # NJX 7/29 严令: 第一轮 staging 用 CloudBase 默认域名, 不配 aog-staging.njx.com CNAME
    assert "aog-staging.njx.com" not in content, (
        ".env.staging.example 严禁含 'aog-staging.njx.com' 字面量 (CNAME 是远端验收后可选项)"
    )

    # 必须用占位符
    for key in ["MINIMAX_API_KEY", "COS_SECRET_ID", "COS_SECRET_KEY", "APP_COMMIT_SHA", "COS_BUCKET", "TCB_ENV_ID"]:
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
    print(f"  ✓ .env.staging.example (全占位符, 强制 staging 模式, 0 CNAME 字面量)")


def test_6_deploy_staging_sh_exists_with_denylist():
    """6. scripts/deploy-staging.sh 存在 + 调 denylist_check.py + ALLOW_STAGING_DEPLOY 闸门 + 读 ops/denylist"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    assert p.exists(), f"deploy-staging.sh 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 必须含 DENYLIST_REGEX 标识符
    assert "DENYLIST_REGEX" in content, "deploy-staging.sh 必须含 DENYLIST_REGEX 标识符"
    # 必须调 denylist_check.py
    assert "denylist_check.py" in content, (
        "deploy-staging.sh 必须调用 denylist_check.py"
    )
    # 必须引用 ops/production-resource-denylist.json
    assert "ops/production-resource-denylist.json" in content, (
        "deploy-staging.sh 必须引用 ops/production-resource-denylist.json (新 denylist 路径)"
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
    assert "auth_gate()" in content, "deploy-staging.sh 必须有 auth_gate 函数"
    # 部署目标函数必须是 aog-api-staging
    assert 'STAGING_FUNCTION_NAME="aog-api-staging"' in content, (
        'deploy-staging.sh 必须 STAGING_FUNCTION_NAME="aog-api-staging" (独立 staging function)'
    )
    print(f"  ✓ scripts/deploy-staging.sh ({p.stat().st_size} bytes, 含 denylist + auth_gate)")


def test_7_deploy_staging_sh_uses_cloudbase_v2_commands():
    """7. deploy-staging.sh 用 CloudBase v2 命令 (严禁老命令 tcb env switch + 严禁老 flag -e APP_COMMIT_SHA=)

    只检查非 # 注释行 (因为文档注释可能含 "tcb env switch" 描述作为反面教材, 不算实际命令)
    """
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    content = p.read_text(encoding="utf-8")
    # 只看非注释行 (排除 # 注释里的描述)
    code_lines = "\n".join(
        line for line in content.splitlines() if not line.strip().startswith("#")
    )
    # 严禁老命令 (排除 # 注释)
    assert "tcb env switch" not in code_lines, (
        "deploy-staging.sh 严禁老命令 'tcb env switch' (CloudBase v2 不再使用, # 注释描述除外)"
    )
    # 严禁老 flag
    assert "-e APP_COMMIT_SHA=" not in code_lines, (
        "deploy-staging.sh 严禁老 flag '-e APP_COMMIT_SHA=' (改用 {{env.APP_COMMIT_SHA}} 占位符)"
    )
    # 必须含正确 CloudBase v2 命令
    assert "tcb fn deploy aog-api-staging" in code_lines, (
        "deploy-staging.sh 必须含正确 CloudBase v2 命令 'tcb fn deploy aog-api-staging'"
    )
    assert "--config-file" in code_lines, "deploy-staging.sh 必须含 --config-file flag"
    assert "--mode staging" in code_lines, "deploy-staging.sh 必须含 --mode staging"
    print(f"  ✓ scripts/deploy-staging.sh (用 CloudBase v2 命令, 0 老命令)")


def test_8_staging_validation_yml_exists():
    """8. .github/workflows/staging-validation.yml 存在 + 含 5 jobs + trigger ops/staging-isolation"""
    p = REPO_ROOT / ".github" / "workflows" / "staging-validation.yml"
    assert p.exists(), f"staging-validation.yml 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    # 5 jobs 必须存在
    for job in ["denylist-check:", "staging-prepare:", "staging-deps-isolation:", "staging-validation-tests:", "staging-all-pass:"]:
        assert job in content, f"staging-validation.yml 缺 {job}"
    # trigger 必须含 ops/staging-isolation 分支
    assert "ops/staging-isolation" in content, "staging-validation.yml trigger 缺 ops/staging-isolation 分支"
    print(f"  ✓ .github/workflows/staging-validation.yml ({p.stat().st_size} bytes, 5 jobs)")


def test_9_no_production_resource_reference_in_staging_files():
    """9. NO_PRODUCTION_RESOURCE_REFERENCE: staging 文件 grep production 4 项 → 0 命中

    跨 cloudbaserc.staging.json / .env.staging.example / scripts/prepare-scf-staging.sh / scripts/deploy-staging.sh
    用 regex word boundary 排除合法 staging 后缀 (aog-api-staging)
    """
    staging_files = [
        "cloudbaserc.staging.json",
        ".env.staging.example",
        "aog-web/scripts/prepare-scf-staging.sh",
        "aog-web/scripts/deploy-staging.sh",
    ]
    # 注: ops/production-resource-denylist.json 允许含 production 4 项 (作为 denylist reference)
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


def test_10_prepare_scf_staging_preflight_runs_clean():
    """10. prepare-scf-staging.sh --preflight 应 exit 0 (本地 verify)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
    assert p.exists(), "prepare-scf-staging.sh 不存在"
    r = subprocess.run(
        ["bash", str(p), "--preflight"],
        capture_output=True, text=True, cwd=str(REPO_ROOT / "aog-web"),
    )
    if r.returncode != 0:
        print("  stdout:", r.stdout)
        print("  stderr:", r.stderr)
        pytest.fail(f"prepare-scf-staging.sh --preflight 失败 exit {r.returncode}")
    print(f"  ✓ bash scripts/prepare-scf-staging.sh --preflight exit 0")


def test_11_deploy_staging_requires_explicit_authorization():
    """11. deploy-staging.sh 无 ALLOW_STAGING_DEPLOY=1 时必须 fail (auth gate)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    assert p.exists(), "deploy-staging.sh 不存在"
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
    if "ALLOW_STAGING_DEPLOY" not in r.stderr and "ALLOW_STAGING_DEPLOY" not in r.stdout:
        pytest.fail(
            f"deploy-staging.sh 失败信息应含 ALLOW_STAGING_DEPLOY\n"
            f"stdout: {r.stdout}\nstderr: {r.stderr}"
        )
    print(f"  ✓ deploy-staging.sh 无授权时 fail (auth gate 生效)")


def test_12_denylist_check_uses_ops_production_resource_denylist():
    """12. denylist_check.py 读 ops/production-resource-denylist.json (不是 cloudbaserc.production.json)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "denylist_check.py"
    assert p.exists(), "denylist_check.py 不存在"
    content = p.read_text(encoding="utf-8")
    # 必须读新路径
    assert "ops/production-resource-denylist.json" in content, (
        "denylist_check.py 必须读 ops/production-resource-denylist.json (不是 cloudbaserc.production.json)"
    )
    # 必须不读老路径
    assert "REPO_ROOT / \"cloudbaserc.production.json\"" not in content, (
        "denylist_check.py 严禁读老路径 cloudbaserc.production.json"
    )
    # 跑一下 denylist_check.py 自身, 应 exit 0 (自身 0 production 命中)
    r = subprocess.run(
        ["python3", str(p), str(p)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if r.returncode != 0:
        print("  stdout:", r.stdout)
        print("  stderr:", r.stderr)
        pytest.fail(f"denylist_check.py 自身检查应 exit 0, 实际 exit {r.returncode}")
    print(f"  ✓ denylist_check.py 读 ops/production-resource-denylist.json, 自身检查 0 命中")


# 测试 runner 入口
if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
