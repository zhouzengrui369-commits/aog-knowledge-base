# AOG Knowledge Base - 重要修改历史

> 详细 commit 列表: `git log --oneline`
> 详细决策: DECISIONS.md
> 当前状态: STATUS.md
> 待办: TODO.md

---

## V30 - LLM 结构化 JSON + chat 组件化 (2026-07-27)

- `9c29b89` **V30** feat(chat): 🅰️ LLM 结构化 JSON + 前端组件化 (治本 markdown 排版混乱)
- `e69427e` V29d++ fix(markdown): heading rule 1.5 允许 ### 无空白紧跟
- `e5f89b7` V29d+ fix(markdown): inline 表格重整算法 v5e
- `21b20c9` V29d fix(markdown): 视觉升级 + max_tokens 4000
- `5e4354a` docs(STATUS/DECISIONS): V29c trigram 治本 D-038 记录
- `80aed9e` **V29c** fix(RAG): D-038 trigram 治本 CJK 召回 (7 query 回归 ✅)
- `2c0c868` fix(markdown): 升级容错 (italic + auto newline 插 #/*/- 前)
- `eeff1d2` fix(chat): P0 修 chat() 非流式用 inline 3 段式 bug
- `7c715a3` docs(changelog): V29b 流式 + markdown + P1-1 wiki 段
- `51e1488` **V29b** feat(chat): 流式 SSE + markdown 渲染 + P1-1 接 wiki 段

## V29 - wiki_curator 双轨方案 MVP (2026-07-27)

- `dd89179` **V29** feat(wiki_curator): 🅰️ 双轨方案 MVP (3 城市) + chat widget panel 治本
- `d644ccb` fix(UI): AI panel z-index 1000 + 思考过程折叠
- `9a249df` fix(RAG + UI): D-030 治本 + AI widget 弹左不挡地图
- `a305ae1` docs(decision): D-032 S-上海虹桥 抽取 bug 调查

## V28b 时代 P0 修复 (2026-07-26)

- `90447f8` docs(focused-retest): DELIVERY 报告 (4/5 PASS + P0-2 BLOCKED)
- `c883905` fix(focused-retest): P0-1 上海主基地 + P0-3 contacts 权限 + P1-1 city_contacts RAG (D-030/031)
- `f04fc92` docs(STATUS): 12:18 实测 4 P0 验证 + 5 FOCUSED_RETEST 状态
- `9e305cb` fix(P0): PENDING check 需 decode URL-encoded code (D-029)
- `e56410d` fix(P0): 删 stub docx + UI S-上海浦东/虹桥 标'待补' (D-029)
- `b963d94` P1-2 (mock fallback 红框) + P1-3 (上海主基地) + P1-? (sentence-transformers)
- `8c90ba6` P0-1+P0-3 治本 (NJX 7/26 product review 反馈)
- `7a53723` docs(STATUS): 更新最近 commit (da8562c 5 文档 push 成功)
- `da8562c` docs: 建项目基线 5 文档 (STATUS / TODO / ARCHITECTURE / CHANGELOG / DECISIONS)
- `f86ab42` **V28b** fix(map): supercluster radius 50→80
- `8333999` **V28** feat(map): supercluster 数字聚合 218 AOG 城市 (zoom 5-7)

## V27 - 城市标签 218 蓝色常驻 (2026-07)

- `7d7dd6e` V27b fix(css): city-label 灰→蓝, 218 label 全部蓝色
- `c79dab1` V27 feat(map): 详细视图 (zoom>=5) 全部 218 AOG 城市常驻 label

## V25-V26 - 218 城市地图治本 (2026-07)

- `acb5239` V26 fix(map): 治本 218 AOG 城市看不见 (默认 zoom 5 + 改 hub 蓝 #2563eb + r 加大)
- `a600ab9` V25 feat(map): 航站 tab 隐藏航司 + panel 折叠 + 218 城市全可见
- `ed63729` V24 feat(map): 航司 tab 地图切换 (NJX 拍 B)

## V22-V23 - 数字徽章 / 推翻 (2026-07)

- `dadda3a` V23 feat(map): 推翻 V22 数字徽章, N=1 改显示实际内容
- `a521977` V22 feat(map): 推翻 V21 堆叠 tooltip, 改数字徽章 + flyTo + 右侧 panel

## V18-V21 - 本地优先 + 25 航司 + 地图重构 (2026-07-15~16)

- `9b0cd84` V21 feat(ui): 页面简化 — 字母 sidebar flex-wrap + tooltip 限 top 5 + panel top 6
- `139bd38` V20 feat(map): 全球 6500 机场 + AOG 218 两层 + 颜色区分 + 缩略图数字
- `d4c122f` V19 feat(mock): 完整 218 城市 MOCK (国内 144 + 国际 74 全坐标)
- `75c9ef5` V18 feat(local): V18 本地验证全流程 (25 航司 MOCK + DISABLE_AUTH + leaflet SSR fix)
- `80afe5b` V17 feat(map): 地图加航司 layer + dev backend 切公网 API
- `d882072` V16 feat(map): react-leaflet 嵌入主图 (替换 react-simple-maps 真实 OSM tile)

## V15 - 字母导航 (2026-07-15)

- `e218fac` V15.3 fix(airlines): backend 接受数字开头 IATA (3U/8L/9C/9D)
- `47077f8` V15.2 dev backend 返空数组时 fallback MOCK (避免 0 城市)
- `e893bac` V15.1 字母导航改为可切换 tab (航站 / 航司)
- `a017c57` V15 字母导航左右并排 3 列 (航站 220 + 航司 220 + 地图)
- `58637a3` Sprint C 本地优先 - 25 航司数据 + /api/airlines + UI tab
- `ac6d8f4` Sprint A 本地优先 - 密码 + JWT 24h token

## V14 - Wave 3 部署 (2026-07-15)

- `c32a4a4` feat(prod): Wave 3 部署完成 - 7 张公网截图 + WAVE3_NOTES.md
- `2e21deb` feat(frontend): Wave 3 - 静态化导出 + client-side 数据加载 (避开 SCF cold start)
- `0fb356e` feat(scf): Wave 3 真 E2E 通过 - FTS5 + MiniMax M3 + 真实文档引用
- `76cca2c` feat(scf): sync 5 backend runtime files (experiences 6MB fix + annotations)

---

## 7/29 P0 修复 (本 PR 范围, 实际 commit)

### P0 Stabilization 完成 (PR head `c290d75`, 7/29 15:50)
- `c290d75` test(stabilization): Stage 9.2/9.3 + P0-4 get_llm fail-closed 治本
  - P0-4 治本: get_llm() factory 之前只看 is_mock_llm, 不看 ALLOW_MOCK — 修
  - Stage 9.2: select_third_sample.py 5 维评分 (contacts/parts/warehouse/logistics/source_docx) — H-赫尔辛基 winner
  - Stage 9.3: 10 旅程本地验收 (test_journey_10_local.py 10/10 PASS)
  - P0-5 10 字段 + 5 cities fixture (B-北京大兴VERIFIED/B-包头STALE/H-赫尔辛基UNVERIFIED/S-上海浦东MISSING/S-上海虹桥MISSING)
- `2c64f35` test(stabilization): P0-3 RAG 8 query 回归 + D-043 短 CJK LIKE 占位符 + P0-7 chunks_count 真实表行数
  - 8 RAG 回归 case: 赫尔辛基/北京大兴/西安/三亚/米兰/南宁/雅典/前轮件号 3-1531
  - fts5_client D-043 修: CAST AS TEXT (doc_id INTEGER affinity) + 占位符顺序
  - export_fts5 P0-7 修: chunks_count 用真实表行数 (9106) 而非 _insert_chunks 数
- `5cecf31` fix(stabilization): P0-7 RAG manifest 增强校验 + GitHub CI 5 类检查
  - 4 项严格校验: db_size / APP_COMMIT_SHA / chunks_count / source_manifest_hash
  - schema_version 改精确等 (`v30-d038-d043`)
  - 9 项新测试 → 21/21 export_fts5 manifest test PASS
  - CI: backend/pipeline/frontend/scf/repository 5 jobs
- `bb75465` fix(stabilization): P0-4 frontend mock 隔离 + P0-7 SCF drift 检测
  - 17/17 vitest mock isolation test PASS
  - prepare-scf.sh: build + drift check + APP_COMMIT_SHA deploy command
- `1c7c7a4` fix(stabilization): P0-6 PII 隔离 + P0-5 数据可信度 pipeline 真写入
  - 17/17 PII 4 层 negative test PASS (RAG chunk / FTS5 / chat context / city API)
  - 10/10 P0-5 trust pipeline test PASS
- `108f890` fix(stabilization): main.py 连续 else 语法错 + export_fts5 manifest 参数绑定 + 12 项测试
  - 修 backend/aog_web/main.py line 118-119 两个连续 else:
  - 修 export_fts5.py SQL 绑定 (VALUES (1, ?×12) → (?×13))
  - 12 项新测试 (manifest + pipeline core + city model)

### 集成主线 (相对 main 80330dd, +59 commits / 98 files / +30496 / -869)
- `0bf770e` merge origin/main (no-op, 80330dd is ancestor)
- `bb3d9ec` feat(ui): P0-5 数据可信度 9 字段顶部组件 + P0-6 contact REDACTED 显示
- `eef8b0e` feat(data+pii): P0-5 9 字段 + P0-6 contact REDACTED
- `ead11b2` feat(config): P0-4 mock 隔离 (ALLOW_MOCK + STRICT_LLM, production 禁 mock)
- `29e6a19` feat(rag): P0-3 build_manifest 写入 + 启动 fail-closed 校验
- `f89e4cd` fix(api): P0-2 消除 double /api 400 (base 不带尾, path /api/...)
- `e37afa5` fix(RAG): D-043 召回错城市治本 (NJX 7/28 反馈 雅典/南宁召错)

---
