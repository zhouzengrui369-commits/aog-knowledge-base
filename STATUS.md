# AOG Knowledge Base - 当前状态

> 最后更新: 2026-07-29 14:30 GMT+8 (Mavis PM)
> 评审对象: review/aog-product-experience-baseline `5d39967` (V28b, 7/27)
> 真正主线: integration/sprint-abc `9c29b89` (V30, 7/27)
> 目标主线: p0/integration-main-convergence (本 PR, 2026-07-29)

---

## 1. 当前阶段

**P0 全面修复收敛** — 按 Owner 2026-07-29 授权提示词, 把项目从"设计完整但数据和 AI 不可信的演示产品"推进到"代码主线统一、技术 P0 清零、样板数据可核验、staging 可真实操作"。

| 阶段 | 状态 | 关键交付 |
|------|------|----------|
| 阶段 0: 工程真相 | 🔄 进行中 | 4 套版本对照 + 5 文档基线 + PROJECT_STATE.yaml |
| 阶段 1: API 修复 | 🔄 进行中 | P0-2 /api 规范 |
| 阶段 2: RAG 维度 | 🔄 进行中 | P0-3 manifest + fail-closed |
| 阶段 3: Provider 边界 | 🔄 进行中 | P0-4 mock 隔离 |
| 阶段 4: 数据可信度 | 🔄 进行中 | P0-5 9 字段合同 |
| 阶段 5: 三个样板 | 📋 待评估 | 北京大兴 (现) / 上海浦东 (待补) / 第三个外站 (待选) |
| 阶段 6: staging 验收 | 🚧 物理阻塞 | 等 NJX 充值 CloudBase + 部署 |
| 阶段 7: PR + 评审 | 📋 本 PR 完成 | gh pr create + 通知评审官 |

---

## 2. 已完成 (历史能力)

- V14 时代 Wave 3 部署: `80330dd` (main HEAD, 但已过时)
- 5 文档基线安装: da8562c (aog-web/STATUS.md + TODO.md + ARCHITECTURE.md + CHANGELOG.md + DECISIONS.md, 但**当前 review baseline 没装**)
- 5 P0 在 V28b 7/27 评审关闭: RAG 维度 (改 fts5) / AI chat live (MiniMax M3) / 数据 fresh (2026-07-27 SSG) / main 落后 integration (评审用 integration HEAD) / mock fallback UI 红框
- V29c D-038 trigram 治本: 80aed9e (7/27 20:26) 解决 CJK 召回 0 命中, 实测 7 query 回归 ✅
- V29b 流式 SSE + markdown 渲染: 51e1488
- V29 wiki_curator 🅰️ 双轨 MVP: dd89179 (3 城市)
- V28 supercluster 数字聚合: 8333999 (zoom 5-7 治本标签重叠)
- V18 引入 view_count: 推荐排序有意义
- V19 完整 218 城市 MOCK: d4c122f (D-029 后 stub 隔离)

---

## 3. 进行中 (本 PR)

- **D-043 召回错城市治本** (NJX 7/28 反馈 "雅典/南宁 召错城市"): fts5_client.py + chat.py 改 5 段式召数 + 通用词表黑名单 + specificity 排序 (现 uncommitted, 本 PR commit)
- **P0-2 API base 规范**: frontend `.env.local` 已带 `/api` 后缀, 修法: 去掉后缀, path 保持 `/api/...` (选 A 规范: base 不带尾, endpoint 加)
- **P0-3 RAG 维度 + manifest**: export_fts5.py 写 build_manifest 表 (tokenizer / build_commit / build_time / source_manifest_hash / chunk_count / db_size_bytes), 启动时校验, 不一致 fail-closed
- **P0-4 mock 隔离**: config 加 `ALLOW_MOCK` 字段, dev 默认 true, production (SCF) 默认 false; frontend .env 加 `NEXT_PUBLIC_ALLOW_MOCK` 同步
- **P0-5 数据可信度合同**: City + Experience model 加 9 字段 (source_document, source_location, source_version, updated_at, reviewed_at, reviewed_by, review_status, confidence, environment, pii_classification) + 6 状态枚举 (VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED); DB migration 加列; pipeline 写入
- **P0-6 PII**: Contact 加 `role_class` 字段 (public/controlled/private) + `redacted` boolean, 缺真值时 REDACTED 兜底, 前端 UI 加"受控/内部"标签 + 不展示 private 字段

