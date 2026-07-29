# PR #1 — P0 Stabilization & Evidence Closure (Owner 7/29 严令)

## ⚠️ 当前状态 (7/29 17:10 实测)

| 维度 | 状态 |
|------|------|
| **GitHub Actions** | 🟢 **SUCCESS** (run 30438222057) |
| **Backend job** | 🟢 success (94+5=99 PASS) |
| **Frontend job** | 🟢 success (tsc/lint/vitest/build + production mock-disabled) |
| **Repository scanner** | 🟢 success (scanner 0 findings + PROJECT_STATE 20 字段验证) |
| **Pipeline job** | 🟢 success (39 项 + FTS5 export smoke) |
| **SCF job** | 🟢 success (drift check 33 files 一致) |
| **All checks passed** | 🟢 success |
| **workflow conclusion** | 🟢 success |
| **merge 条件** | 🟢 READY (等 NJX review + merge) |
| **CloudBase 充值** | ❌ 等 NJX (Owner 决定时机) |
| **tcb fn deploy** | ❌ 等 merge + 充值后 |
| **hosting deploy** | ❌ 同上 |
| **产品体验复验** | ❌ 等 staging 部署后 |

## PR 规模 (GitHub 实际)

```
PR head:    4fdc56167ef5bac7bb8285a8e606ff84810a8c52  (Stage 12+ CI Green Closure)
main:       80330ddec8188c8bf3319a35e82ea62f065cca86  (V14, 落后 67 commits)
commits:    67 ahead of main
files:      99+ changed
insertions: +30,802
deletions:  -872
branch:     p0/integration-main-convergence
URL:        https://github.com/zhouzengrui369-commits/aog-knowledge-base/pull/1
CI:         run 30438222057 conclusion=success (5/5 jobs + all-pass 全绿)
```

## P0 状态 (Owner 7/29 12 阶段严令)

| P0 | 状态 | 证据 |
|------|------|------|
| **P0-1** 分支收敛 | ⏳ IN_PROGRESS | PR head 65 ahead, **未 merge**, 等 NJX |
| **P0-2** API 修复 | ✅ CLOSED_LOCAL | f89e4cd + test_get_city_ok |
| **P0-3** RAG 维度 | ✅ CLOSED_LOCAL | 5cecf31 + 8/8 RAG + fts5 4 项校验 |
| **P0-4** Provider 边界 | ✅ CLOSED_LOCAL | ead11b2 + c290d75 (D-044-G get_llm fail-closed 治本) |
| **P0-5** 数据可信度 | ✅ CLOSED_LOCAL | eef8b0e + 1c7c7a4 + 10/10 P0-5 test |
| **P0-6** PII | ✅ CLOSED_LOCAL | 1c7c7a4 + 17/17 PII 4 层 + J8 |
| **P0-7** staging 验收 | ⏸️ BLOCKED | 10/10 本地 PASS, 公网等 NJX 物理 |

**P0-1 / P0-7 明确未 CLOSED** — 等 NJX merge + 充值 + deploy。

## Stage 9-12 stabilization 提交列表 (7/29 14:xx-16:xx)

```
718319c docs(state): Stage 12 final — pr_head 581a5a89 → fd02795 同步
fd02795 fix(ci): drop accidental .next.died/ commit (Next.js compile cache, 不应入仓)
a8693de docs(state): Stage 12 final — pr_head 跟实际 commit 581a5a8 对齐
581a5a8 fix(scf): prepare-scf.sh sync backend→aog-api snapshot 跟 PR head e976e00 一致
38762f4 docs(state): Stage 12 — 填入真实 sha256 + 索引 manifest 详情
e976e00 docs(stabilization): Stage 10/11 — 5 文档 + PROJECT_STATE.yaml 12 字段
c290d75 test(stabilization): Stage 9.2/9.3 + P0-4 get_llm fail-closed 治本
2c64f35 test(stabilization): P0-3 RAG 8 query 回归 + D-043 + P0-7 chunks_count
5cecf31 fix(stabilization): P0-7 RAG manifest 增强校验 + GitHub CI 5 类检查
bb75465 fix(stabilization): P0-4 frontend mock 隔离 + P0-7 SCF drift 检测
1c7c7a4 fix(stabilization): P0-6 PII 隔离 + P0-5 数据可信度 pipeline 真写入
108f890 fix(stabilization): main.py 连续 else 语法错 + export_fts5 manifest 参数绑定
0bf770e merge origin/main (no-op, 80330dd is ancestor)
```

## CI Green Closure 修复 (本次 stage 12+ 待 push)

