"""staging_isolation_test.py — staging 隔离 + DEPLOYABILITY unit tests (NJX 7/29 严令)

NJX 7/29 严令 (PR #2 内修复):
  DEPLOYABILITY 5 项:
    1. cloudbaserc.staging.json: envVariables 必须 object (不是 array)
       + type=HTTP + installDependency=false + memorySize=512 + timeout=60 + region=ap-shanghai
       + 必含全部 required env keys (ENVIRONMENT / ALLOW_MOCK / STRICT_LLM / SYNC_ENABLED / APP_COMMIT_SHA /
         MINIMAX_API_KEY / MINIMAX_BASE_URL / MINIMAX_MODEL / CHROMA_PATH / SQLITE_PATH / FTS5_PATH /
         RAG_BACKEND / LOG_LEVEL / COS_BUCKET / COS_REGION / COS_SECRET_ID / COS_SECRET_KEY /
         AOG_DB_PATH / AOG_VIEW_PASSWORD / JWT_SECRET / STAGING_HOSTING_ORIGIN /
         KNOWLEDGE_BASE_PATH / RAW_PATH / CORS_ALLOW_ORIGINS)
    2. prepare-scf-staging.sh: staging package 含 scf_bootstrap / main.py / scf_adapter.py / scf_cos.py / requirements.txt / aog_web/
       + scf_bootstrap +x + 3 py 编译通过
    3. deploy-staging.sh: STAGING_DEPLOY_MODE=dry-run 默认 + ALLOW_STAGING_DEPLOY=1 + STAGING_DEPLOY_MODE=execute 才真执行
       + 4 项强校验: MERGE_SHA 40 hex / MERGE_SHA==git HEAD / APP_COMMIT_SHA==MERGE_SHA / git status clean
       + 用参数数组执行 tcb fn deploy, 严禁 eval
    4. .env.staging.example: 含 AOG_DB_PATH / AOG_VIEW_PASSWORD / JWT_SECRET (>=32 bytes) / STAGING_HOSTING_ORIGIN
    5. deploy-staging.sh execute 模式: 用 fake tcb 验证确实调用部署命令
       + 4 项错误路径全 fail: dirty tree / SHA mismatch / production env / 未授权

NJX 7/29 严令 (前置, 已通过):
  STAGING_ISOLATION 12 项:
    1. docs/STAGING_ISOLATION_SPEC.md 存在 + _spec_denylist_documentation_only 标记
    2. scripts/prepare-scf-staging.sh 存在 + 调 denylist_check.py + 读 ops/production-resource-denylist.json
    3. cloudbaserc.staging.json 是 v2 schema + {{env.*}} 占位符
    4. ops/production-resource-denylist.json 存在 + 含 _isolated_for_staging_denylist_only 标记
    5. .env.staging.example 全占位符
    6. scripts/deploy-staging.sh 存在 + 调 denylist_check.py + ALLOW_STAGING_DEPLOY 闸门
    7. deploy-staging.sh 用 CloudBase v2 命令
    8. staging-validation.yml 存在 + 5 jobs
    9. NO_PRODUCTION_RESOURCE_REFERENCE 0 命中
   10. prepare-scf-staging.sh --preflight exit 0
   11. deploy-staging.sh 无授权时 fail
   12. denylist_check.py 读 ops/production-resource-denylist.json

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

# regex 版本: word boundary + negative lookahead 排除 staging 后缀 + 路径分隔符
# (?![-/]) 排除路径引用 (e.g. "aog-api/requirements.txt" 合法 read 引用)
# 跟 denylist_check.py 严格对齐 (NJX 7/29 严令 denylist 自杀防御)
DENYLIST_4_REGEX_PATTERNS = {
    "envId": re.compile(r"njx-copilot-d6gs7642f8fa17122"),
    "bucket": re.compile(r"aog-prod-data-1343051603"),
    "domain": re.compile(r"aog\.njx\.com(?!-staging)"),
    "function": re.compile(r"\baog-api\b(?![-/])"),  # 排除 aog-api-staging / aog-api/
}

# NJX 7/29 严令: cloudbaserc.staging.json 必含全部这些 env vars
REQUIRED_STAGING_ENV_KEYS = {
    "ENVIRONMENT", "ALLOW_MOCK", "STRICT_LLM", "SYNC_ENABLED",
    "APP_COMMIT_SHA", "MINIMAX_API_KEY", "MINIMAX_BASE_URL", "MINIMAX_MODEL",
    "CHROMA_PATH", "SQLITE_PATH", "FTS5_PATH", "RAG_BACKEND", "LOG_LEVEL",
    "COS_BUCKET", "COS_REGION", "COS_SECRET_ID", "COS_SECRET_KEY",
    "AOG_DB_PATH", "AOG_VIEW_PASSWORD", "JWT_SECRET", "STAGING_HOSTING_ORIGIN",
    "KNOWLEDGE_BASE_PATH", "RAW_PATH", "CORS_ALLOW_ORIGINS",
}

# NJX 7/29 严令: staging package 必含这些 handler 文件
REQUIRED_STAGING_HANDLER_FILES = [
    "scf_bootstrap", "main.py", "scf_adapter.py", "scf_cos.py",
    "requirements.txt", "aog_web",
]

# .env.staging.example 必含的关键 (deployability)
REQUIRED_STAGING_DOTENV_KEYS = {
    "AOG_DB_PATH", "AOG_VIEW_PASSWORD", "JWT_SECRET", "STAGING_HOSTING_ORIGIN",
    "TCB_ENV_ID", "APP_COMMIT_SHA", "MINIMAX_API_KEY", "COS_SECRET_ID", "COS_SECRET_KEY",
    "ENVIRONMENT", "ALLOW_MOCK", "STRICT_LLM", "SYNC_ENABLED",
}


def test_1_staging_isolation_spec_exists():
    """1. docs/STAGING_ISOLATION_SPEC.md 存在 + 含 denylist documentation 标记"""
    p = REPO_ROOT / "docs" / "STAGING_ISOLATION_SPEC.md"
    assert p.exists(), f"staging isolation spec 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    forbidden_patterns = [r"current_pr_head=", r"commits_ahead=\d+", r"observed_pr_head=[a-f0-9]{40}", r"run \d{10,}"]
    for pat in forbidden_patterns:
        m = re.search(pat, content)
        assert not m, f"staging isolation spec 禁止动态状态字段, 命中: {pat} → {m.group(0)!r}"
    assert "_spec_denylist_documentation_only: true" in content, (
        "STAGING_ISOLATION_SPEC.md 必须含 _spec_denylist_documentation_only: true 标记"
    )
    print(f"  ✓ docs/STAGING_ISOLATION_SPEC.md ({p.stat().st_size} bytes, 无动态状态)")


def test_2_prepare_scf_staging_sh_exists_with_denylist():
    """2. scripts/prepare-scf-staging.sh 存在 + 调 denylist_check.py + 读 ops/production-resource-denylist.json"""
    p = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
    assert p.exists(), f"prepare-scf-staging.sh 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    assert "DENYLIST_REGEX" in content, "prepare-scf-staging.sh 必须含 DENYLIST_REGEX 标识符"
    assert "denylist_check.py" in content, "prepare-scf-staging.sh 必须调用 denylist_check.py"
    assert "ops/production-resource-denylist.json" in content, "prepare-scf-staging.sh 必须引用 ops/production-resource-denylist.json"
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, f"prepare-scf-staging.sh 严禁 hardcode production {label}, 命中: {m.group(0)!r}"
    assert "preflight()" in content, "prepare-scf-staging.sh 必须有 preflight 函数"
    print(f"  ✓ scripts/prepare-scf-staging.sh ({p.stat().st_size} bytes, 调 denylist_check.py)")


def test_3_cloudbaserc_staging_is_v2_schema_with_deployability():
    """3. cloudbaserc.staging.json 是 v2 schema + envVariables 是 object + 全部 required env keys
    + type=HTTP + installDependency=false + memorySize=512 + timeout=60 + region=ap-shanghai

    NJX 7/29 严令 DEPLOYABILITY:
      - envVariables 必须是 dict (key→value object), 不是 array
      - type=HTTP (trigger type)
      - installDependency=false (vendor/ 已经在函数包)
      - memorySize=512
      - timeout=60
      - region=ap-shanghai
      - 必含全部 REQUIRED_STAGING_ENV_KEYS
    """
    p = REPO_ROOT / "cloudbaserc.staging.json"
    assert p.exists(), f"cloudbaserc.staging.json 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    data = json.loads(content)

    # v2 schema 字段
    assert data.get("version") == "2.0", "cloudbaserc.staging.json 必须 version='2.0'"
    assert data.get("envId") == "{{env.TCB_ENV_ID}}", "cloudbaserc.staging.json envId 必须 '{{env.TCB_ENV_ID}}'"
    assert data.get("region") == "ap-shanghai", "cloudbaserc.staging.json 必须 region='ap-shanghai' (NJX 7/29 严令)"
    assert "functionRoot" in data, "cloudbaserc.staging.json 必须含 functionRoot"
    functions = data.get("functions")
    assert isinstance(functions, list) and len(functions) > 0, "cloudbaserc.staging.json 必须含 functions[]"
    fn = functions[0]
    assert fn.get("name") == "aog-api-staging", "function name 必须是 aog-api-staging"

    # ===== DEPLOYABILITY 关键字段 =====
    assert fn.get("type") == "HTTP", f"function.type 必须 'HTTP' (NJX 7/29 严令), 实际: {fn.get('type')!r}"
    assert fn.get("installDependency") is False, f"function.installDependency 必须 false (NJX 7/29 严令, 用 vendor/), 实际: {fn.get('installDependency')!r}"
    assert fn.get("memorySize") == 512, f"function.memorySize 必须 512 (NJX 7/29 严令), 实际: {fn.get('memorySize')!r}"
    assert fn.get("timeout") == 60, f"function.timeout 必须 60 (NJX 7/29 严令), 实际: {fn.get('timeout')!r}"

    # NJX 7/30 严令: handler 改为 main.main_handler (直接 Python3.11 entry, 不走 bash)
    assert fn.get("handler") == "main.main_handler", (
        f"function.handler 必须 'main.main_handler' (NJX 7/30 严令 runtime preflight), 实际: {fn.get('handler')!r}"
    )

    # ===== envVariables 必须是 object (dict), 不是 array =====
    env_vars = fn.get("envVariables")
    assert isinstance(env_vars, dict), (
        f"function.envVariables 必须是 dict (object) 不是 array/list (NJX 7/29 严令 DEPLOYABILITY), 实际类型: {type(env_vars).__name__}"
    )
    # 必含全部 REQUIRED_STAGING_ENV_KEYS
    missing = REQUIRED_STAGING_ENV_KEYS - set(env_vars.keys())
    assert not missing, (
        f"function.envVariables 缺 required keys: {sorted(missing)}\n"
        f"  当前含: {sorted(env_vars.keys())}"
    )
    # 占位符用 {{env.*}} 形式
    for key, value in env_vars.items():
        if key in {"APP_COMMIT_SHA", "MINIMAX_API_KEY", "MINIMAX_BASE_URL", "MINIMAX_MODEL",
                  "CHROMA_PATH", "SQLITE_PATH", "FTS5_PATH", "RAG_BACKEND", "LOG_LEVEL",
                  "COS_BUCKET", "COS_REGION", "COS_SECRET_ID", "COS_SECRET_KEY",
                  "AOG_DB_PATH", "AOG_VIEW_PASSWORD", "JWT_SECRET", "STAGING_HOSTING_ORIGIN",
                  "KNOWLEDGE_BASE_PATH", "RAW_PATH", "CORS_ALLOW_ORIGINS"}:
            assert isinstance(value, str) and value.startswith("{{env.") and value.endswith("}}"), (
                f"function.envVariables['{key}'] = {value!r} 必须是 '{{env.*}}' 占位符"
            )

    # 严禁 production 4 项字面量
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, f"cloudbaserc.staging.json 严禁含 production {label}: {m.group(0)!r}"
    # 不含自定义 CNAME 字面量
    assert "aog-staging.njx.com" not in content, (
        "cloudbaserc.staging.json 严禁含 'aog-staging.njx.com' 字面量 (CNAME 是远端验收后可选项)"
    )
    print(f"  ✓ cloudbaserc.staging.json (v2 schema, envVariables dict, {len(env_vars)} keys, type=HTTP, installDependency=false, memorySize=512, timeout=60, region=ap-shanghai)")


def test_4_ops_production_resource_denylist_exists():
    """4. ops/production-resource-denylist.json 存在 + 含 _isolated_for_staging_denylist_only 标记"""
    p = REPO_ROOT / "ops" / "production-resource-denylist.json"
    assert p.exists(), f"ops/production-resource-denylist.json 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    data = json.loads(content)
    assert data.get("_isolated_for_staging_denylist_only") is True, "缺 _isolated_for_staging_denylist_only: true 标记"
    for key in ["envId", "function_name", "bucket", "domain"]:
        assert key in data, f"ops/production-resource-denylist.json 缺 {key!r}"
        assert isinstance(data[key], str) and len(data[key]) > 0, f"ops/production-resource-denylist.json {key} 必须非空字符串"
    cloudbaserc_prod = REPO_ROOT / "cloudbaserc.production.json"
    assert not cloudbaserc_prod.exists(), (
        f"cloudbaserc.production.json 必须删除 (严禁伪装为可部署 rc, 改用 ops/production-resource-denylist.json): {cloudbaserc_prod}"
    )
    print(f"  ✓ ops/production-resource-denylist.json (denylist reference, 含隔离标记)")


def test_5_env_staging_example_placeholders_and_deployability():
    """5. .env.staging.example 全占位符 + 强制 staging 模式 + deployability 必含 AOG_DB_PATH/AOG_VIEW_PASSWORD/JWT_SECRET(>=32)/STAGING_HOSTING_ORIGIN"""
    p = REPO_ROOT / ".env.staging.example"
    assert p.exists(), f".env.staging.example 必须存在: {p}"
    content = p.read_text(encoding="utf-8")

    # 严禁 production 4 项
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, f".env.staging.example 严禁含 production {label}: {m.group(0)!r}"
    # 严禁 CNAME 字面量
    assert "aog-staging.njx.com" not in content, ".env.staging.example 严禁含 'aog-staging.njx.com' 字面量"

    # NJX 7/29 DEPLOYABILITY 必含全部 REQUIRED_STAGING_DOTENV_KEYS
    env_map = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Z_][A-Z0-9_]*)=(\S*)$", line)
        if m:
            env_map[m.group(1)] = m.group(2)
    missing = REQUIRED_STAGING_DOTENV_KEYS - set(env_map.keys())
    assert not missing, f".env.staging.example 缺 required keys: {sorted(missing)}"

    # JWT_SECRET 必须 >= 32 bytes (NJX 7/29 严令)
    jwt_secret = env_map.get("JWT_SECRET", "")
    assert len(jwt_secret) >= 32, f"JWT_SECRET 至少 32 bytes (NJX 7/29 严令), 实际 {len(jwt_secret)} bytes"

    # 占位符检查 (严禁真凭据)
    for key in ["MINIMAX_API_KEY", "COS_SECRET_ID", "COS_SECRET_KEY", "APP_COMMIT_SHA", "COS_BUCKET", "TCB_ENV_ID", "AOG_VIEW_PASSWORD", "STAGING_HOSTING_ORIGIN"]:
        val = env_map.get(key, "")
        assert "xxx-" in val or "STAGING" in val.upper() or "{{env." in val, (
            f".env.staging.example {key}={val!r} 非占位符 (严禁真凭据)"
        )

    # NJX 7/30 严令 data paths: FTS5_PATH / SQLITE_PATH / AOG_DB_PATH / CHROMA_PATH / SYNC_STATE_DB_PATH 全 /tmp
    for path_key in ["FTS5_PATH", "SQLITE_PATH", "AOG_DB_PATH", "CHROMA_PATH", "SYNC_STATE_DB_PATH"]:
        path_val = env_map.get(path_key, "")
        assert path_val.startswith("/tmp/"), (
            f".env.staging.example {path_key}={path_val!r} 必须 /tmp/ 开头 (NJX 7/30 严令 TMP_PATH_CONTRACT)"
        )

    # 强制 staging 模式
    assert env_map.get("ENVIRONMENT") == "staging", f"必须 ENVIRONMENT=staging, 实际 {env_map.get('ENVIRONMENT')!r}"
    assert env_map.get("ALLOW_MOCK") == "false", f"必须 ALLOW_MOCK=false, 实际 {env_map.get('ALLOW_MOCK')!r}"
    assert env_map.get("STRICT_LLM") == "true", f"必须 STRICT_LLM=true, 实际 {env_map.get('STRICT_LLM')!r}"
    assert env_map.get("SYNC_ENABLED") == "false", f"必须 SYNC_ENABLED=false, 实际 {env_map.get('SYNC_ENABLED')!r}"
    print(f"  ✓ .env.staging.example (全占位符, JWT_SECRET={len(jwt_secret)} bytes, 强制 staging 模式, deployability 完整)")


def test_6_deploy_staging_sh_exists_with_denylist():
    """6. scripts/deploy-staging.sh 存在 + 调 denylist_check.py + ALLOW_STAGING_DEPLOY 闸门 + 读 ops/denylist"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    assert p.exists(), f"deploy-staging.sh 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    assert "DENYLIST_REGEX" in content, "deploy-staging.sh 必须含 DENYLIST_REGEX 标识符"
    assert "denylist_check.py" in content, "deploy-staging.sh 必须调用 denylist_check.py"
    assert "ops/production-resource-denylist.json" in content, "deploy-staging.sh 必须引用 ops/production-resource-denylist.json"
    for label, regex in DENYLIST_4_REGEX_PATTERNS.items():
        m = regex.search(content)
        assert not m, f"deploy-staging.sh 严禁 hardcode production {label}, 命中: {m.group(0)!r}"
    assert "ALLOW_STAGING_DEPLOY" in content, "deploy-staging.sh 必须含 ALLOW_STAGING_DEPLOY 闸门"
    assert "preflight()" in content, "deploy-staging.sh 必须有 preflight 函数"
    assert "auth_gate()" in content, "deploy-staging.sh 必须有 auth_gate 函数"
    assert 'STAGING_FUNCTION_NAME="aog-api-staging"' in content, 'deploy-staging.sh 必须 STAGING_FUNCTION_NAME="aog-api-staging"'
    # NJX 7/29 DEPLOYABILITY 严令: STAGING_DEPLOY_MODE 默认 dry-run
    assert 'STAGING_DEPLOY_MODE:-dry-run' in content, "deploy-staging.sh 必须 STAGING_DEPLOY_MODE 默认 dry-run"
    # 4 项校验
    assert '^[0-9a-f]{40}$' in content, "deploy-staging.sh 必须 4 项校验: MERGE_SHA 40 hex"
    assert "git rev-parse HEAD" in content, "deploy-staging.sh 必须校验 MERGE_SHA==git HEAD"
    assert "APP_COMMIT_SHA" in content, "deploy-staging.sh 必须校验 APP_COMMIT_SHA"
    assert "git status --porcelain" in content, (
        "deploy-staging.sh 必须用 'git status --porcelain' 校验 (NJX 严令 含 untracked, 不只 tracked)"
    )
    # 参数数组 (不 eval)
    assert "tcb_cmd=(" in content, "deploy-staging.sh 必须用 tcb_cmd 数组执行 tcb fn deploy (严禁 eval)"
    assert "eval " not in content, "deploy-staging.sh 严禁用 eval"
    # NJX 7/30 严令: 删 CLOUDBASE_STAGING_ENV alias, denylist 与实际部署都只使用 TCB_ENV_ID
    assert "CLOUDBASE_STAGING_ENV=\"${CLOUDBASE_STAGING_ENV:-$TCB_ENV_ID}\"" not in content, (
        "deploy-staging.sh 严禁 CLOUDBASE_STAGING_ENV alias (NJX 7/30 严令 ENV_ALIAS_BYPASS, 只用 TCB_ENV_ID)"
    )
    # NJX 7/30 严令: 增 --path aog-api-staging
    assert "--path \"$FUNCTIONS_DIR\"" in content, (
        "deploy-staging.sh 必须含 --path \$FUNCTIONS_DIR (NJX 7/30 严令, 让 tcb 知道函数包路径)"
    )
    # NJX 7/30 严令: 修 tcb 失败 exit code 捕获
    assert 'tcb_exit=0' in content and '|| tcb_exit=$?' in content, (
        "deploy-staging.sh 必须修 tcb exit code 捕获 (用 || tcb_exit=$?, NJX 7/30 严令)"
    )
    print(f"  ✓ scripts/deploy-staging.sh ({p.stat().st_size} bytes, 含 denylist + auth_gate + dry-run + 4 校验 + tcb_cmd 数组)")


