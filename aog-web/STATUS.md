# AOG 项目状态 (Project Status)

> **目的**: 让任何新 AI 只看 README + STATUS + TODO + docs 目录就能 10 分钟内理解项目并继续开发。
> **维护**: 每完成一个功能 / 阶段必更新本文件。
> **最后更新**: 2026-07-27 20:18 by Mavis (PM)

---

## 🎯 当前阶段

**Phase 1.5 · V30 治本完成 (LLM 结构化 JSON + 组件化渲染)**

- **里程碑**: V30 治本完成 — LLM 输出 `===JSON_START===...===JSON_END===` 段, 后端解析成 18 sections, 前端用 8 组件渲染 (heading/paragraph/table/list/ordered_list/code/alert/quote)
- **下一里程碑**: 公网 SCF 重新部署 V30 + DECISIONS D-042 落地

---

## 📍 当前目标

让 NJX（OPC 独立创业）能够：

1. **本地浏览器硬刷 http://localhost:3004/** → 看到 V28b 治本后的地图（218 蓝点 + 数字 bubble + 6,072 灰点）
2. **点击紫色数字 bubble** → 自动 flyTo + zoom in 展开
3. **AI panel 提问** → V30 治本: 流式 markdown 打字机 → sections event 到达后切到结构化组件化 (heading 色块 / 表格 / 列表 蓝圆点 / alert 4 变体)
4. **公网部署更新** → 含 V13-V30 全部新功能

---

## ✅ 已完成 (Recent Shipped)