---

## 4. 下一步 (PR merge 后)

1. NJX 充值 CloudBase 账户 (`njx-copilot-d6gs7642f8fa17122`) — 解锁 SCF 函数
2. NJX 物理 OAuth + `tcb fn deploy` 重新部署 aog-api
3. NJX 上传 frontend/out (V30 重新 SSG) 到 CloudBase 静态托管
4. PM 自动跑 E2E 验收 (10 项旅程)
5. PM 通知独立产品体验评审官线程, 走 FOCUSED_RETEST 模式重新盲测
6. 评审官基于新 staging commit 输出报告, Owner 走 Human Gate

---

## 5. 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 公网 SCF InsufficientBalance | 🔴 HIGH | 阻塞 P0-7, 必须 NJX 充值 |
| chroma 集合 dim=1024 vs chroma default ONNX mini-L6=384 dim 不匹配 | 🟡 MEDIUM | V28b 切 fts5 绕开; chroma 集合可清理 (memory 数据备份到 /tmp 后删除) |
| fts5_index.db 旧 (7/17) | 🟡 MEDIUM | D-043 改 fts5_client 后必须 rebuild + verify 7 query |
| AOG知识库/ read-only 数据源被 P0-1 ~ P0-7 误改 | 🔴 HIGH | 严守 7/27 D-029 教训, 所有数据走 staging / NJX 物理 cp; PM 不写源 |
| 5 文档基线缺失 | 🟡 MEDIUM | 本 PR 重建, 根目录 + aog-web/ 双层 |
| SyncService 持续抛错 (7/27 评 P0-6 残余) | 🟡 MEDIUM | SCF 部署 SYNC_ENABLED=false (cloudbaserc 已配), dev 本地仍 5min 跑, 单次失败不挂 (logger.exception) |
| 个人手机号 PII 裸露 | 🟡 MEDIUM | 本 PR P0-6 加 role_class + REDACTED; 旧 contacts 字段待审 (北京/哈尔滨仍同模板) |
| 上海浦东 docx 缺失 | 🟡 MEDIUM | P0-5 加 MISSING 状态后 UI 显示"暂无已核验数据"而不是 404 |

---

## 6. 最近 commit / 分支

| 类型 | ref | label |
|------|------|------|
| main HEAD | `80330dd` | V14 (7/15) |
| integration HEAD | `9c29b89` | V30 (7/27 23:xx) |
| review HEAD | `5d39967` | V28b 评审基线 (7/27) |
| **本 PR base** | `origin/integration/sprint-abc` | V30 |
| **本 PR target** | `origin/main` | V14 (待 merge) |
| **staging 远端** | **不存在** | 需创建 |

---

## 7. 文档归位 (跨项目规则)

- AOG 项目 docs: 本仓库根目录 (STATUS.md / PROJECT_STATE.yaml / TODO.md / docs/ARCHITECTURE.md / CHANGELOG.md / DECISIONS.md) + aog-web/STATUS.md (镜像)
- 原始数据: `/Users/njx/Project/AOG知识库/AOG知识库/` (read-only, PM 绝对不能写)
- 原始导出: `/Users/njx/Project/AOG知识库/RAW/` (read-only)
- NJX 知识库整理: `/Volumes/南极熊/03知行合一/opc/` (NAS, 必须 `cp -X` 去 macOS metadata)

---

## 8. 反向检查 (NJX 立的基线规则 7/26)

> "如果我现在把 session 关掉, 一个新 AI 接手能在 10 分钟内继续吗?"

✅ PROJECT_STATE.yaml (7.1KB) 锁定版本真相
✅ STATUS.md (本文件) 锁定阶段/目标/风险
✅ TODO.md (下一文件) 锁定待办优先级
✅ docs/ARCHITECTURE.md (下一文件) 锁定系统架构
✅ CHANGELOG.md (下一文件) 锁定修改历史
✅ DECISIONS.md (下一文件) 锁定重大决策
✅ aog-web/STATUS.md 等 5 文档 (子目录镜像)
✅ README.md (V14 时代) 需更新到 V30 真相

---
