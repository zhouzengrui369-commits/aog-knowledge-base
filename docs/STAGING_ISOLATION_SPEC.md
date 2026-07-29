<!-- _spec_denylist_documentation_only: true -->
<!-- 本文件含 production 4 项 denylist 描述 (envId / function / bucket / domain), 仅作 documentation 用途 -->
<!-- staging 脚本/配置严禁 hardcode 这 4 项, 必须从 ops/production-resource-denylist.json 读 (DENYLIST_REGEX 策略) -->
<!-- CI staging-validation.yml 通过 _spec_denylist_documentation_only 标记白名单本文件 -->

# AOG Knowledge Base · Staging Isolation Spec

> **文件性质**: 规范性安全/运维合同 (NJX 7/29 授权)
> **不允许内容**: current head / 临时 CI run ID / 动态完成状态
> **作用域**: production (CloudBase envId `njx-copilot-d6gs7642f8fa17122`) 完全不动, staging 全新边界
> **当前 PR 阶段**: 仅规范 + 脚本 + 防误部署代码, **不动云资源** (NJX 7/29 拍板)

---

## 1. Production 资源 (staging 严禁触碰的 denylist)

> 完整 4 项 production 值见 `ops/production-resource-denylist.json` (`_isolated_for_staging_denylist_only: true` 标记, 仅作 denylist reference, 严禁 staging 脚本实际引用)

| 资源类型 | 含义 | staging 必须隔离 |
|---------|------|------------------|
| CloudBase envId | production 环境 ID | **staging 严禁引用** (denylist) |
| SCF 函数名 | production 函数名 | **staging 严禁引用** (denylist) |
| COS bucket | production 存储桶 | **staging 严禁引用** (denylist) |
| 域名 | production 业务域名 | **staging 严禁引用** (denylist) |

任何 staging 脚本 (prepare-scf-staging.sh / deploy-staging.sh / staging-validation.yml) 必须包含 denylist check, 启动时用 `denylist_check.py` 严格检查不包含这 4 个 production 值.

## 2. Staging 必须独立的新资源 (NJX 拍板: 独立 CloudBase 环境方案)

| 资源 | staging 要求 | NJX 操作 | 当前 PR 必填? |
|------|--------------|----------|--------------|
| CloudBase envId | 新 ID, 跟 production 不同 | NJX 在 CloudBase 控制台创建新环境 | ❌ 远端验收前必填 |
| SCF 函数 | `aog-api-staging` (独立函数名, 不复用 production) | NJX 在 staging env 创函数 | ❌ 远端验收前必填 |
| 域名 (第一轮) | **CloudBase 默认域名** (不配 aog-staging.njx.com CNAME) | 自动 | ❌ 当前 PR 不要求 |
| 域名 (第二轮, 可选) | `aog-staging.njx.com` (sub-domain, 不复用 production) | NJX 配 sub-domain CNAME | ❌ 远端验收通过后可选项 |
| COS bucket | 新 ID, 跟 production 不同 | NJX 在 staging env 创 bucket | ❌ 远端验收前必填 |
| 凭据 | 独立 `MINIMAX_API_KEY` (staging 凭据, 不复用 production) | NJX 申请 | ❌ 远端验收前必填 |
| DATABASE/SQLite | production aog.db snapshot → 一次性复制到 staging (不实时同步) | NJX 执行 | ❌ 远端验收前必填 |
| 强制 env vars | `ENVIRONMENT=staging` / `ALLOW_MOCK=false` / `STRICT_LLM=true` / `SYNC_ENABLED=false` | PM 部署时设 | ✅ 已写入 cloudbaserc.staging.json v2 envVariables |
| `APP_COMMIT_SHA` | merge commit SHA (锁定) | CI 注入 `{{env.APP_COMMIT_SHA}}` | ✅ 已写入 cloudbaserc.staging.json v2 |

## 3. Staging 准备工具 (PM 任务, 不需 NJX 充值即可完成)

### 3.1 `scripts/prepare-scf-staging.sh` (新建)

- 只允许 package/compile/drift/manifest/preflight
- 不允许执行任何云端写操作
- 输出到独立 staging 路径 `functions/aog-api-staging/aog_web/`
- 包含 denylist check (脚本启动时跑 `denylist_check.py`, 命中 production 4 项则 exit 1)
- 包含 SCF_ALLOWLIST.txt (跟 production 同步 + 加 staging 标识)

### 3.2 `cloudbaserc.staging.json` (新建, CloudBase v2 正式结构)

CloudBase v2 schema (NJX 7/29 拍板):
- `version: "2.0"`
- `envId: "{{env.TCB_ENV_ID}}"` (占位符, 部署时由 TCB_ENV_ID env 注入)
- `functionRoot: "./aog-web/functions"`
- `functions[]`: 含 `aog-api-staging` (Python3.11, 256MB, 30s timeout, installDependency: true)
- `envVariables[]`: `{{env.MINIMAX_API_KEY}}` / `{{env.APP_COMMIT_SHA}}` 等占位符, 部署时 CI 注入
- 严禁 production 4 项字面量 (denylist 严格)