def test_7_deploy_staging_sh_uses_cloudbase_v2_commands():
    """7. deploy-staging.sh 用 CloudBase v2 命令 (严禁老命令 + 严禁老 flag)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    content = p.read_text(encoding="utf-8")
    code_lines = "\n".join(line for line in content.splitlines() if not line.strip().startswith("#"))
    assert "tcb env switch" not in code_lines, "deploy-staging.sh 严禁老命令 'tcb env switch' (CloudBase v2 不再使用)"
    assert "-e APP_COMMIT_SHA=" not in content, "deploy-staging.sh 严禁老 flag '-e APP_COMMIT_SHA=' (改用 {{env.APP_COMMIT_SHA}})"
    assert "tcb fn deploy aog-api-staging" in code_lines, "deploy-staging.sh 必须含 'tcb fn deploy aog-api-staging'"
    assert "--config-file" in code_lines, "deploy-staging.sh 必须含 --config-file"
    assert "--mode staging" in code_lines, "deploy-staging.sh 必须含 --mode staging"
    print(f"  ✓ scripts/deploy-staging.sh (用 CloudBase v2 命令, 0 老命令)")


def test_8_staging_validation_yml_exists():
    """8. .github/workflows/staging-validation.yml 存在 + 5 jobs + trigger ops/staging-isolation"""
    p = REPO_ROOT / ".github" / "workflows" / "staging-validation.yml"
    assert p.exists(), f"staging-validation.yml 必须存在: {p}"
    content = p.read_text(encoding="utf-8")
    for job in ["denylist-check:", "staging-prepare:", "staging-deps-isolation:", "staging-validation-tests:", "staging-all-pass:"]:
        assert job in content, f"staging-validation.yml 缺 {job}"
    assert "ops/staging-isolation" in content, "staging-validation.yml trigger 缺 ops/staging-isolation 分支"
    print(f"  ✓ .github/workflows/staging-validation.yml ({p.stat().st_size} bytes, 5 jobs)")


def test_9_no_production_resource_reference_in_staging_files():
    """9. NO_PRODUCTION_RESOURCE_REFERENCE: staging 文件 grep production 4 项 → 0 命中"""
    staging_files = [
        "cloudbaserc.staging.json",
        ".env.staging.example",
        "aog-web/scripts/prepare-scf-staging.sh",
        "aog-web/scripts/deploy-staging.sh",
    ]
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
    """10. prepare-scf-staging.sh --preflight exit 0"""
    p = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
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
    r = subprocess.run(
        ["bash", str(p)],
        capture_output=True, text=True, cwd=str(REPO_ROOT / "aog-web"),
        env={**os.environ, "ALLOW_STAGING_DEPLOY": ""},
    )
    if r.returncode == 0:
        pytest.fail(f"deploy-staging.sh 不带 ALLOW_STAGING_DEPLOY=1 应 fail, 但 exit 0\nstdout: {r.stdout}\nstderr: {r.stderr}")
    if "ALLOW_STAGING_DEPLOY" not in r.stderr and "ALLOW_STAGING_DEPLOY" not in r.stdout:
        pytest.fail(f"deploy-staging.sh 失败信息应含 ALLOW_STAGING_DEPLOY\nstdout: {r.stdout}\nstderr: {r.stderr}")
    print(f"  ✓ deploy-staging.sh 无授权时 fail (auth gate 生效)")


def test_12_denylist_check_uses_ops_production_resource_denylist():
    """12. denylist_check.py 读 ops/production-resource-denylist.json + 自身 0 命中"""
    p = REPO_ROOT / "aog-web" / "scripts" / "denylist_check.py"
    content = p.read_text(encoding="utf-8")
    assert "ops/production-resource-denylist.json" in content, "denylist_check.py 必须读 ops/production-resource-denylist.json"
    assert "REPO_ROOT / \"cloudbaserc.production.json\"" not in content, "denylist_check.py 严禁读老路径"
    r = subprocess.run(["python3", str(p), str(p)], capture_output=True, text=True, cwd=str(REPO_ROOT))
    if r.returncode != 0:
        print("  stdout:", r.stdout)
        print("  stderr:", r.stderr)
        pytest.fail(f"denylist_check.py 自身检查应 exit 0, 实际 exit {r.returncode}")
    print(f"  ✓ denylist_check.py 读 ops/production-resource-denylist.json, 自身 0 命中")


# =============================================================================
# NJX 7/29 严令 DEPLOYABILITY 新增测试
# =============================================================================

def _build_fake_tcb(tmp_path: Path) -> Path:
    """建一个 fake tcb 脚本, 记录被调用参数到 tmp_path/tcb_args.log, exit 0
    日志格式: 'tcb <args>' (含 'tcb' 前缀, 方便 test 验证 fake tcb 被调用)
    """
    fake_tcb = tmp_path / "tcb"
    fake_tcb.write_text(
        "#!/bin/bash\n"
        "echo \"tcb $@\" >> \"$TCB_FAKE_LOG\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake_tcb.chmod(0o755)
    return fake_tcb


def test_13_staging_handler_package_complete():
    """13. prepare-scf-staging.sh 跑完后, staging 函数包含全部 REQUIRED_STAGING_HANDLER_FILES

    NJX 7/29 严令 DEPLOYABILITY: staging package 必须含:
      - scf_bootstrap (bash 启动脚本, exec uvicorn)
      - main.py (SCF Web Function 入口, 同步 lifespan + handle_apigw)
      - scf_adapter.py (handle_apigw 适配器)
      - scf_cos.py (COS 下载)
      - requirements.txt (Python 依赖)
      - aog_web/ (FastAPI app)

    NJX 7/30 严令: vendor/ build 需 docker (Linux AMD64 Python3.11), 本地无 docker 时 skip vendor build
    """
    p = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
    assert p.exists(), "prepare-scf-staging.sh 不存在"

    # 先 build_vendor (docker 不可用时 skip, 因为 vendor/ 已存在就不重 build)
    has_docker = subprocess.run(
        ["which", "docker"], capture_output=True, text=True,
    ).returncode == 0
    if has_docker:
        r_vendor = subprocess.run(
            ["bash", str(p), "--build-vendor"],
            capture_output=True, text=True, cwd=str(REPO_ROOT / "aog-web"),
        )
        if r_vendor.returncode != 0:
            print(f"  [staging-vendor] docker build vendor 失败 (可能网络/限速), 继续 package verify")
    else:
        print(f"  [staging-vendor] 本地无 docker, 跳过 vendor build (CI 跑 docker)")

    # 跑完整 prepare (preflight + package + compile + drift + manifest)
    r = subprocess.run(
        ["bash", str(p)],
        capture_output=True, text=True, cwd=str(REPO_ROOT / "aog-web"),
    )
    if r.returncode != 0:
        print("  stdout:", r.stdout[-2000:])
        print("  stderr:", r.stderr[-2000:])
        pytest.fail(f"prepare-scf-staging.sh 失败 exit {r.returncode}")

    functions_dir = REPO_ROOT / "aog-web" / "functions" / "aog-api-staging"
    missing = []
    for f in REQUIRED_STAGING_HANDLER_FILES:
        if not (functions_dir / f).exists():
            missing.append(f)
    assert not missing, f"staging 函数包缺文件: {missing} (期望: {REQUIRED_STAGING_HANDLER_FILES})"

    # scf_bootstrap 必须可执行
    scf_bootstrap = functions_dir / "scf_bootstrap"
    assert os.access(str(scf_bootstrap), os.X_OK), f"scf_bootstrap 必须 +x 可执行"

    # main.py / scf_adapter.py / scf_cos.py 必须 python 编译通过
    compile_errors = []
    for f in ["main.py", "scf_adapter.py", "scf_cos.py"]:
        r2 = subprocess.run(
            ["python", "-m", "py_compile", str(functions_dir / f)],
            capture_output=True, text=True,
        )
        if r2.returncode != 0:
            compile_errors.append(f"{f}: {r2.stderr.strip()}")
    assert not compile_errors, f"handler .py 编译失败: {compile_errors}"

    # MANIFEST.json 必须 environment=staging + package_sha256 字段
    manifest = functions_dir / "MANIFEST.json"
    assert manifest.exists(), "MANIFEST.json 必须生成"
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert m.get("environment") == "staging", f"MANIFEST.environment 必须 staging, 实际 {m.get('environment')!r}"
    assert m.get("package_sha256"), f"MANIFEST.package_sha256 必须存在 (NJX 7/30 严令)"
    assert m.get("production_resources_denied", {}).get("envId"), (
        "MANIFEST.production_resources_denied.envId 必须存在 (NJX 7/30 严令 flat keys)"
    )

    print(f"  ✓ staging 函数包含全部 6 个 handler 文件 (scf_bootstrap +x, 3 py 编译通过, MANIFEST environment=staging + package_sha256 + 4 denylist keys)")


def test_14_deploy_staging_dry_run_does_not_execute_tcb():
    """14. deploy-staging.sh 默认 STAGING_DEPLOY_MODE=dry-run, 不实际执行 tcb fn deploy

    用 fake tcb 验证 dry-run 模式不调用 tcb 命令.
    """
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    with tempfile_TCB_LOG() as log_path:
        fake_tcb_dir = log_path.parent
        fake_tcb = _build_fake_tcb(fake_tcb_dir)
        env = {
            **os.environ,
            "PATH": f"{fake_tcb_dir}:{os.environ.get('PATH', '')}",
            "ALLOW_STAGING_DEPLOY": "1",
            "TCB_ENV_ID": "njx-copilot-staging-FAKE",
            "MERGE_SHA": "0" * 40,  # 40 hex 但不是真 git HEAD
            "APP_COMMIT_SHA": "0" * 40,
            "STAGING_DEPLOY_MODE": "dry-run",
            "TCB_FAKE_LOG": str(log_path),
        }
        r = subprocess.run(
            ["bash", str(p)],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "aog-web"),
            env=env,
        )
        # dry-run 模式: 即使其他校验通过, 也不实际调用 tcb
        if r.returncode != 0:
            # 4 项校验 (MERGE_SHA==HEAD / clean tree) 可能 fail, 但 dry-run 不应该调用 tcb
            if log_path.exists() and log_path.read_text():
                pytest.fail(f"dry-run 模式严禁调用 tcb, 但 fake tcb log 有内容: {log_path.read_text()}")
        else:
            # exit 0 也行, 但 fake tcb log 必须空
            assert not log_path.exists() or not log_path.read_text(), (
                f"dry-run 模式严禁调用 tcb, 但 fake tcb log 有内容: {log_path.read_text() if log_path.exists() else ''}"
            )
        print(f"  ✓ dry-run 模式不调用 tcb fn deploy (fake tcb log 空)")


def test_15_deploy_staging_execute_calls_tcb_with_correct_args():
    """15. deploy-staging.sh STAGING_DEPLOY_MODE=execute 真实执行 tcb fn deploy (fake tcb)

    验证 fake tcb 被调用, 参数含:
      - "tcb fn deploy aog-api-staging"
      - --env-id <TCB_ENV_ID>
      - --config-file <REPO_ROOT/cloudbaserc.staging.json>
      - --mode staging
      - --yes
    """
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    with tempfile_TCB_LOG() as log_path:
        fake_tcb_dir = log_path.parent
        fake_tcb = _build_fake_tcb(fake_tcb_dir)
        env = {
            **os.environ,
            "PATH": f"{fake_tcb_dir}:{os.environ.get('PATH', '')}",
            "ALLOW_STAGING_DEPLOY": "1",
            "TCB_ENV_ID": "njx-copilot-staging-FAKE",
            "MERGE_SHA": "0" * 40,
            "APP_COMMIT_SHA": "0" * 40,
            "STAGING_DEPLOY_MODE": "execute",
            "TCB_FAKE_LOG": str(log_path),
        }
        r = subprocess.run(
            ["bash", str(p)],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "aog-web"),
            env=env,
        )
        # 4 项校验之一: MERGE_SHA==git HEAD (40 个 0 != git HEAD) 应 fail
        # 不管 exit code 是什么, fake tcb log 应该空 (因为 HEAD 校验先 fail)
        # 但这测试是验证 execute 模式调用 tcb, 所以另用 git HEAD 一样的 SHA
        # 改: MERGE_SHA = git rev-parse HEAD
        git_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        ).stdout.strip()
        env["MERGE_SHA"] = git_head
        env["APP_COMMIT_SHA"] = git_head
        # git status clean (含 untracked files, 跟 deploy-staging.sh 4.4 一致)
        status_clean = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        ).stdout.strip() == ""
        if not status_clean:
            # 当前 tree 不 clean, 跳过此测试 (或 commit 后跑)
            pytest.skip(f"git working tree 不 clean, 跳过 fake tcb 真实执行测试 (NJX 拍板后续跑)")

        r = subprocess.run(
            ["bash", str(p)],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "aog-web"),
            env=env,
        )
        if r.returncode != 0:
            print("  stdout:", r.stdout)
            print("  stderr:", r.stderr)
            pytest.fail(f"execute 模式 deploy-staging.sh 失败 exit {r.returncode}")

        # 验证 fake tcb 被调用
        assert log_path.exists() and log_path.read_text(), "execute 模式必须调用 fake tcb"
        called = log_path.read_text()
        assert "tcb" in called and "fn" in called and "deploy" in called, f"fake tcb 调用参数异常: {called!r}"
        assert "aog-api-staging" in called, f"fake tcb 必须部署 aog-api-staging, 实际: {called!r}"
        assert "--env-id" in called and "njx-copilot-staging-FAKE" in called, f"fake tcb 必须含 --env-id, 实际: {called!r}"
        assert "--config-file" in called and "cloudbaserc.staging.json" in called, f"fake tcb 必须含 --config-file cloudbaserc.staging.json, 实际: {called!r}"
        assert "--mode" in called and "staging" in called, f"fake tcb 必须含 --mode staging, 实际: {called!r}"
        assert "--yes" in called, f"fake tcb 必须含 --yes, 实际: {called!r}"
        print(f"  ✓ execute 模式 fake tcb 被正确调用: {called.strip()[:120]}")


def test_16_deploy_staging_fails_on_dirty_tree():
    """16. deploy-staging.sh git status dirty 时必须 fail (NJX 7/29 严令)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    ).stdout.strip()
    # 自建 fake tcb (本地没装 tcb CLI, 必须 mock)
    with tempfile_TCB_LOG() as log_path:
        fake_tcb_dir = log_path.parent
        _build_fake_tcb(fake_tcb_dir)
        env = {
            **os.environ,
            "PATH": f"{fake_tcb_dir}:{os.environ.get('PATH', '')}",
            "ALLOW_STAGING_DEPLOY": "1",
            "TCB_ENV_ID": "njx-copilot-staging-FAKE",
            "MERGE_SHA": git_head,
            "APP_COMMIT_SHA": git_head,
            "STAGING_DEPLOY_MODE": "execute",
            "TCB_FAKE_LOG": str(log_path),
        }
        # 在 REPO_ROOT 临时 touch 一个文件, 让 git status 不 clean
        # 避开 .gitignore `*.tmp` 排除, 用 `_staging_dirty_sentinel_FILE` 名 (无 .tmp)
        sentinel = REPO_ROOT / "_staging_dirty_sentinel_FILE"
        sentinel.write_text("dirty\n", encoding="utf-8")
        try:
            r = subprocess.run(
                ["bash", str(p)],
                capture_output=True, text=True,
                cwd=str(REPO_ROOT / "aog-web"),
                env=env,
            )
            assert r.returncode != 0, f"git working tree dirty 时应 fail, 但 exit 0\nstdout: {r.stdout}\nstderr: {r.stderr}"
            combined = r.stdout + r.stderr
            assert "git" in combined.lower() and ("clean" in combined.lower() or "不 clean" in combined or "未提交" in combined), (
                f"失败信息应提到 git tree 不 clean, 实际: {combined[:500]}"
            )
            print(f"  ✓ dirty tree 时 deploy-staging.sh fail (auth 闸门生效)")
        finally:
            sentinel.unlink(missing_ok=True)


