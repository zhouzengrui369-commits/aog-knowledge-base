# AOG Knowledge Base - 待办事项

> 最后更新: 2026-07-29 14:30 GMT+8
> 优先级: P0 (Owner 7/29 授权) > P1 (产品体验评审 7/27 残余) > P2 (体验一致性) > P3 (非阻塞优化)
> 状态: 🔄 进行中 / ✅ 已完成 / ⏸️ 阻塞 (等 NJX 物理) / 📋 待评估

---

## 🔴 P0 - Owner 7/29 授权必关 (本 PR 范围)

| ID | 任务 | 状态 | 验证方式 |
|----|------|------|----------|
| P0-1 | 分支和版本收敛 — main / integration / staging 同 commit, 或锁 baseline | 🔄 | 本 PR push, gh pr create; merge 后 main = staging HEAD |
| P0-2 | API 修复 — 消除 double /api, 全栈 URL 规范唯一 | 🔄 | `curl ${BASE}/api/health` 返 200; browser fetch 验证 |
| P0-3 | RAG 维度与索引 — provider/model/dim 显式 + manifest + fail-closed | 🔄 | `select * from build_manifest` 返非空; 维度不匹配启动 fail-closed; 7 query 回归 ✅ |
| P0-4 | 真实 Provider + mock 边界 — production 禁 mock, UI 显著标识 | 🔄 | SCF 环境 ALLOW_MOCK=false 启动; chat endpoint 无 key 时返 503 + UI 显式 "Provider 未配置" |
| P0-5 | 数据可信度合同 — 9 字段 + 6 状态枚举 | 🔄 | `select count(*) from cities where review_status IS NULL` = 0; UI 显示来源/审核/置信度 |
| P0-6 | PII 与权限 — 个人手机号不公网裸露, contact role 分级 | 🔄 | grep `1[3-9]\d{9}` 在 frontend bundle = 0; public role 直展示, controlled/private 默认 REDACTED |
| P0-7 | staging 真实验收 — main+staging 同 commit + 10 项旅程 | ⏸️ 阻塞 | 等 NJX 充值 + 部署后跑 10 项旅程 |

---

## 🟡 P1 - 7/27 评审残余

| ID | 任务 | 状态 | 来源 |
|----|------|------|------|
| P1-1 | RAG 召回 city_contacts 数据 — D-030/031 已加, D-043 优化 | ✅ CLOSED | c883905, 80aed9e, D-043 |
| P1-2 | mock fallback UI 红框 | ✅ CLOSED | b963d94 (V14 P1-2) |
| P1-3 | 上海主基地 docx 补 — 上海浦东 / 虹桥 | ⏸️ 阻塞物理 | docx 录入 + build_index + SSG, 需 NJX 物理操作 (AOG知识库/ read-only) |
| P1-4 | 联系人 tab 5 航司重复 — 北京/哈尔滨 99% 相同 | 📋 待 P0-6 后 | docx 抽取 dedup |
| P1-5 | 84 城市 stock 全 0 — 备件 template | 📋 待 P0-5 后 | docx 抽取 dedup |
| P1-6 | warehouse 重复 5 次 (数据抽取 bug) | 📋 待 P0-5 后 | pipeline 修复 |
| P1-7 | AI references score 全 0.70 — 真实 RAG 排名 | ✅ PARTIALLY_FIXED | 7/27 评 Q1 0.60 0.80 0.80 |
| P1-8 | exp-001/exp-002 SSG 404 | 📋 待补 | SSG list 4 个, 后端 3 个, 删 1 个 |
| P1-9 | 暴露个人手机号 (李伟男/徐涛/石培) | 📋 待 P0-6 后 | P0-6 REDACTED 兜底 |
| P1-10 | SyncService 持续抛错 (5min ollama timeout) | ⏸️ SCF 禁用 SYNC | cloudbaserc SYNC_ENABLED=false |
| P1-11 | 课程 v2 何时发布 — AMBIGUOUS_SCOPE | 📋 待 NJX 拍 | owner decision |
| P1-12 | chroma 集合 dim=1024 vs chroma default=384 不匹配 (已废用) | 📋 清理 | P0-3 后删 chroma.sqlite3, 释放 87MB |

---

## 🟢 P2 - 体验一致性

| ID | 任务 | 优先级 |
|----|------|------|
| P2-1 | 数据来源标注 UI — "数据来源 + 最后更新" 显示在 city detail | P0-5 后 |
| P2-2 | 移动端 375×800 全旅程验收 | staging 后 |
| P2-3 | 字母 sidebar hover expand 优化 | non-blocking |
| P2-4 | 首页 5 秒理解强化 — "我是给航空维修值班员用的" | non-blocking |
| P2-5 | 经验页 SSG 重建 (exp-001/002 已 404) | P0-7 后 |

---

## ⚪ P3 - 非阻塞优化 (按 Owner 7/29 提示词: 不得抢先)

| ID | 任务 | 阻塞 |
|----|------|------|
| P3-1 | 地图标签密度微调 | Owner 禁 |
| P3-2 | 新地图组件重构 | Owner 禁 |
| P3-3 | 新城市批量灌入 | Owner 禁 |
| P3-4 | 新航司功能扩展 | Owner 禁 |
| P3-5 | 新视觉系统 | Owner 禁 |
| P3-6 | D-029 stub 清理历史 (PENDING 待审 docx) | 等 NJX 物理 cp |

---

## 🚧 NJX 物理待办 (本 PM 不能解决)

| ID | 任务 | 阻塞 |
|----|------|------|
| NJX-1 | 充值 CloudBase 账户 (`njx-copilot-d6gs7642f8fa17122`) | P0-7 |
| NJX-2 | PR merge 后 `tcb fn deploy` 重新部署 aog-api 函数 | P0-7 |
| NJX-3 | CloudBase 静态托管重新上传 frontend/out (V30 重新 SSG) | P0-7 |
| NJX-4 | 上海浦东/虹桥 docx 录入 (AOG知识库/02_外战预案/) | P1-3 |
| NJX-5 | 上海浦东/虹桥 物理 cp 到 build_index 源目录 | P1-3 |
| NJX-6 | 知识库 read-only 数据源 PENDING 状态 docx 物理 mv 到正式位置 | D-029 残余 |
| NJX-7 | AOG Co-pilot PRD v1.0 复审 (AOG知识库/05_项目立项/) | non-blocking |

---

## 📋 待评估 (AMBIGUOUS_SCOPE)

- 联系人 tab 敏感信息展示 (P0-6 后定 "公开" / "受控" / "私密" 边界)
- RAG 召回范围 (P0-3 后定 fts5 索引包含 wiki / city / city_contacts / experience / core_plan 5 种 source_type)
- "课件 v2" 何时发布 (5/项目立项/ 中有相关文档)

---
