# AOG Knowledge Base · Staging Isolation Spec

<!-- _spec_denylist_documentation_only: true -->
<!-- 本文件含 production 4 项 denylist 描述 (envId / function / bucket / domain), 仅作 documentation 用途 -->
<!-- staging 脚本/配置严禁 hardcode 这 4 项, 必须从 cloudbaserc.production.json 读 (DENYLIST_REGEX 策略) -->
<!-- CI staging-validation.yml 通过 _spec_denylist_documentation_only 标记白名单本文件 -->

> **文件性质**: 规范性安全/运维合同 (NJX 7/29 授权)
> **不允许内容**: current head / 临时 CI run ID / 动态完成状态
> **作用域**: production (CloudBase envId `njx-copilot-d6gs7642f8fa17122`) 完全不动, staging 全新边界

---

## 1. Production 资源 (staging 严禁触碰的 denylist)

| 资源 | production 值 | staging 必须隔离 |
|------|----------------|------------------|
| CloudBase envId | `njx-copilot-d6gs7642f8fa17122` | **staging 严禁引用** (denylist) |
| SCF 函数 | `aog-api` | **staging 严禁引用** (denylist) |
| COS bucket | `aog-prod-data-1343051603` (ap-shanghai) | **staging 严禁引用** (denylist) |
| 域名 | `aog.njx.com` | **staging 严禁引用** (denylist) |

任何 staging 脚本 (prepare-scf-staging.sh / deploy-staging.sh / staging-validation.yml) 必须包含 denylist check, 启动时 grep 自身脚本不包含这 4 个 production 值.

## 2. Staging 必须独立的新资源 (NJX 拍板: 独立 CloudBase 环境方案)

| 资源 | staging 要求 | NJX 操作 |
|------|--------------|----------|
| CloudBase envId | 新 ID, 跟 production 不同 | NJX 在 CloudBase 控制台创建新环境 |
| SCF 函数 | `aog-api-staging` (独立函数名, 不复用 `aog-api`) | NJX 在 staging env 创函数 |
| Hosting | `aog-staging.njx.com` (sub-domain, 不复用 `aog.njx.com`) | NJX 配 sub-domain CNAME |
| COS bucket | `aog-staging-data-XXXXXXXX` (新 ID) | NJX 在 staging env 创 bucket |
| 凭据 | 独立 `MINIMAX_API_KEY` (staging 凭据, 不复用 production) | NJX 申请 |
| DATABASE/SQLite | production aog.db snapshot → 一次性复制到 staging (不实时同步) | NJX 执行 |
| 强制 env vars | `ENVIRONMENT=staging` / `ALLOW_MOCK=false` / `STRICT_LLM=true` / `APP_COMMIT_SHA=$MERGE_SHA` / `SYNC_ENABLED=false` | PM 部署时设 |

## 3. Staging 准备工具 (PM 任务, 不需 NJX 充值即可完成)

### 3.1 `scripts/prepare-scf-staging.sh` (新建)

- 只允许 package/compile/drift/manifest/preflight
- 不允许执行任何云端写操作
- 输出到独立 staging 路径 `functions/aog-api-staging/aog_web/`
- 包含 denylist check (脚本启动时 grep production 4 项, 命中则 exit 1)
- 包含 SCF_ALLOWLIST.txt (跟 production 同步 + 加 staging 标识)

### 3.2 `cloudbaserc.staging.json` (新建)

- mock 结构, 独立 envId (placeholder `njx-copilot-staging-XXXXXXXX`)
- function name = `aog-api-staging`
- region = `ap-shanghai` (跟 production 同 region, 不同 env)
- **不** 含 production 任何凭据 (no `njx-copilot-d6gs7642f8fa17122` / no `aog-prod-data-1343051603`)

### 3.3 `cloudbaserc.production.json` (新建, denylist reference)

- 记录 production 4 项 (envId / function / bucket / domain) 作为 denylist 镜像
- 仅供 staging 脚本 `grep -v` 校验, 严禁 staging 脚本实际引用
- 标记 `isolated_for_staging_denylist_only: true` (文件头注释)

### 3.4 `.env.staging.example` (新建)

- 独立 staging 凭据模板, 占位符 `xxx-STAGING-PLACEHOLDER-xxx`
- 必含: `ENVIRONMENT=staging` / `ALLOW_MOCK=false` / `STRICT_LLM=true` / `SYNC_ENABLED=false`
- 不含: production `MINIMAX_API_KEY` / production `COS_*` / production `aog-prod-data-1343051603`

### 3.5 `scripts/deploy-staging.sh` (新建, 含 denylist preflight)

- 启动时:
  1. denylist check: `grep -E "njx-copilot-d6gs7642f8fa17122|aog-api[^a-z-]|aog-prod-data-1343051603|aog.njx.com" "$0"`
  2. 命中任一 production 值 → exit 1
  3. 仅当 NJX 设 `ALLOW_STAGING_DEPLOY=1` env 才执行 `tcb fn deploy aog-api-staging`
- 部署目标: `aog-api-staging` (独立函数, 严 deploy `aog-api` 失败)
- 部署后输出: `STAGING_DEPLOYMENT_ID` / `APP_COMMIT_SHA` / `STAGING_URL`