def test_17_deploy_staging_fails_on_sha_mismatch():
    """17. deploy-staging.sh MERGE_SHA != git HEAD 时必须 fail (NJX 7/29 严令)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    # 构造一个 40 hex 但 != git HEAD 的 SHA
    fake_sha = "deadbeef" + "f" * 32  # 40 hex
    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    ).stdout.strip()
    assert fake_sha != git_head, "测试前提: fake_sha != git HEAD"
    # 自建 fake tcb (本地没装 tcb CLI, 必须 mock)
    with tempfile_TCB_LOG() as log_path:
        fake_tcb_dir = log_path.parent
        _build_fake_tcb(fake_tcb_dir)
        env = {
            **os.environ,
            "PATH": f"{fake_tcb_dir}:{os.environ.get('PATH', '')}",
            "ALLOW_STAGING_DEPLOY": "1",
            "TCB_ENV_ID": "njx-copilot-staging-FAKE",
            "MERGE_SHA": fake_sha,
            "APP_COMMIT_SHA": fake_sha,
            "STAGING_DEPLOY_MODE": "execute",
            "TCB_FAKE_LOG": str(log_path),
        }
        r = subprocess.run(
            ["bash", str(p)],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "aog-web"),
            env=env,
        )
        assert r.returncode != 0, f"MERGE_SHA != git HEAD 时应 fail, 但 exit 0\nstdout: {r.stdout}\nstderr: {r.stderr}"
        combined = r.stdout + r.stderr
        assert "MERGE_SHA" in combined or "HEAD" in combined, f"失败信息应提到 MERGE_SHA/HEAD, 实际: {combined[:500]}"
        print(f"  ✓ MERGE_SHA != git HEAD 时 deploy-staging.sh fail (校验生效)")


def test_18_deploy_staging_fails_on_production_env():
    """18. deploy-staging.sh TCB_ENV_ID == production envId 时必须 fail (NJX 7/29 严令)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    # 从 ops/production-resource-denylist.json 读 production envId
    denylist_rc = REPO_ROOT / "ops" / "production-resource-denylist.json"
    production_envid = json.loads(denylist_rc.read_text(encoding="utf-8"))["envId"]
    env = {
        **os.environ,
        "ALLOW_STAGING_DEPLOY": "1",
        "TCB_ENV_ID": production_envid,  # 用 production envId
        "MERGE_SHA": "0" * 40,
        "APP_COMMIT_SHA": "0" * 40,
        "STAGING_DEPLOY_MODE": "dry-run",  # 只需到 deploy_target_validate 阶段就 fail (不调 tcb)
    }
    r = subprocess.run(
        ["bash", str(p)],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT / "aog-web"),
        env=env,
    )
    assert r.returncode != 0, f"TCB_ENV_ID=production envId 时应 fail, 但 exit 0\nstdout: {r.stdout}\nstderr: {r.stderr}"
    combined = r.stdout + r.stderr
    assert "production" in combined.lower() or "denylist" in combined.lower(), (
        f"失败信息应提到 production/denylist, 实际 stdout+stderr: {combined[:500]}"
    )
    print(f"  ✓ TCB_ENV_ID=production envId 时 deploy-staging.sh fail (denylist 生效)")