### 3.3 `ops/production-resource-denylist.json` (新建, 仅 denylist)

- 记录 production 4 项 (envId / function_name / bucket / domain) 作为 denylist 镜像
- 仅供 staging 脚本 `denylist_check.py` 校验, 严禁 staging 脚本实际引用
- 文件头 `_isolated_for_staging_denylist_only: true` (强制标记)
- 路径在 `ops/` 目录下, 不跟 `cloudbaserc.*.json` 同级, 避免被误认为可部署 rc

### 3.4 `.env.staging.example` (新建)

- 独立 staging 凭据模板, 占位符 `xxx-STAGING-PLACEHOLDER-xxx`
- 必含: `TCB_ENV_ID` / `APP_COMMIT_SHA` / `ENVIRONMENT=staging` / `ALLOW_MOCK=false` / `STRICT_LLM=true` / `SYNC_ENABLED=false`
- 不含: production `MINIMAX_API_KEY` / production `COS_*` / production 4 项字面量
- 不含: `aog-staging.njx.com` 字面量 (CNAME 是远端验收通过后的可选项, 当前 PR 不要求)

### 3.5 `scripts/deploy-staging.sh` (新建, 含 denylist preflight + CloudBase v2 命令)

- 启动时:
  1. denylist check: `denylist_check.py` 严格检查 staging 脚本 + 配置
  2. auth_gate: 必须 `ALLOW_STAGING_DEPLOY=1` 显式授权
  3. verify_package: staging 函数包完整 (≥30 py files)
  4. deploy_target_validate: 严禁 deploy 到 production (用 python 读 denylist 严格比较)
- 部署目标: `aog-api-staging` (独立函数, 严禁 production 函数)
- 严禁老命令 `tcb env switch` (CloudBase v2 不再使用)
- 严禁老 flag `-e APP_COMMIT_SHA=` (改用 cloudbaserc.staging.json envVariables + `{{env.APP_COMMIT_SHA}}`)
- 正确命令: `tcb fn deploy aog-api-staging --env-id "$TCB_ENV_ID" --config-file cloudbaserc.staging.json --mode staging --yes`
- **当前 PM 阶段**: 仅 preflight + verify_package + deploy_target_validate, 不实际 `tcb fn deploy` (NJX 拍板后由 NJX 物理执行)

### 3.6 `staging-validation.yml` (新建 CI workflow)

- trigger: push to `ops/staging-isolation` 分支 + PR 到 main
- jobs:
  1. `denylist-check`: 跑 `denylist_check.py` 验证 staging 脚本 + 配置不含 production 4 项
  2. `staging-prepare`: 跑 `prepare-scf-staging.sh`, 验证 `functions/aog-api-staging/aog_web/` 完整 + drift 0
  3. `staging-deps-isolation`: 验证 staging 脚本用占位符, 不含真 production 凭据
  4. `staging-validation-tests`: 跑新增的 `staging_isolation_test.py` 全部 unit tests
  5. `staging-all-pass`: aggregate, 全部 job 通过

### 3.7 staging isolation CI tests (新增 `tests/staging_isolation_test.py`)

测试:
- 全部 staging 脚本不含 production 4 项 denylist (regex word boundary 排除合法 staging 后缀)
- `cloudbaserc.staging.json` 是 v2 schema (含 `version: "2.0"` + `functionRoot` + `functions[]` + `envVariables`)
- `cloudbaserc.staging.json` 不含 production 4 项字面量
- `cloudbaserc.staging.json` 含 `{{env.TCB_ENV_ID}}` + `{{env.*}}` 占位符
- `ops/production-resource-denylist.json` 含 `_isolated_for_staging_denylist_only: true`
- `.env.staging.example` 默认值用占位符, 不含真 production 凭据
- `.env.staging.example` 不含 `aog-staging.njx.com` 字面量 (CNAME 是远端验收后可选项)
- `deploy-staging.sh` 启动会做 denylist preflight (未设 `ALLOW_STAGING_DEPLOY=1` 时 exit 1)
- `deploy-staging.sh` 不含老命令 `tcb env switch` 和老 flag `-e APP_COMMIT_SHA=`
- `prepare-scf-staging.sh` 输出到独立 staging 路径, 跟 production `functions/aog-api` 隔离
- `staging-validation.yml` 包含 denylist-check job

## 4. RAG 远程回归 (staging 验收阶段执行, 不需本 PR 完成)

`pipeline/tests/test_rag_8query_remote.py` 已写好 (commit 23f8604 含), 等 NJX 提供:
- `AOG_STAGING_API_BASE` 环境变量 (staging URL, 第一轮是 CloudBase 默认域名)
- staging 函数/前端/COS 部署完成

