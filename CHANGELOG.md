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

## 7/29 P0 修复 (本 PR 范围, 计划)

- `pending` feat(docs): 重建 5 基线文档 (根目录) + 同步 aog-web/
- `pending` fix(api): P0-2 API base 规范 (frontend .env.local 去尾 /api)
- `pending` feat(rag): P0-3 fts5_index build_manifest (tokenizer/build_commit/source_manifest)
- `pending` feat(config): P0-4 ALLOW_MOCK 隔离 (dev true / SCF false)
- `pending` feat(data): P0-5 9 字段数据可信度合同 (City/Experience model + DB + UI)
- `pending` feat(pii): P0-6 contact role_class + REDACTED
- `pending` feat(rag): D-043 召回错城市治本 (NJX 7/28 反馈, 已 uncommitted)

---