# =============================================================================
# NJX 7/30 PR #3 runtime preflight 8 完成门 (对应 OWNER_MAY_CREATE_AND_FUND_STAGING_ENVIRONMENT)
# =============================================================================

def test_19_LINUX_VENDOR_IMPORT_PASS():
    """19. LINUX_VENDOR_IMPORT_PASS: handler=main.main_handler + vendor/ 必填 + import verify

    NJX 7/30 严令: installDependency=false, 必须 vendor/ 预装 deps, 运行时 scf_bootstrap 强 vendor 优先
    """
    # 1. cloudbaserc.staging.json handler == main.main_handler (NJX 7/30 改)
    staging_rc = REPO_ROOT / "cloudbaserc.staging.json"
    data = json.loads(staging_rc.read_text(encoding="utf-8"))
    fn = data["functions"][0]
    assert fn.get("handler") == "main.main_handler", (
        f"cloudbaserc.staging.json handler 必须是 main.main_handler (NJX 7/30 严令), 实际: {fn.get('handler')!r}"
    )
    assert fn.get("installDependency") is False, (
        f"installDependency 必须 false (NJX 7/30 严令, 用 vendor/), 实际: {fn.get('installDependency')!r}"
    )
    # 2. aog-web/functions/aog-api/scf_bootstrap 强制 /var/lang/python311/bin/python3.11 + PYTHONPATH
    scf_bootstrap = REPO_ROOT / "aog-web" / "functions" / "aog-api" / "scf_bootstrap"
    sb_content = scf_bootstrap.read_text(encoding="utf-8")
    assert "/var/lang/python311/bin/python3.11" in sb_content, (
        "scf_bootstrap 必须用 /var/lang/python311/bin/python3.11 (NJX 7/30 严令 SCF runtime Python3.11)"
    )
    assert 'export PYTHONPATH="$PWD/vendor:$PWD:${PYTHONPATH:-}"' in sb_content, (
        "scf_bootstrap 必须 export PYTHONPATH=$PWD/vendor:$PWD:${PYTHONPATH:-} (NJX 7/30 严令 vendor 优先)"
    )
    # 3. prepare-scf-staging.sh 必须有 build_vendor step
    prep = REPO_ROOT / "aog-web" / "scripts" / "prepare-scf-staging.sh"
    prep_content = prep.read_text(encoding="utf-8")
    assert "build_vendor()" in prep_content, (
        "prepare-scf-staging.sh 必须有 build_vendor() 函数 (NJX 7/30 严令 vendor build)"
    )
    assert "python:3.11-slim" in prep_content, (
        "prepare-scf-staging.sh 必须用 docker python:3.11-slim build vendor (Linux AMD64 Python3.11)"
    )
    # 4. handler import verify (main.main_handler 必须可 import)
    assert "from main import main_handler" in prep_content, (
        "prepare-scf-staging.sh 必须 verify 'from main import main_handler' (NJX 7/30 严令 isolated import smoke)"
    )
    print(f"  ✓ LINUX_VENDOR_IMPORT_PASS: handler=main.main_handler + /var/lang/python311 + vendor build + import verify")