| 版本 | 日期 | 内容 |
|---|---|---|
| **V30** | 2026-07-27 | 🅰️ 治本: LLM 输出结构化 JSON (`===JSON_START===`...`===JSON_END===` sentinel) + 后端 _parse_sections 解析 + 前端 8 组件化渲染 (HeadingSection/ParagraphSection/TableSection/ListSection/OrderedListSection/CodeSection/AlertSection/QuoteSection) (NJX 22:14 拍板 🅰️, 治本 LLM 输出 markdown 不稳定根因) |
| **V29d** | 2026-07-27 | 视觉升级: max_tokens 1024→4000 (治本 LLM 截断) + normalize v3 (heading 允许紧贴) + renderMarkdown 视觉升级 (h1/h2 色块 + table 边框 + list 圆点) (NJX 20:34 反馈"AI 输出依然不便于阅读"根因) |
| **V29c** | 2026-07-27 | D-038 trigram 治本 CJK 召回: 3 张 FTS5 表改 trigram tokenizer + 应用层 3-gram + 短 CJK LIKE fallback (NJX 19:55 反馈"未找到赫尔辛基预案"根因) |
| **V29b** | 2026-07-27 | 流式 SSE + 自写 markdown 渲染 + P1-1 chat 5 段式 (wiki > city > contacts > experience > core_plan) |
| **V29** | 2026-07-27 | 🅰️ 双轨方案: RAG (D-030 治本) + LLM wiki 整理 (3 城市 MVP) + chat widget panel 治本 + 思考过程鲁棒折叠 |
| V28b | 2026-07-24 | supercluster radius 50→80 (治本 "5.0 还是有点挤") |
| **V28** | 2026-07-24 | supercluster 数字聚合 218 AOG (zoom 5-7 治本标签重叠) |
| **V27b** | 2026-07-24 | city-label 灰→蓝 (218 label 全部蓝色) |
| **V27** | 2026-07-24 | 详细视图 zoom≥5 全部 218 城市常驻 label |
| **V26** | 2026-07-24 | 治本 218 城市看不见 (默认 zoom 5 + 改 hub 蓝 #2563eb + r 加大) |
| V25 | 2026-07-23 | 航站 tab 隐藏航司 + 全球 panel 折叠 + 218 城市全可见 |
| V24 | 2026-07-23 | 航司 tab 地图切换 (NJX 拍 🅱️) |
| V23 | 2026-07-23 | N=1 显示实际内容 (推翻 V22 数字 "1") |
| V22 | 2026-07-23 | 数字徽章 + flyTo + 右侧 panel (NJX 拍 🅱️) |
| V21 | 2026-07-23 | UI 简化 (字母 sidebar + tooltip 限 5 + panel top 6) |
| V20 | 2026-07-22 | OpenFlights 6,072 全球机场 + 颜色区分 |
| V19 | 2026-07-22 | 完整 218 城市 MOCK (国内 144 + 国际 74) |
| V18 | 2026-07-22 | 本地验证全流程 (25 航司 MOCK + DISABLE_AUTH) |
| V17 | 2026-07-21 | 地图加航司 layer (紫环) |
| V16 | 2026-07-21 | react-leaflet 嵌入主图 (替换 react-simple-maps) |
| V15.3 | 2026-07-20 | backend 接受数字开头 IATA (3U/8L/9C/9D) |
| V15.2 | 2026-07-20 | dev backend 返空数组时 fallback MOCK |
| V15.1 | 2026-07-20 | 字母导航改为 tab 切换 (推翻 V15 2 个并列) |
| V15 | 2026-07-20 | 字母导航左右并排 3 列 (已废) |
| V14 | 2026-07-17 | 地图 click 直跳 uppercase URL + client render 防御性 |
| V13 | 2026-07-17 | postbuild rename URL-encoded city files to Chinese names |
| Sprint A | 2026-07-15 | 密码 + JWT 24h + AuthGate |
| Sprint B | 2026-07-15 | react-leaflet 调研 + prototype |
| Sprint C | 2026-07-15 | 25 航司数据 + /api/airlines + UI tab |
| V11 | 2026-07-14 | hub label density + 中文 city code 兼容 |
| V8-V12 | 2026-07-13~14 | 城市详情 / 智能 404 / UI polish |

---

## 🔄 正在进行 (In Progress)

- **V30 公网 deploy**: SCF 重新部署含 V30 sections 解析 + 组件化渲染 (等 NJX 续费 CloudBase)
- **V30 wiki 同步**: wiki_curator 改用 JSON sections 输出 (V30 兼容)
- **V30 回归测试**: minimax M3 JSON 模板遵循率 (3/3 query emit, 待扩量验证)

---

## ⏭️ 下一步 (Next Steps)

### 🔴 高优先级（NJX 拍板后可立刻做）

1. **公网 SCF 重新部署**（含 V13-V28b 全部新功能）
   - 公网 SCF `76cca2c` (Jul 17) 仍跑老版本，缺 `/api/airlines` + `/api/auth/login`
   - 需拉最新 backend code + 重新部署 SCF 函数
   - 风险: CloudBase 静态托管 CDN 缓存可能滞后（之前用 tcb CLI 3.6.2 无 invalidate/purge/refresh）

2. **合并 integration/sprint-abc → main + 部署前端**
   - V25-V28b 16 个新 commit 在 integration/sprint-abc 分支
   - 公网前端仍是 Jul 17 老版本
   - 风险: GitHub push SSL 偶发超时（已确认 8333999 / 7d7dd6e / c79dab1 push 成功）

### 🟡 中优先级（NJX 拍板后做）

3. **Vite error overlay 治本**（升级 react-leaflet v5）
   - 当前 workaround: dev 死掉时 `nohup pnpm dev --port 3004 > /tmp/aog_v28b_dev.log 2>&1 &` 重启
   - 治本: 升级 react-leaflet v5（内部用 React 18 createRoot 解决 strict mode）
   - 风险: 工作量大，可能引入新 bug

4. **AOG 微信小程序备案**
   - 域名 aog.knowledge.com 待 ICP 备案
   - 微信小程序类目选择 + 主体选择（个人 vs 企业）
   - 风险: NJX 0 CloudBase / 备案经验，PM 全权负责

### 🟢 低优先级（V29+ 阶段）

5. **OpenClaw 知识库整理自动化**（项目外）
6. **V29 UI polish**: supercluster bubble 颜色 / hub vs 普通视觉差异
7. **V30+ 性能优化**: 视口外 city dot 不渲染（leaflet 内置优化）

---

## ⚠️ 当前风险 (Active Risks)

| 风险 | 等级 | 详情 | 缓解 |
|---|---|---|---|
| **🔴 P0 事故 (D-029)** | **高** | **PM 7/26 16:45 误写 stub docx 到 read-only AOG知识库/，build_index 吃进假数据** | **7/27 08:19 mavis-trash stub + UI PENDING_CITY_CODES 标"待补" + DECISIONS D-029 + rebuild index 225→223 城市** |
| 公网 SCF InsufficientBalance | 🔴 高 | NJX 续费日 2026-07-24 23:59:59 已过，公网后端 + 前端全挂 | NJX 续费 → PM 重 deploy；本地 dev 优先走通 P0/P1 |
| 公网 SCF 老版本 | 🟡 中 | `76cca2c` (Jul 17) 缺 V15-V28b endpoint | 拉最新 backend code + 重新部署 |
| GitHub push SSL 偶发超时 | 🟡 中 | 之前 8333999 / 7d7dd6e / c79dab1 push 失败 1-3 次才成功 | sleep 30-90s 重试 |
| Vite error overlay (dev) | 🟡 中 | Next.js 15 + React 19 + leaflet 已知问题，dev only | 重启 dev 15s 恢复；production OK |
| CloudBase 静态托管 CDN 缓存 | 🟡 中 | tcb CLI 3.6.2 无 invalidate/purge/refresh | 等 10 分钟自然过期或文件名加 hash |
| macOS TCC EPERM (LaunchAgent) | 🟢 低 | 当前不用 LaunchAgent，无影响 | 1 天 MVP 别碰 LaunchAgent + 写盘 |
| worker lost 概率 | 🟢 低 | bg_xxx status=lost，需要 PM 手动接管收口 | 任务拆小，重要 commit 自己来 |

---

## 📦 最近一次重要修改

### 最近代码 (V30)
- **Commit**: (pending, 5 modified)
- **分支**: `integration/sprint-abc`
- **标题**: V30 feat(chat): 🅰️ LLM 结构化 JSON + 前端组件化 (治本 markdown 排版混乱)
- **内容**:
  - `backend/aog_web/api/chat.py` — SYSTEM_PROMPT 加 JSON 输出模板 + _parse_sections() 解析器 + chat() 返 sections + chat_stream() emit event=sections
  - `backend/aog_web/models/chat.py` — ChatSectionType Literal + ChatSection model + ChatResponse.sections 字段
  - `frontend/lib/types.ts` — ChatSection interface + ChatResponse.sections? + ChatStreamCallbacks.onSections
  - `frontend/lib/api.ts` — chatStream SSE 解析 event=sections 回调
  - `frontend/components/chat-widget.tsx` — 8 组件 (HeadingSection/ParagraphSection/TableSection/ListSection/OrderedListSection/CodeSection/AlertSection/QuoteSection) + SectionRenderer/renderSections + formatAnswer sections 优先 / markdown fallback + cleanText
- **效果**:
  - 18 sections per query (heading 7 / table 2 / list 4 / ordered_list 1 / paragraph 2 / alert 1 / quote 1)
  - 8 type 全部组件化渲染, 0 markdown 解析依赖
  - 流式打字机 (token 阶段) → sections event 触发后切到结构化
  - 5 张 Playwright 截图 (`/tmp/aog_v30_final_20260727/`)
- **本地 verify**: 3/3 query emit sections event, DOM 渲染 h1=1, h2=3-7, h3=1-3, lis=12-19, alerts=1-2, quotes=1, thinks=0

### 最近代码 (V29d)
- **Commit**: `21b20c9` (push 成功)
- **分支**: `integration/sprint-abc`
- **标题**: V29 feat(wiki_curator): 🅰️ 双轨方案 MVP (3 城市) + chat widget panel 治本
- **内容**:
  - `pipeline/scripts/wiki_curator.py` (新, 12KB) — LLM 整理 docx → MOC wiki 页 + 交叉链接 + NSM-2 引用段
  - `frontend/components/chat-widget.tsx` — panel z-index 1100 + messages bg-slate-50 不透明 + formatAnswer 鲁棒 think 解析 (think/thinking/reasoning/THINK 多格式)
  - `backend/aog_web/llm/minimax.py` — httpx.Timeout 30s → 120s (wiki max_tokens 12000 兼容)
- **效果**:
  - 3 wiki 页生成 (B-北京大兴 2594 / S-三亚 2309 / X-西安 2535 chars) 含 ⚠️ 风险标注 + 互援 [[code]] 交叉链接
  - chat panel 完全不透明覆盖 home 地图
  - <think> 思考过程默认折叠为 💭 AI 思考过程 (点击展开)
- **本地 verify**: 7 Playwright 截图 (`/tmp/aog_widget_fix_20260727/0{1..7}_*.png`)

### 最近代码 (V28b)
- **Commit**: `f86ab42`
- **分支**: `integration/sprint-abc` (待 merge → main)
- **标题**: V28b fix(map): supercluster radius 50→80 (治本 "5.0 还是有点挤")
- **内容**: 1 行改 (`world-map-leaflet.tsx` supercluster radius 50→80)
- **效果**: zoom 5 单点 label 156→90 (-42%)，数字 bubble 28→53 (+89%)，拥挤治本

### 最近代码 (P0 修复 D-029, 进行中)
- **Commit**: (pending, rebuild index 跑中)
- **分支**: `integration/sprint-abc`
- **标题**: fix(P0): 删 stub docx + UI S-上海浦东/虹桥 标"待补" (D-029 事故)
- **内容**: mavis-trash S-上海浦东/虹桥.docx + city-detail-client.tsx PENDING_CITY_CODES set + DECISIONS.md D-029
- **效果**: 225→223 城市, S-上海浦东/虹桥 入口"预案待补"红字提示, 等 NJX 补真 docx

### 最近文档 (本批基线 5 文档)
- **Commit**: `da8562c` (HEAD)
- **标题**: docs: 建项目基线 5 文档 (STATUS / TODO / ARCHITECTURE / CHANGELOG / DECISIONS)
- **内容**: 5 个新 md 文件, 1236 行, 含 V13-V28b 全部状态快照 + 28 条决策 + 架构说明
- **意义**: 任何新 AI 接手 10 分钟内能继续开发

### Push 状态
- ✓ GitHub `zhouzengrui369-commits/aog-knowledge-base` integration/sprint-abc
- 全部 5 文档已 push 成功 (commit `da8562c`)

---

## 🔗 关键链接 (Important Links)

- **GitHub**: https://github.com/zhouzengrui369-commits/aog-knowledge-base
- **公网前端 (老)**: https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com
- **公网 API (老)**: https://njx-copilot-d6gs7642f8fa17122.service.tcloudbase.com/api
- **本地前端**: http://localhost:3004/ (dev 跑, V28b 治本)
- **本地后端**: http://localhost:8000/ (uvicorn, DISABLE_AUTH=1)
- **本地 swagger**: http://localhost:8000/docs

---

## 📂 文档索引 (Documentation Index)

| 文档 | 用途 | 维护频率 |
|---|---|---|
| [README.md](./README.md) | 项目入口 + 部署链接 | 大版本变更 |
| [STATUS.md](./STATUS.md) | **本文件** - 当前状态快照 | 每功能/阶段必更新 |
| [TODO.md](./TODO.md) | 待办事项（高/中/低） | 每日 |
| [CHANGELOG.md](./CHANGELOG.md) | 每次重要修改 | 每功能 |
| [DECISIONS.md](./DECISIONS.md) | 重大决策背景 + 选项 + 原因 | 战略决策时 |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 系统架构 + 关键设计 | 架构变更时 |
| [DEPLOY_CLOUDBASE.md](./DEPLOY_CLOUDBASE.md) | CloudBase 部署 SOP | 部署变更时 |

---

**新 AI 接手步骤**：
1. 读 README.md (项目入口)
2. 读 STATUS.md (本文件, 当前状态)
3. 读 TODO.md (待办事项 + 优先级)
4. 读 docs/ARCHITECTURE.md (架构 + 关键设计)
5. 读 CHANGELOG.md (最近修改历史)
6. 读 DECISIONS.md (重大决策，避免重复讨论)
7. 跑 `pnpm dev --port 3004` + 打开 http://localhost:3004/
8. 读代码: `frontend/components/world-map-leaflet.tsx` (核心 UI)

---

## 12:18 实测验证 (NJX 让我读 4 handoff + 答 4 P0 验证问题, 反馈评审 root mvs_adf2f57e...)

### 测试环境 (12:18 实测)

| URL | 状态 |
|---|---|
| `http://localhost:3004/` | **200 OK** (PID 27598, Next.js 15 dev) |
| `http://localhost:8001/api/health` | **200 OK** (PID 63272, uptime 11034s, `llm_mode=live, rag_backend=fts5`) |
| `http://localhost:8001/api/cities` | **200, 223 城市** (真数据, P0 修复 225→223) |
| 公网 `https://aog.njx.com/api/health` | **400 Bad Request** ⚠️ InsufficientBalance 阻塞 |

### 4 P0 验证问题 (v2/v4 LAUNCH 都问, 12:18 答)

- **Q1 (lib/api.ts:16 BASE 拼接)**: ✅ **PASS** — commit `8c90ba6` `.replace(/\/api\/?$/, "")` 双兼容公网 + 局本
- **Q2 (RAG 维度 mismatch 1024 vs 384)**: ✅ **PASS** — 根因比预期更深 (chroma 0 docs + fts5 path 错), 改 fts5 + sentence-transformers (commit `b963d94` + v3 rebuild `9e305cb`)
- **Q3 (MINIMAX_API_KEY hardcode)**: ⚠️ **本地 PASS / 公网 PENDING** — 本地 .env mode 600, 公网 .env.cloudbase.example 用占位符, NJX 物理填
- **Q4 (公网 SCF tcb fn deploy)**: ❌ **BLOCKED** — InsufficientBalance 余额耗尽, NJX 续费 + 物理 OAuth

### 5 FOCUSED_RETEST 整改状态 (v3 handoff)

- **P0-1 上海主基地**: 🟡 D-029 PENDING UI / 等 NJX 真 docx (UI "待补"页 + D-029 解释已上, git snapshot 7a79785 确认这俩文件名从来不存在)
- **P0-2 公网 SCF 部署**: ❌ BLOCKED 余额
- **P0-3 联系人权限分类**: ⏳ 未做 (半天)
- **P1-1 RAG 召回 city.contacts**: ⏳ 未做 (2h, 依赖 P0-3 字段设计)
- **P1-2 SyncService ollama**: ✅ PASS (RAG 切 fts5 隐含修, 7/27 12:18 backend log `sync poll: no changes`)

### Playwright 5 张截图 (12:10 实拍, P0 修复完整 verify)

- `/tmp/aog_p0_rebuild_20260727/01_home_default_zoom5.png` (273KB) — 223 城市 / 18 实战 / 8686 知识片段
- `/tmp/aog_p0_rebuild_20260727/02_city_normal_beijing_daxing.png` (124KB) — B-北京大兴 8 parts + 5 contacts
- `/tmp/aog_p0_rebuild_20260727/03_city_pending_shanghai_pudong.png` (94KB) — S-上海浦东 "预案待补" 黄字框 + D-029
- `/tmp/aog_p0_rebuild_20260727/04_city_pending_shanghai_hongqiao.png` (94KB) — S-上海虹桥 "预案待补" 黄字框 + D-029
- `/tmp/aog_p0_rebuild_20260727/05_chat_aog_query.png` (273KB) — chat 入口

### Reply to 评审 root

- scratchpad: `HANDOFF-REPLY-2026-07-27-1217.md` (7466 bytes)
- 评审 root 收到后跑 FOCUSED_RETEST 5 项 (不重跑 8 旅程)
- 期望 3.85 → 4.5+/5 升级 EXPERIENCE_READY (P0-1+3+P1-1+2 改完)