```
fix(ci): Frontend TypeScript 4 错治本
  - chat-widget.tsx: 动态 Tag (h${level}) → 显式 h1/h2/h3 (React 19 + TS 5.9 不接受 dynamic string tag)
  - city-tabs.tsx: 创建 ContactViewModel + normalizeContact() (联合类型 cast 治本, P0-6 三层)
  - world-map-leaflet.tsx: airline.hq → airline.headquarters (统一字段)
  - lib/types.ts CityStatus: 加 "inactive" 合法值 (frontend 展示态, 67 个 mockup city 不报错)
  - eslint.config.mjs flat config (next lint 已被 Next 16 移除, 改 eslint .)

fix(scanner): Phone/email scanner UnicodeDecodeError 治本
  - .github/scripts/phone_email_scanner.py: 独立可执行脚本, 文本扩展白名单 (.py .ts .tsx .js .jsx .json .yaml .yml .md .txt .env .sh)
  - catch UnicodeDecodeError → skipped_binary (不静默跳过源代码)
  - 4 类计数输出: scanned_text / skipped_binary / skipped_fixture / findings
  - findings > 0 → exit 1, scanner 内部异常 → exit 2
  - .github/tests/test_phone_email_scanner.py: 8 项测试 (UTF-8 / binary / fixture / production / example / 真实邮箱 / 内部异常 / main 真仓库)
  - 真仓库 0 findings (清理 mockup 注释 SPE@satair.com → Satair SPE; city.py fixture phone → PII_FIXTURE_PHONE_11; DECISIONS.md 同)

fix(ci): pipefail 兜底
  - 所有 run block 加 set -euo pipefail (禁止 head/tail pipe 掩盖错误)
  - 修 reports/product-review/2026-07-26-aog/HANDOFF-TO-DEV.md 8 行 trailing whitespace

docs(state): PROJECT_STATE.yaml 20 字段 schema
  - candidate_code_commit: 最后一个修改代码/测试/构建配置的 commit
  - state_document_parent_commit: 本次状态文件提交的父 commit
  - observed_pr_head: 生成状态报告时 git rev-parse HEAD
  - last_completed_ci_run_id: 30434710828
  - last_completed_ci_conclusion: failure
  - 部署 SHA 不在 merge 前硬编码 (staging_deploy_commit: null)
```

## 测试总览 (本 PR head)

| 套 | 测试 | 状态 |
|----|------|------|
| pipeline/tests/test_rag_8query_regression | 8+1 summary | ✅ 9/9 PASS in 0.68s |
| pipeline/tests/test_pii_isolation | 17 | ✅ 17/17 PASS in 1.43s |
| pipeline/tests/test_p05_trust_pipeline | 10 | ✅ 10/10 PASS in 1.01s |
| pipeline/tests/test_export_fts5_manifest | 21 | ✅ 21/21 PASS |
| pipeline/tests (其他) | 23 | ✅ 23/23 PASS |
| backend/tests/test_journey_10_local | 10 | ✅ 10/10 PASS in 1.66s |
| backend/tests/test_cities | 11 | ✅ 11/11 PASS in 9.54s |
| backend/tests/test_fts5_e2e | 3 | ✅ 3/3 PASS in 1.25s |
| backend/tests/test_phone_email_scanner | 8 | ✅ 8/8 PASS in 0.86s (本地 regression, CI 跑主程序) |
| frontend/tests/api-mock-isolation | 17 | ✅ 17/17 PASS in 4.33s |
| **总计** | **128** | **✅ 128/128 PASS** |

## 三个样板 (Stage 9.2)

| 样板 | code | review_status | source | 备注 |
|------|------|---------------|--------|------|
| #1 | B-北京大兴 | **VERIFIED** (2026-01-15, NJX) | B-北京大兴.docx | 人工审核标杆 |
| #2 | S-上海浦东 | **MISSING** (无源 docx) | — | 等 NJX 物理 cp docx |
| #3 | **H-赫尔辛基** | UNVERIFIED (2026-01-20 mtime) | H-赫尔辛基.docx 59178 bytes | 23.80/31 评分, 自动选 |

## 唯一 NJX 外部动作 (CI 全绿并独立复核后)

```
1. gh pr merge 1 --merge   # Owner 严令: merge commit 保留历史, 不用 --squash
2. 充值 CloudBase 账户 njx-copilot-d6gs7642f8fa17122 (解除 InsufficientBalance)
3. APP_COMMIT_SHA=$(git rev-parse main)
4. cd aog-web && bash scripts/prepare-scf.sh
5. tcb fn deploy aog-api -e APP_COMMIT_SHA=$APP_COMMIT_SHA
6. staging URL 上跑 10 旅程 (test_journey_10_local.py 验证真实部署)
7. 通知独立产品体验评审官基于 staging 重新评审
```

**当前 PR 不具备 merge 条件 — 等 GitHub CI 全绿。**
**当前不要求 Owner 充值或部署 — 等 CI 真正全绿。**