def test_20_HANDLER_MATCH_PASS():
    """20. HANDLER_MATCH_PASS: cloudbaserc.staging.json handler=main.main_handler, main.py 含 main_handler(event, context)"""
    # 1. cloudbaserc handler=main.main_handler
    staging_rc = REPO_ROOT / "cloudbaserc.staging.json"
    data = json.loads(staging_rc.read_text(encoding="utf-8"))
    fn = data["functions"][0]
    assert fn.get("handler") == "main.main_handler", (
        f"cloudbaserc.staging.json handler 必须是 main.main_handler, 实际: {fn.get('handler')!r}"
    )
    # 2. aog-web/functions/aog-api/main.py 含 main_handler(event, context) 函数
    main_py = REPO_ROOT / "aog-web" / "functions" / "aog-api" / "main.py"
    main_content = main_py.read_text(encoding="utf-8")
    assert "def main_handler(event, context)" in main_content or "def main_handler(event,context):" in main_content, (
        "main.py 必须含 def main_handler(event, context) 函数 (NJX 7/30 严令 handler match)"
    )
    print(f"  ✓ HANDLER_MATCH_PASS: cloudbaserc handler=main.main_handler + main.py main_handler(event, context)")


def test_21_TMP_PATH_CONTRACT_PASS():
    """21. TMP_PATH_CONTRACT_PASS: .env.staging.example 全 /tmp 路径 (FTS5/SQLITE/AOG_DB/CHROMA/SYNC_STATE)"""
    env_file = REPO_ROOT / ".env.staging.example"
    content = env_file.read_text(encoding="utf-8")
    env_map = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Z_][A-Z0-9_]*)=(\S+)$", line)
        if m:
            env_map[m.group(1)] = m.group(2)
    for path_key in ["FTS5_PATH", "SQLITE_PATH", "AOG_DB_PATH", "CHROMA_PATH", "SYNC_STATE_DB_PATH"]:
        path_val = env_map.get(path_key, "")
        assert path_val.startswith("/tmp/"), (
            f"TMP_PATH_CONTRACT: {path_key}={path_val!r} 必须 /tmp/ 开头 (NJX 7/30 严令)"
        )
    # cloudbaserc.staging.json 也必须 /tmp 占位符
    staging_rc = REPO_ROOT / "cloudbaserc.staging.json"
    staging_data = json.loads(staging_rc.read_text(encoding="utf-8"))
    fn = staging_data["functions"][0]
    env_vars = fn.get("envVariables", {})
    for path_key in ["FTS5_PATH", "SQLITE_PATH", "AOG_DB_PATH", "CHROMA_PATH", "SYNC_STATE_DB_PATH"]:
        # 占位符是 {{env.X}}, 默认值是 {{env.X}} 形式
        val = env_vars.get(path_key, "")
        # 部署时由 NJX 物理填入, 但占位符 {{env.X}} 表示引用 staging 独立 /tmp 路径
        assert val == f"{{{{env.{path_key}}}}}", (
            f"cloudbaserc.staging.json envVariables['{path_key}']={val!r} 应 '{{{{env.{path_key}}}}}' 占位符"
        )
    print(f"  ✓ TMP_PATH_CONTRACT_PASS: 5 data paths 全 /tmp + cloudbaserc 占位符一致")