### 3.6 `staging-validation.yml` (新建 CI workflow)

- trigger: push to `ops/staging-isolation` 分支 + PR 到 main
- jobs:
  1. `denylist-check`: 跑 denylist grep 全部 staging 脚本, 命中 production → fail
  2. `staging-prepare`: 跑 `prepare-scf-staging.sh`, 验证 functions/aog-api-staging/aog_web 完整 + drift 0
  3. `staging-deps-isolation`: 验证 staging 脚本不引用 production 凭据/COS/域名
  4. `staging-validation-tests`: 跑新增的 staging isolation unit tests

### 3.7 staging isolation CI tests (新增 `tests/staging_isolation_test.py`)

测试:
- 全部 staging 脚本不含 production 4 项 denylist
- `cloudbaserc.staging.json` 不含 `njx-copilot-d6gs7642f8fa17122`
- `.env.staging.example` 默认值用占位符, 不含真 production 凭据
- `deploy-staging.sh` 启动会做 denylist preflight (未设 ALLOW_STAGING_DEPLOY=1 时 exit 1)
- `prepare-scf-staging.sh` 输出到独立 staging 路径, 跟 production functions/aog-api 隔离
- `staging-validation.yml` 包含 denylist-check job

## 4. RAG 远程回归 (staging 验收阶段执行, 不需本 PR 完成)

`pipeline/tests/test_rag_8query_remote.py` 已写好 (commit 23f8604 含), 等 NJX 提供:
- `AOG_STAGING_API_BASE` 环境变量 (staging URL)
- staging 函数/前端/COS 部署完成

跑真实远端:
- 8 RAG query 通过真实 staging `/api/chat`
- PII negative: 真实 `/api/city/H-赫尔辛基` 不含 raw phone
- 10 旅程: 真实 staging URL 上跑 test_journey_10_local.py 改 base

## 5. 完成门 (STAGING_ISOLATION_PR_GREEN)

PR (ops/staging-isolation → main) 必须满足:

| # | 门 | 验证 |
|---|----|------|
| 1 | docs/STAGING_ISOLATION_SPEC.md 存在 | `test -f` |
| 2 | scripts/prepare-scf-staging.sh 存在 + 含 denylist check | `bash scripts/prepare-scf-staging.sh --preflight` |
| 3 | cloudbaserc.staging.json 存在 + 不含 production envId | `! grep njx-copilot-d6gs7642f8fa17122 cloudbaserc.staging.json` |
| 4 | cloudbaserc.production.json 存在 + 仅作 denylist reference | 文件头有 `isolated_for_staging_denylist_only: true` |
| 5 | .env.staging.example 存在 + 占位符无真凭据 | `grep -v xxx-STAGING-PLACEHOLDER .env.staging.example` 应空 |
| 6 | scripts/deploy-staging.sh 存在 + 含 denylist preflight | `bash scripts/deploy-staging.sh` (无 ALLOW_STAGING_DEPLOY 时) 应 exit 1 |
| 7 | staging-validation.yml 存在 + 含 denylist-check job | `grep denylist-check .github/workflows/staging-validation.yml` |
| 8 | tests/staging_isolation_test.py 存在 + 全部 PASS | `pytest tests/staging_isolation_test.py -v` |
| 9 | NO_PRODUCTION_RESOURCE_REFERENCE | 全部 staging 脚本 grep production 4 项 → 0 命中 |
| 10 | CI green (ops/staging-isolation push 触发) | staging-validation.yml 全 success |

10/10 PASS 后 → NJX 拍板 `OWNER_MAY_RECHARGE_AND_CREATE_SEPARATE_ENVIRONMENT` → 充值 → 部署 → 真实远端 10 旅程 + 8 RAG → 状态 PR

## 6. NJX 拍板后才可执行的动作

- 在 CloudBase 控制台创建 **staging 环境** (新 envId)
- 申请独立 staging `MINIMAX_API_KEY` 凭据
- 创建 `aog-staging.njx.com` sub-domain CNAME
- 创建独立 COS bucket `aog-staging-data-XXXXXXXX`
- 充值 staging env (PM 建议 ¥50-100 够跑 7 天测试)
- 跑 `bash scripts/deploy-staging.sh` (带 ALLOW_STAGING_DEPLOY=1)
- 提供 `AOG_STAGING_API_BASE` 给 PM 跑远程 RAG 回归

## 7. NJX 严令禁止 (再次强调)

- ❌ staging 脚本任何位置引用 `njx-copilot-d6gs7642f8fa17122` / `aog-api` / `aog-prod-data-1343051603` / `aog.njx.com`
- ❌ staging 部署到 production 函数 (`aog-api`)
- ❌ staging 数据写入 production COS bucket
- ❌ staging URL 用 `aog.njx.com` (必须 `aog-staging.njx.com`)
- ❌ staging 凭据复用 production `MINIMAX_API_KEY`
- ❌ staging 文档写 current head / 临时 CI run ID / 动态完成状态
- ❌ staging 准备直接 push main (必须独立 PR ops/staging-isolation → main)
- ❌ staging 验收未跑真实远端就用 in-process TestClient 替代