跑真实远端:
- 8 RAG query 通过真实 staging `/api/chat`
- PII negative: 真实 `/api/city/H-赫尔辛基` 不含 raw phone
- 10 旅程: 真实 staging URL 上跑 `test_journey_10_local.py` 改 base

## 5. 完成门 (STAGING_ISOLATION_PR_GREEN)

PR (ops/staging-isolation → main) 必须满足:

| # | 门 | 验证 |
|---|----|------|
| 1 | `docs/STAGING_ISOLATION_SPEC.md` 存在 + 含 `_spec_denylist_documentation_only: true` | `test -f` + `grep` |
| 2 | `scripts/prepare-scf-staging.sh` 存在 + 调 `denylist_check.py` + 引用 `ops/production-resource-denylist.json` | `bash scripts/prepare-scf-staging.sh --preflight` |
| 3 | `cloudbaserc.staging.json` 是 CloudBase v2 schema (含 `version: "2.0"` + `functionRoot` + `functions[]` + `envVariables`) | `yaml/json 解析 + 字段检查` |
| 4 | `cloudbaserc.staging.json` 不含 production 4 项字面量 + 含 `{{env.*}}` 占位符 | `grep` + `denylist_check.py` |
| 5 | `ops/production-resource-denylist.json` 存在 + 含 `_isolated_for_staging_denylist_only: true` 标记 | `test -f` + `grep` |
| 6 | `.env.staging.example` 全占位符 + 不含 `aog-staging.njx.com` 字面量 | `grep` |
| 7 | `scripts/deploy-staging.sh` 存在 + 调 `denylist_check.py` + 含 `ALLOW_STAGING_DEPLOY` 闸门 | `bash scripts/deploy-staging.sh` (无 `ALLOW_STAGING_DEPLOY`) 应 exit 1 |
| 8 | `deploy-staging.sh` 不含 `tcb env switch` + 不含 `-e APP_COMMIT_SHA=` | `grep` |
| 9 | `staging-validation.yml` 存在 + 含 denylist-check job | `grep denylist-check` |
| 10 | `tests/staging_isolation_test.py` 10 项全过 | `pytest` |
| 11 | `NO_PRODUCTION_RESOURCE_REFERENCE` 4 staging 文件 0 production 命中 | `denylist_check.py` |
| 12 | CI green on `ops/staging-isolation` push + pull_request 触发 staging-validation 全 success | GitHub Actions |

12/12 PASS → 创建 Draft PR → CI 5/5 jobs success → Ready/Merge

**Merge 后第二阶段 (status PR 收口)**:
- NJX 5 步物理操作 (创建 staging env / 申请独立 MINIMAX_API_KEY / 创建独立 COS bucket / 充值)
- (可选) 配 `aog-staging.njx.com` sub-domain CNAME
- `bash scripts/deploy-staging.sh` (带 `ALLOW_STAGING_DEPLOY=1 MERGE_SHA=...`)
- 跑真实远端 10 旅程 + 8 RAG + PII 验证
- 第二个小型 receipt/status PR 记录部署证据 + PROJECT_STATE 更新

## 6. NJX 拍板后才可执行的动作 (第二阶段, 不在本 PR)

- 在 CloudBase 控制台创建 **staging 环境** (新 envId)
- 申请独立 staging `MINIMAX_API_KEY` 凭据
- 创建独立 COS bucket (staging 命名空间)
- 充值 staging env (PM 建议 ¥50-100 够跑 7 天测试)
- (可选, 远端验收通过后) 配 `aog-staging.njx.com` sub-domain CNAME
- 跑 `bash scripts/deploy-staging.sh` (带 `ALLOW_STAGING_DEPLOY=1 MERGE_SHA=...`)
- 提供 `AOG_STAGING_API_BASE` 给 PM 跑远程 RAG 回归

## 7. NJX 严令禁止 (再次强调)

- ❌ staging 脚本任何位置 hardcode production 4 项 (必须从 `ops/production-resource-denylist.json` 读)
- ❌ staging 部署到 production 函数
- ❌ staging 数据写入 production COS bucket
- ❌ staging URL 用 production 业务域名 (第一轮用 CloudBase 默认域名, 第二轮可选 `aog-staging.njx.com`)
- ❌ staging 凭据复用 production `MINIMAX_API_KEY`
- ❌ staging 文档写 current head / 临时 CI run ID / 动态完成状态
- ❌ staging 准备直接 push main (必须独立 PR ops/staging-isolation → main)
- ❌ staging 验收未跑真实远端就用 in-process TestClient 替代
- ❌ staging 部署用 `tcb env switch` 老命令 (CloudBase v2 不再使用)
- ❌ staging 部署用 `-e APP_COMMIT_SHA=` 老 flag (改用 `{{env.APP_COMMIT_SHA}}` 占位符)
- ❌ 第一轮 staging 部署前 NJX 创建 `aog-staging.njx.com` CNAME (远端验收通过后的可选项)
- ❌ 本阶段 (规范 PR) NJX 充值 / 建环境 / 建 bucket / 配 DNS / 部署