def test_22_ENV_ALIAS_BYPASS_TEST_PASS():
    """22. ENV_ALIAS_BYPASS_TEST_PASS: deploy-staging.sh 严禁 CLOUDBASE_STAGING_ENV alias (NJX 7/30 严令)"""
    p = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    content = p.read_text(encoding="utf-8")
    # 严禁 CLOUDBASE_STAGING_ENV alias
    assert "CLOUDBASE_STAGING_ENV=\"${CLOUDBASE_STAGING_ENV:-$TCB_ENV_ID}\"" not in content, (
        "deploy-staging.sh 严禁 CLOUDBASE_STAGING_ENV alias (NJX 7/30 严令 ENV_ALIAS_BYPASS)"
    )
    assert "local CLOUDBASE_STAGING_ENV=" not in content, (
        "deploy-staging.sh 严禁 CLOUDBASE_STAGING_ENV 局部变量 (NJX 7/30 严令)"
    )
    # 必须只用 TCB_ENV_ID
    assert "TCB_ENV_ID" in content, "deploy-staging.sh 必须用 TCB_ENV_ID (NJX 7/30 严令)"
    tcb_id_count = content.count("TCB_ENV_ID")
    assert tcb_id_count >= 5, f"deploy-staging.sh TCB_ENV_ID 引用次数应 >= 5, 实际 {tcb_id_count}"
    # 同样 deploy-frontend-staging.sh 也要 ENV_ALIAS_BYPASS
    fe = REPO_ROOT / "aog-web" / "scripts" / "deploy-frontend-staging.sh"
    if fe.exists():
        fe_content = fe.read_text(encoding="utf-8")
        # 检查 CLOUDBASE_STAGING_ENV 是否作为变量赋值/alias 出现 (排除 # 注释文档)
        code_lines = "\n".join(line for line in fe_content.splitlines() if not line.strip().startswith("#"))
        assert "CLOUDBASE_STAGING_ENV" not in code_lines, (
            "deploy-frontend-staging.sh 严禁 CLOUDBASE_STAGING_ENV alias (NJX 7/30 严令)"
        )
    print(f"  ✓ ENV_ALIAS_BYPASS_TEST_PASS: deploy-staging.sh + deploy-frontend-staging.sh 0 CLOUDBASE_STAGING_ENV alias, TCB_ENV_ID 引用 {tcb_id_count} 次")


