# AOG Knowledge Base - 待办事项

> 最后更新: 2026-07-29 15:50 GMT+8
> 优先级: P0 (Owner 7/29 授权必关) > P1 (产品体验评审 7/27 残余) > P2 (体验一致性) > P3 (非阻塞优化)
> 状态: ✅ 已完成 / 🔄 进行中 / ⏸️ 阻塞 (等 NJX 物理) / 📋 待评估

---

## 🔴 P0 - Owner 7/29 授权必关 (本 PR 范围)

| ID | 任务 | 状态 | 验证证据 |
|----|------|------|----------|
| P0-1 | 分支和版本收敛 | ⏳ IN PROGRESS (待 NJX merge) | PR head `c290d75`, 59 commits ahead of main |
| P0-2 | API 修复 (消除 double /api) | ✅ CLOSED_LOCAL | f89e4cd + test_get_city_ok PASS |
| P0-3 | RAG 维度与索引 | ✅ CLOSED_LOCAL | 5cecf31 + 8/8 RAG 回归 PASS + fts5_index.db 9106 chunks manifest 校验 PASS |
| P0-4 | 真实 Provider + mock 边界 | ✅ CLOSED_LOCAL | ead11b2 + 581a5a89 (get_llm fail-closed 治本) + J6/J7 PASS |
| P0-5 | 数据可信度 10 字段 + 6 状态 | ✅ CLOSED_LOCAL | eef8b0e + 1c7c7a4 + 10/10 trust pipeline test PASS |
| P0-6 | PII 与权限 | ✅ CLOSED_LOCAL | 1c7c7a4 + 17/17 PII 4 层 negative test PASS + J8 PASS |
| P0-7 | staging 真实验收 | ⏸️ BLOCKED (物理) | 等 NJX 充值 CloudBase + merge PR + tcb fn deploy |

---

## 🟡 P1 - 7/27 评审残余 (本 PR 不在范围, 但已完成大部分)

| ID | 任务 | 状态 | 来源 |
|----|------|------|------|
| P1-1 | RAG 召回 city_contacts 数据 — D-030/031 已加, D-043 优化 | ✅ CLOSED | c883905, 80aed9e, e37afa5 |
| P1-2 | mock fallback UI 红框 | ✅ CLOSED | b963d94 (V14 P1-2) |
| P1-3 | 上海主基地 docx 补 — 上海浦东/虹桥 | ⏸️ 阻塞物理 | docx 录入 + build_index + SSG, 需 NJX 物理操作 (AOG知识库/ read-only) |
| P1-4 | 联系人 tab 5 航司重复 — 北京/哈尔滨 99% 相同 | 📋 待 P0-6 后 | docx 抽取 dedup |
| P1-5 | API 100 城市 401 — auth middleware 误命中 | ✅ CLOSED | (V14 时代已修) |

---

## 🟢 P2 - 体验一致性 (本 PR 不在范围)

| ID | 任务 | 状态 |
|----|------|------|
| P2-1 | 首页 hero 副标题弱 — "AI 知识库" 缺少价值主张 | 📋 待排期 |
| P2-2 | 移动端城市搜索未优化 — 字母抽屉不直观 | 📋 待排期 |
| P2-3 | 联系人 tab 标签未做权限可视化 | 📋 待 P0-6 后 |
| P2-4 | 错误页无品牌 | 📋 待排期 |
| P2-5 | 首页 API 健康检查日志缺失 | ✅ P0 阶段验证 (J1 PASS) |

---

## ⚪ P3 - 非阻塞优化

| ID | 任务 | 状态 |
|----|------|------|
| P3-1 | 地图标签密度 + 灰底融合 (V28 supercluster) | ✅ V28 已部署 (8333999) |
| P3-2 | wiki curator 质量 | 🟡 5 cities (V29) — 扩 50 cities 待评估 |
| P3-3 | mock 工具 | ✅ ALLOW_MOCK gate (P0-4) |

---

## 🚧 阻塞项 (NJX 物理)

| 项 | 状态 | 原因 |
|----|------|------|
| CloudBase 充值 | ⏸️ 阻塞 P0-7 | 公网 SCF `InsufficientBalance` 返 400 |
| 上海浦东/虹桥 docx 录入 | ⏸️ 阻塞 P1-3 | AOG知识库/02_外战预案/ 是 read-only 数据源 (D-029 教训) |
| PR merge | ⏸️ 阻塞 P0-1 | NJX review 后 squash merge |
| 独立产品体验复验 | ⏸️ 阻塞 P0-7 | 等 staging 部署完成 |

---

## 📋 完成门 (本 PR 13 项)

- [x] PR head 不落后 main (581a5a89 领先 59 commits)
- [x] 工作树 clean
- [x] 后端 compile/import 成功 (3 命令 exit 0)
- [x] 全部 CI green (117/117 tests PASS)
- [x] FTS5 manifest 真正写入 (9106 chunks, 58.3 MB, schema=v30-d038-d043)
- [x] 索引可重建 (export_fts5.py + rebuild 命令)
- [x] PII 不进入普通 RAG (test_pii_isolation.py 4 层)
- [x] pipeline 实际写入 trust fields (test_p05_trust_pipeline.py 10/10)
- [x] production frontend 不使用 mock (api-mock-isolation.test.ts 17/17)
- [x] SCF package 与 backend 同源 (prepare-scf.sh + drift check)
- [x] 8 条 RAG 回归通过 (test_rag_8query_regression.py 8/8)
- [x] 本地 10 项旅程通过 (test_journey_10_local.py 10/10)
- [x] PROJECT_STATE.yaml 12 字段 schema
- [x] 5 文档基线存在 + 更新到 7/29 状态
- [x] 无虚假 CLOSED (P0-1/P0-7 明确未 CLOSED)
- [x] 不需要 Owner 先执行充值或部署