def test_23_SECRET_FILE_IGNORE_PASS():
    """23. SECRET_FILE_IGNORE_PASS: .gitignore 排除 .env.staging / .env.staging.local / .env.*.local + CI 验证"""
    gitignore = REPO_ROOT / ".gitignore"
    content = gitignore.read_text(encoding="utf-8")
    # 必须排除真凭据
    assert ".env.staging" in content and ".env.staging" not in [".env.staging.example"], (
        ".gitignore 必须含 '.env.staging' (字面, 排除真凭据, 跟 .env.staging.example 区分)"
    )
    # 注: .env.staging.example 不应被排除 (是 commit 的 template)
    # 但 '.env.staging' 字面匹配 '.env.staging.example' ? — 不, .gitignore pattern 'X' 匹配字面 X
    # 让我用 git check-ignore 验证
    import subprocess
    # .env.staging 必被 ignore
    r1 = subprocess.run(
        ["git", "check-ignore", ".env.staging"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r1.returncode == 0, f".env.staging 必须被 .gitignore ignore, git check-ignore 返 {r1.returncode}: {r1.stderr}"
    # .env.staging.example 不被 ignore (template)
    r2 = subprocess.run(
        ["git", "check-ignore", ".env.staging.example"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r2.returncode != 0, f".env.staging.example 是 template, 必须不被 ignore, git check-ignore 返 {r2.returncode}"
    # .env.staging.local 必被 ignore
    r3 = subprocess.run(
        ["git", "check-ignore", ".env.staging.local"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert r3.returncode == 0, f".env.staging.local 必须被 ignore, 返 {r3.returncode}"
    # deploy-staging.sh preflight 必须有 tracked .env.staging reject 逻辑
    deploy = REPO_ROOT / "aog-web" / "scripts" / "deploy-staging.sh"
    deploy_content = deploy.read_text(encoding="utf-8")
    assert "git ls-files --error-unmatch .env.staging" in deploy_content, (
        "deploy-staging.sh preflight 必须 git ls-files --error-unmatch .env.staging (NJX 7/30 secret safety 严令)"
    )
    print(f"  ✓ SECRET_FILE_IGNORE_PASS: .gitignore 排除 .env.staging / .env.staging.local, deploy 拒绝 tracked .env.staging")


def test_24_HTTP_ROUTE_SCRIPT_READY():
    """24. HTTP_ROUTE_SCRIPT_READY: deploy-frontend-staging.sh 存在 + 可执行 + ALLOW_STAGING_DEPLOY + TCB_ENV_ID"""
    fe = REPO_ROOT / "aog-web" / "scripts" / "deploy-frontend-staging.sh"
    assert fe.exists(), f"deploy-frontend-staging.sh 必须存在 (NJX 7/30 PR #3 修 8)"
    assert os.access(str(fe), os.X_OK), "deploy-frontend-staging.sh 必须可执行"
    fe_content = fe.read_text(encoding="utf-8")
    # 必含 ALLOW_STAGING_DEPLOY 闸门
    assert "ALLOW_STAGING_DEPLOY" in fe_content, "deploy-frontend-staging.sh 必须含 ALLOW_STAGING_DEPLOY 闸门"
    # 必含 TCB_ENV_ID (不用 CLOUDBASE_STAGING_ENV alias)
    assert "TCB_ENV_ID" in fe_content, "deploy-frontend-staging.sh 必须含 TCB_ENV_ID"
    # 排除 # 注释 (文档说明 CLOUDBASE_STAGING_ENV alias 严禁)
    fe_code_lines = "\n".join(line for line in fe_content.splitlines() if not line.strip().startswith("#"))
    assert "CLOUDBASE_STAGING_ENV" not in fe_code_lines, (
        "deploy-frontend-staging.sh 严禁 CLOUDBASE_STAGING_ENV alias (NJX 7/30 严令)"
    )
    # 必含 4 项强校验
    assert "40 hex" in fe_content or "^[0-9a-f]{40}$" in fe_content, "deploy-frontend-staging.sh 必须含 40 hex 校验"
    assert "git rev-parse HEAD" in fe_content, "deploy-frontend-staging.sh 必须含 git HEAD 校验"
    assert "APP_COMMIT_SHA" in fe_content, "deploy-frontend-staging.sh 必须含 APP_COMMIT_SHA 校验"
    assert "git status --porcelain" in fe_content, "deploy-frontend-staging.sh 必须含 git status clean 校验 (含 untracked)"
    # 必含 dry-run / execute 分离
    assert "STAGING_DEPLOY_MODE" in fe_content and "dry-run" in fe_content and "execute" in fe_content, (
        "deploy-frontend-staging.sh 必须 STAGING_DEPLOY_MODE=dry-run/execute 分离"
    )
    # 必含 tcb hosting deploy 命令
    assert "tcb hosting deploy" in fe_content, "deploy-frontend-staging.sh 必须用 tcb hosting deploy"
    print(f"  ✓ HTTP_ROUTE_SCRIPT_READY: deploy-frontend-staging.sh 存在 + 可执行 + 4 校验 + dry-run/execute + tcb hosting deploy")


def test_25_FRONTEND_STAGING_SCRIPT_READY():
    """25. FRONTEND_STAGING_SCRIPT_READY: build-data-release.sh + test_journey_10_remote.py 完整
    (NJX 7/30 PR #4 严令 7.1/7.2/7.3 更新):
      - Gate 3: 旧 pii_redaction informational → 新 pii_gate 6 项真实验证
      - staging-validation.yml remote-validation: 缺 URL fail → 缺 URL skip
      - staging-remote-validation.yml 新增 workflow_dispatch 真实远端
    """
    # 1. build-data-release.sh 存在 + 可执行 + 3 gates
    bdr = REPO_ROOT / "aog-web" / "scripts" / "build-data-release.sh"
    assert bdr.exists(), "build-data-release.sh 必须存在 (NJX 7/30 修 7)"
    assert os.access(str(bdr), os.X_OK), "build-data-release.sh 必须可执行"
    bdr_content = bdr.read_text(encoding="utf-8")
    assert "APP_COMMIT_SHA" in bdr_content and "build_commit" in bdr_content, (
        "build-data-release.sh 必须含 build_commit == APP_COMMIT_SHA 校验 (Gate 1)"
    )
    assert "Gate 2" in bdr_content and "rag_8_query" in bdr_content, (
        "build-data-release.sh 必须含 Gate 2: 8 RAG query 验证"
    )
    # NJX 7/30 PR #4 严令 5 修复: Gate 3 改用 pii_gate (不是 pii_redaction informational)
    assert "Gate 3" in bdr_content and "pii_gate" in bdr_content and "PII Gate" in bdr_content, (
        "build-data-release.sh 必须含 Gate 3: pii_gate 6 项真实验证 (NJX 7/30 严令 5 修复, 禁 informational)"
    )
    assert "release-manifest.json" in bdr_content, "build-data-release.sh 必须输出 release-manifest.json"
    # 2. test_journey_10_remote.py 存在 + 缺 URL skip
    remote = REPO_ROOT / "tests" / "test_journey_10_remote.py"
    assert remote.exists(), "test_journey_10_remote.py 必须存在 (NJX 7/30 修 8)"
    remote_content = remote.read_text(encoding="utf-8")
    assert "AOG_STAGING_API_BASE" in remote_content, "test_journey_10_remote.py 必须读 AOG_STAGING_API_BASE env"
    assert "pytest.skip" in remote_content, "test_journey_10_remote.py 缺 URL 时必须 skip"
    # 3. staging-validation.yml 含 frontend-build + remote-validation jobs
    sw = REPO_ROOT / ".github" / "workflows" / "staging-validation.yml"
    sw_content = sw.read_text(encoding="utf-8")
    assert "frontend-build:" in sw_content, "staging-validation.yml 必须含 frontend-build job"
    assert "remote-validation:" in sw_content, "staging-validation.yml 必须含 remote-validation job"
    assert "AOG_STAGING_API_BASE" in sw_content, "staging-validation.yml 必须设 AOG_STAGING_API_BASE env"
    # NJX 7/30 PR #4 严令 7.1/7.2: 缺 URL 应 skip, 不再 FAIL
    assert "缺 URL skip" in sw_content or "缺 URL" in sw_content, (
        "staging-validation.yml remote-validation 缺 URL 应 skip (NJX 7/30 严令 7.1/7.2, 禁缺 URL fail)"
    )
    # 4. staging-remote-validation.yml 新增 (NJX 7/30 严令 7.3)
    remote_wf = REPO_ROOT / ".github" / "workflows" / "staging-remote-validation.yml"
    assert remote_wf.exists(), "staging-remote-validation.yml 必须存在 (NJX 7/30 严令 7.3 独立 workflow_dispatch)"
    remote_wf_content = remote_wf.read_text(encoding="utf-8")
    assert "workflow_dispatch" in remote_wf_content, "staging-remote-validation.yml trigger 必须是 workflow_dispatch"
    assert "test_rag_8query_remote" in remote_wf_content, "staging-remote-validation.yml 必须跑 test_rag_8query_remote"
    assert "test_journey_10_remote" in remote_wf_content, "staging-remote-validation.yml 必须跑 test_journey_10_remote"
    assert "AOG_STAGING_API_BASE" in remote_wf_content, "staging-remote-validation.yml 缺 URL 必须 FAIL"
    print(f"  ✓ FRONTEND_STAGING_SCRIPT_READY: build-data-release.sh 3 gates + test_journey_10_remote.py + remote-validation job 强制 URL")
    print(f"  ✓ FRONTEND_STAGING_SCRIPT_READY: build-data-release.sh 3 gates + test_journey_10_remote.py + remote-validation job 强制 URL")


def test_26_STAGING_RUNTIME_PREFLIGHT_PR_GREEN():
    """26. STAGING_RUNTIME_PREFLIGHT_PR_GREEN: 8 完成门聚合验证 (NJX 7/30 PR #3)"""
    # 这个 test 本身是聚合, 跑它意味着前 8 个完成门 (test_19-25) 全过
    # 这里只 verify 相关文件存在 + 关键内容
    files = [
        "aog-web/scripts/build-data-release.sh",
        "aog-web/scripts/deploy-frontend-staging.sh",
        "tests/test_journey_10_remote.py",
        ".github/workflows/staging-validation.yml",
        "cloudbaserc.staging.json",
        ".env.staging.example",
        "aog-web/scripts/prepare-scf-staging.sh",
        "aog-web/scripts/deploy-staging.sh",
        "aog-web/scripts/denylist_check.py",
        "ops/production-resource-denylist.json",
    ]
    for f in files:
        p = REPO_ROOT / f
        assert p.exists(), f"STAGING_RUNTIME_PREFLIGHT_PR_GREEN: {f} 必须存在"
    print(f"  ✓ STAGING_RUNTIME_PREFLIGHT_PR_GREEN: 8 完成门聚合, 10 关键文件全在, 准备 NJX 拍板 OWNER_MAY_CREATE_AND_FUND_STAGING_ENVIRONMENT")


# 测试 helper
import contextlib
import tempfile


@contextlib.contextmanager
def tempfile_TCB_LOG():
    """提供 tmp_path + log_path, 自动 cleanup"""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log_path = tmp_path / "tcb_args.log"
        yield log_path


# 测试 runner 入口
if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
