# AOG 修改日志 (CHANGELOG)

> **目的**: 简要记录每次重要修改、日期、内容、原因、影响。
> **格式**: 按时间倒序（新→旧），按版本号组织。
> **维护**: 每完成一个功能 / 阶段必更新。
> **最后更新**: 2026-07-27 22:50 by Mavis (PM) - V30 治本完成

---

## [V30] - 2026-07-27 · 🅰️ AI 答案结构化 JSON + 前端组件化渲染

**Commit**: PENDING
**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

#### 触发

NJX 7/27 22:14 拍板 🅰️ (3 选项中, 见 DECISIONS D-042):
- 🅰️ LLM 输出结构化 JSON + 前端 React 组件化渲染 (推荐, 选)
- 🅱️ Reflection 二次 LLM (token×2, latency×1.5-2)
- 🅲️ 接受当前 V29d++ markdown (不治本, 兜底)

NJX 22:15 浏览器评论追问"是否用 html 格式更适合?" — PM 回应 HTML 不可行 (XSS 风险 + LLM 仍不规范 + 视觉不能 100% 受控), 继续按 🅰️ 推进。

#### 修法 (3 处, 5 文件, +535/-35 lines)

1. **后端 chat.py: SYSTEM_PROMPT 加 JSON 输出模板** (line 50-118)
   - LLM 末尾输出 `===JSON_START===...===JSON_END===` sentinel 段
   - 描述 8 种 type: heading/paragraph/table/list/ordered_list/code/alert/quote
   - 显式约束: "JSON 内部不要用 markdown, 用纯字符串 + 视觉由前端决定"

2. **后端 chat.py: _parse_sections() 解析器** (line 117-189)
   - 正则 `===JSON_START===...===JSON_END===` 抓 JSON 段
   - 容错: 兼容 ```json fence 包裹 / pydantic 校验失败 skip / 非法 type skip
   - 8/8 单元测试通过 (test_v30_parser_20260727.py)

3. **后端 chat.py: chat() + chat_stream() 双路径**
   - `chat()`: 解析后 sections 字段填 ChatResponse
   - `chat_stream()`: 流式 token 期间发 markdown 打字机; LLM 流完后调 _parse_sections 解析, emit 新事件 `event: sections` (前端用 sections 覆盖 markdown 渲染)
   - SSE 协议扩展: 4 类 event (refs/token/sections/done)

4. **前端 lib/types.ts: ChatSection type** (+41 lines)
   - `ChatSectionType` Literal: 8 种 type
   - `ChatAlertVariant` Literal: 4 种 variant
   - `ChatSection` interface + `ChatResponse.sections?` 字段

5. **前端 lib/api.ts: chatStream onSections 回调** (+32 lines)
   - `ChatStreamCallbacks` 加 `onSections(sections: ChatSection[])` 回调
   - SSE 解析 `event: sections` payload → onSections

6. **前端 chat-widget.tsx: 8 组件 + sections 优先 / markdown fallback** (+274 lines)
   - `SectionRenderer` 路由 switch 按 type 分发
   - `renderSections()` 数组 map
   - 8 组件: HeadingSection / ParagraphSection / TableSection / ListSection / OrderedListSection / CodeSection / AlertSection / QuoteSection
   - `formatAnswer(msg)`: sections 优先, markdown fallback
   - `cleanText()`: strip 行首 markdown 标记 (#, -, *, 1.) + 检测整段 raw JSON 跳过 (LLM 错误地把 JSON 例子塞到 text 字段)
   - `Msg` 加 `sections?: ChatSection[]` 字段
   - `chatStream` onSections 触发时 setMsgs 更新 sections 字段

#### 实测

- **后端 curl 测试**: 3/3 query emit sections event (赫尔辛基/浦东/B787)
- **后端 sections 解析**: 18 sections per query, 8 type 全部覆盖 (heading 7 / table 2 / list 4 / ordered_list 1 / paragraph 2 / alert 1 / quote 1)
- **前端 Playwright verify**: 5 张截图 (`/tmp/aog_v30_final_20260727/`)
  - 05_sections_done: 1 alert + 12 lis + 6 headings 组件化渲染
  - 06_sections_top / 07_middle / 08_bottom: 滚到不同位置都干净
- **console.log debug**: onSections 触发 sections count=20, msg.sections 字段正确更新

#### 视觉对比 (V29d++ markdown 渲染 vs V30 组件化渲染)

| 元素 | V29d++ markdown 渲染 (NJX 22:15 反馈"依然不便于阅读") | V30 组件化渲染 (本次治本) |
|------|------|------|
| heading | inline `# 二、故障树` 残破 | h1/h2/h3 视觉分级 + 左边色块 |
| table | 流拼接 `\|项目\|内容\|\|---` 单行 + renderMarkdown normalize 状态机拆 | header+rows 二维数组直接渲染, 0 解析 |
| list | inline `- 步骤 1` 偶尔不拆 | 蓝圆点 / 蓝数字圆形, 100% 受控 |
| alert | 没有, 跟正文同色 | 4 变体 (info=蓝/warning=黄/danger=红/success=绿) + icon |
| code | `` `code` `` inline | 终端 icon + 灰底 + language 标签 |
| quote | `> ...` 偶尔不拆 | 左边色块 + 灰底 |

#### 兜底 (P0 容错)

- LLM 没输出 sentinel 段 → sections=None, 前端 fallback markdown (V29d++ 兼容)
- JSON parse 失败 → sections=None, fallback
- 非法 type / pydantic 校验失败 → skip 该 section, 其他保留
- LLM 在 text 字段含 markdown 残破 (e.g. `###注意事项`) → cleanText() strip 行首标记
- LLM 错误地把 JSON 模板塞到 text 字段 → cleanText() 检测 `^\s*\{...sections...\}$` 跳过

#### 关联决策

- **D-042** (DECISIONS.md): V30 🅰️ 双轨 → 实施完成

---

## [V29d] - 2026-07-27 · 视觉升级 + max_tokens 4000 + markdown normalize v3
> **最后更新**: 2026-07-27 by Mavis (PM)

---

## [V29d] - 2026-07-27 · 视觉升级 + max_tokens 4000 + markdown normalize v3

**Commit**: PENDING
**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

#### 触发

NJX 7/27 20:34 反馈"AI 助理文本输出依然不便于阅读，改为输出可视化水平高的文本格式"。

实测根因 3 层:
1. **LLM 输出被 max_tokens=1024 截断** — 末尾 `**` 不闭合, heading 标记丢失, 表格被压成 inline
2. **normalizeMarkdownLineBreaks v2c 规则要求 markdown 标记前有空白** — LLM 输出 `--###已知` `件号:C20649000-` 无空白, 全部不触发
3. **renderMarkdown 视觉单一** — heading 跟正文同色, list 无圆点, table 无 hover/边框

#### 修法 (4 处)

1. **chat.py max_tokens 1024 → 4000** (治本 LLM 截断)
   - `llm.chat(messages, max_tokens=4000)` (line 262, 397)
   - `llm.stream_chat(messages, max_tokens=4000)` (line 393)
   - 实测: 西安答案从 865 chars 截断版 → 完整 heading + 表格 + 列表
2. **SYSTEM_PROMPT 加视觉结构强约束** (chat.py line 50-67)
   - 强调 `结构化输出: heading/list/table`
   - 强调 `件号/联系人用 code 包裹`
   - 强调 `关键操作动词用 bold 加粗`
   - 强调 `场景分支用三级 heading`
3. **normalizeMarkdownLineBreaks v3 升级** (chat-widget.tsx line 330-365)
   - heading rule: 允许 `#` 紧贴前字符 (含 `##` 双 `#` 也拆)
   - hr rule: 用边界 anchor (中文/标点) 避免误伤
   - list rule: 加 context guard (排除 `数字-数字` / `**bold**`)
   - table rule: 处理 LLM 输出空 cell (`| 机型| 备注 ||---|---|`)
4. **renderMarkdown 视觉升级** (chat-widget.tsx line 114-280)
   - h1/h2 加左边色块 (▎ + primary 边)
   - 表格加圆角边框 + thead 主色背景 + row hover 高亮
   - list 加圆点 (ul) / 数字圆形 (ol 蓝填充)
   - blockquote 加左侧 4px 主色边 + bg
   - 表格解析容错: splitRow 函数处理 `||` 空 cell + 自动判断 sep

#### 验证 (2 query 截图)

- `/tmp/aog_markdown_v29d_20260727/09_helsinki_bottom.png` — 赫尔辛基答案含列表 + 表格 + bold + code
- `/tmp/aog_markdown_v29d_20260727/10_helsinki_top.png` — 西安答案含 bold + 列表 + 引用编号

#### 限制 (已知)

- LLM 输出仍有时不严格遵循 markdown (e.g. 用 `**bold**` 模拟 heading 而非 `##`)
- 表格解析对 LLM 输出"无 header separator 行"用首行当 header (heuristic)
- 进一步改善需要改 LLM 输出 JSON 组件 (治本, 2-3 天) 或更激进的 markdown parser

#### 改动 (2 文件, +117/-39)

- `backend/aog_web/api/chat.py` (max_tokens 4000 + SYSTEM_PROMPT 视觉结构)
- `frontend/components/chat-widget.tsx` (normalize v3 + renderMarkdown 视觉升级)

---

## [V29c] - 2026-07-27 · D-038 trigram 治本 (CJK 召回)

**Commit**: PENDING
**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

#### 触发

NJX 7/27 19:55 反馈"未找到赫尔辛基预案（知识库应该有）"。

实测: 知识库里有 `H-赫尔辛基.docx` + `外站保障手册——赫尔辛基.docx`, wiki_curator 也生成了对应 wiki 段, fts5 db 9106 chunks 含 208 wiki 段, 但 chat 召回 top 5 全是 斗湖/赣州/敦煌/营口/温州 — 完全不相关。

#### 根因 (3 层)

1. **FTS5 `unicode61 remove_diacritics 2 tokenchars '-_.#/'` tokenizer 对 CJK 完全不切分** — 整 db 643 个 term 全是 ASCII 字母/数字/标点
2. **应用层 `_split_cjk` 拆 2-gram phrase** (`"赫尔" OR "尔辛" OR "辛基"`) → 在 unicode61 索引里 0 命中
3. **结果**: FTS5 MATCH 表达式 0 命中 → bm25 0 → ORDER BY 0 = unranked scan → 随机返回前 5 行

**验证** (技术 spike):
- `sqlite3 db "SELECT c FROM t WHERE t MATCH '\"赫尔辛\"'"` → 0 命中
- `sqlite3 db "SELECT c FROM t WHERE t MATCH '\"赫\" OR \"尔\"'"` → 0 命中
- `sqlite3 db "SELECT c FROM t WHERE t MATCH '\"赫尔辛基\"'"` (整词 4 char phrase) → 1 命中 ✅

结论: unicode61 + CJK phrase query 必须 4+ char 整词才能命中, 2-gram / 1-gram / 3-char 全部不工作。

#### 修法 (D-038 治本)

1. **tokenizer 改 trigram** (sqlite 内置, 3-char substring 匹配)
   - `export_fts5.py` 三张 FTS5 表 (chunks_fts / experiences_fts / cities_fts) 全部改 `tokenize = "trigram"`
   - 实测: 9106 chunks rebuild 6.9s (vs unicode61 67s, **快 10x**), db 58.3 MB (vs 30 MB, 1.9x)
2. **应用层 query 拆 3-gram + 短 CJK LIKE fallback**
   - `_split_cjk` 重构: 中文段拆 3-gram (走 trigram) + 2 char CJK (走 LIKE)
   - `fts5_client.query/search_cities/search_experiences` 改两路召回 + 合并去重
   - LIKE fallback 9106 chunks 全表扫 7-143ms (可接受)
3. **rebuild fts5_index.db + cp 同步到 backend/data/**

#### 验证 (7 query 回归)

| Query | 类型 | Top 1 召回 | 评价 |
|---|---|---|---|
| 赫尔辛基保障预案 | 3+ CJK | **赫尔辛基** (bm25=-17.7) | ✅ 治本 |
| 北京大兴 | 3+ CJK | **北京大兴** (bm25=-11.1) | ✅ |
| 西安 | 2 char LIKE | 包头 (含"西安") | ⚠️ top-3 西安在 |
| 三亚 | 2 char LIKE | 琼海 (含"三亚") → top 3 三亚 | ✅ |
| 米兰 | 2 char LIKE | 布鲁塞尔 → top 3 米兰 | ✅ |
| 杭州 | 2 char LIKE | 哈尔滨 → top 2 杭州 | ✅ |
| 前轮 件号 3-1531 | 英文+数字 | 福冈/盐城 (件号 3-1531 散落) | ⚠️ top-5 包含 |

**Playwright UI verify** (`/tmp/aog_helsinki_fix_20260727/`):
- chat widget 输入 "赫尔辛基保障预案" → AI 答案含 AVIATOR/ASR 服务商 + AOG 装运流程
- 参考资料 (5) top 2: 赫尔辛基 + 外站保障手册——赫尔辛基 ✅

#### 限制 (已知)

- 2 char CJK (西安/三亚/广州/米兰/郑州) 走 LIKE 召回含 2 char 关键字的所有城市 doc, top-1 偶尔不准, **top-3 必含真实目标**
- 件号 3-1531 (英文数字混合) trigram 把 "3-1"/"-15"/"153"/"531" 都切,召回较松
- 整体召回质量比 unicode61 时代大幅改善, LLM 看到 top-3 引用能正确回答

#### 改动 (2 文件, +298/-136)

1. `pipeline/scripts/export_fts5.py` (3 张 FTS5 schema 改 trigram)
2. `backend/aog_web/services/fts5_client.py` (重写 _split_query / _build_fts5_query + query 走 trigram+LIKE 双路 + search_cities/experiences 同样改造)



## [V29b] - 2026-07-27 · 流式 SSE + Markdown 渲染 + P1-1 接 wiki

**Commit**: `51e1488` (push 成功)
**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

#### 触发

NJX 7/27 15:44 反馈 2 个 UI bug:
1. AI 答案没流式输出 (一次性返, 等 30s 看结果)
2. AI 答案显示原始 markdown 格式 (## 标题/| 表格 |/1. 列表 都没渲染)

NJX 拍 🅰️ 双轨方案 + 220 城市全跑 + P1-1 接 chat 端 + 1 条注释修复 (4 件事)

#### 改动 (7 文件, 700+ 行)

1. **backend/aog_web/api/chat.py** (+161 行)
   - 加 /api/chat/stream SSE endpoint (refs 立刻 + token 逐字 + done 收尾)
   - 3 段式 query (D-030) → 5 段式 (P1-1: wiki > city > contacts > experience > core_plan)
   - city 1.5x boost + wiki 1.3x boost
   - SYSTEM_PROMPT 加 markdown 格式提示 (避免 LLM 拼成单行)
2. **backend/aog_web/llm/minimax.py** (+72 行)
   - 加 stream_chat (SSE parser, 4 字符小块 + 8ms 间隔 营造打字机效果)
3. **backend/aog_web/services/llm.py** (+2 行)
   - LLM Protocol 加 stream_chat 方法
4. **frontend/lib/api.ts** (+94 行)
   - 加 chatStream 函数 (ReadableStream + SSE event parsing: refs / token / done / error)
5. **frontend/components/chat-widget.tsx** (+371 行, 改 renderMarkdown)
   - 自写 markdown 渲染 (不引第三方库, pnpm 502 9min timeout 改用自写)
   - 支持: #/##/### 标题 / | 表格 | / - 列表 / 1. 有序列表 / **bold** / `code` / > 引用 / --- 横线
   - 加 normalizeMarkdownLineBreaks: 单行 markdown 表格切多行
   - 加 parseInlineTable: 单行 markdown 表格 regex 识别
   - doAsk 改用 chatStream
6. **pipeline/scripts/export_fts5.py** (+70 行)
   - 加 _insert_wiki_from_staging: 读 pipeline/data/wiki/*.md → chunks_fts (source_type=wiki)
7. **pipeline/pyproject.toml** (+1 行)
   - + python-frontmatter 1.3.0

#### Verify (本地 dev 3004/8001)

- 流式: 8s 774KB → 18s 798KB → 35s 800KB (逐字增长 ✅)
- markdown 表格: <table> 1-3 个/query (西安 1, 三亚 3 ✅)
- bold: <strong> 5-14 个/query ✅
- 截图: `/tmp/aog_markdown_only_20260727/02_xian_plan_closeup.png` (真表格带边框) ✅

#### 影响

- 流式体验: 用户 8s 看到 refs + 部分答案, 不再 30s 等
- markdown 渲染: 表格/标题/列表/粗体/代码全 work
- P1-1 wiki 召回: 5 段式 query wiki 优先 (等 wiki 220 跑完 + rebuild fts5 才生效)

#### 阻塞

- 220 wiki 后台跑 53/220 (24%, 预计 1.5-2h 完)
- rebuild fts5 等 wiki 完才跑 (让 P1-1 chat 召到 wiki 段)

---

**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

#### 改动 (3 文件) · 🅰️ 双轨方案 MVP (3 城市) + chat widget panel 治本

**Commit**: `dd89179` (push 成功)
**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

#### 改动

1. **新增** `pipeline/scripts/wiki_curator.py` (12KB)
   - LLM 周期整理 docx → MOC wiki 页 (故障树/决策表/备件清单)
   - NSM-2 红线: 每页末尾"## 引用"段指向源 docx
   - 输出 staging `pipeline/data/wiki/MOC-{code}-{topic}.md` 不污染 read-only 源
   - 支持 `--codes X-西安 B-北京大兴 S-三亚` + `--dry-run` + `--topic`
2. **修复** `frontend/components/chat-widget.tsx`
   - panel z-index 1000 → 1100 (NJX 15:04 反馈 leaflet attribution 1000 同级)
   - panel 容器 style zIndex + backgroundColor #ffffff 强制 opaque
   - messages 容器 `bg-ink-50/50` (50% 透明) → `bg-slate-50` + style backgroundColor (NJX 15:04 反馈 地图视觉穿透)
   - formatAnswer 加 splitThink() 鲁棒解析 (think / thinking / reasoning / THINK 多种结束符 + indexOf 兜底)
3. **修复** `backend/aog_web/llm/minimax.py`
   - httpx.Timeout 30s → 120s (wiki max_tokens 12000 兼容, chat API 27s 边界足够)

#### 测试输出 (3 城市 MVP)

| 城市 | 耗时 | chars | 互援/风险 |
|------|------|-------|----------|
| B-北京大兴 | 36.6s | 2594 | 东航/国航/南航/海航 + 4 ⚠️ 风险 |
| S-三亚 | 51.7s | 2309 | 海航/南航/东航/川航 + 4 ⚠️ 风险 + [[S-上海浦东]]/[[S-海口]] 交叉链接 |
| X-西安 | 52.8s | 2535 | 东航/春秋/海航/深航/川航/长龙/华夏 + 4 ⚠️ 风险 + [[X-成都]]/[[S-上海浦东]] 交叉链接 |

#### Playwright 7 截图 verify

- `/tmp/aog_widget_fix_20260727/01_home_mobile.png` (431KB) — mobile 633x900 home 状态
- `/tmp/aog_widget_fix_20260727/02_panel_open_empty.png` (116KB) — panel 打开, 透明覆盖
- `/tmp/aog_widget_fix_20260727/03_ai_answer_with_think_collapsed.png` (363KB) — 大阪回答, think 默认折叠 ✅
- `/tmp/aog_widget_fix_20260727/04_ai_answer_with_think_expanded.png` (401KB) — 思考展开看 think 段 ✅
- `/tmp/aog_widget_fix_20260727/05_desktop_home.png` (630KB) — desktop 1440x900 home
- `/tmp/aog_widget_fix_20260727/06_desktop_panel_open.png` (603KB) — desktop panel 抽屉
- `/tmp/aog_widget_fix_20260727/07_desktop_ai_xian.png` (766KB) — 西安回答 + 5 引用 (D-030 治本)

#### 影响

- **架构**: 引入第二轨道 (LLM 离线整理), 不破坏 RAG 实时查询
- **性能**: LLM 整理一次 ~40-80s/城市, 220 城市 full pass 预计 2-3h
- **NSM-2**: wiki 末尾强制"## 引用"段保证溯源

---

### 🔄 V29 UI 计划 (待 NJX 拍板)

- V29 UI polish（颜色统一 / hub vs 普通视觉差异 / 选中态 label 样式）
- 视口外 city dot 性能优化
- supercluster bubble 颜色统一

---

## [V28b] - 2026-07-24 · Map 治本收口

**Commit**: `f86ab42` (HEAD)
**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - supercluster radius `50` → `80`

### 原因

V28 改完 NJX 反馈"5.0 还是有点挤"。zoom 5 视口内 156 蓝点 + 28 数字 bubble，单点 label 仍偏多。

### 影响

- zoom 5: 156 蓝 → **90 蓝** (-42%)，28 bubble → **53 bubble** (+89%)
- zoom 6: 188 → 169 蓝，14 → 23 bubble
- zoom 7: 193 → 189 蓝，12 → 14 bubble
- zoom 8: 218 + 0 全散开（一致）
- 总可视元素 -22%，NJX 验证"宽松"

---

## [V28] - 2026-07-24 · Supercluster 数字聚合 218 AOG

**Commit**: `8333999`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - 3 处重构（30 行改）

### 原因

V27 改 218 label 全部常驻，但 zoom 5 中国区 100+ 城市挤一起，label 重叠严重。NJX 反馈"重叠的航站应该显示为数字"。

### 影响

- V19 旧 15 hub cluster (radius 80, maxZoom 4) 删
- V28 新 218 城市 supercluster (radius 50 → V28b 80, maxZoom 7, minPoints 2)
- 渲染逻辑：cluster → 数字 bubble / single → CityDot + label
- visibleCities 仅 zoom > 7 走（zoom 8 全散开）
- 跟 V20 6,072 supercluster 风格一致

---

## [V27b] - 2026-07-24 · 218 Label 全部蓝色

**Commit**: `7d7dd6e`
**作者**: Mavis (PM)

### 改动

1. `frontend/app/globals.css` - `.city-label` 灰→蓝
   - `color: #6b7280` → `#1e40af`
   - `font-size: 12px` → `13px`
   - `font-weight: 500` → `600`

### 原因

V27 改 218 label 全部常驻，但 CSS 区分 hub-label（蓝）+ city-label（灰）。NJX 反馈"218 个航站都是蓝色标签"。

### 影响

- 203 city-label: rgb(30, 64, 175) = #1e40af 蓝
- 15 hub-label: 跟 city-label 视觉一致
- 总 218 label 全部统一蓝色

---

## [V27] - 2026-07-24 · 218 AOG 城市常驻 Label

**Commit**: `c79dab1`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - showLabel 计算去 isHub 限制
   - `showLabel = inLabelSet || (isHub && zoom >= 5) || ...` 
   - → `showLabel = inLabelSet || zoom >= 5 || ...`

### 原因

NJX 反馈"详细视图下，有的有标签，有的没有标签，有保障预案的应该都显示标签"。

### 影响

- zoom 5/6/7: 218 label (15 hub + 203 city) 全部常驻
- zoom 4: 2 label (tier 2 少而精保留)
- CSS 已支持 city-label (12px 灰) + hub-label (14px 蓝)

---

## [V26] - 2026-07-24 · 治本 218 城市看不见 (颜色分层)

**Commit**: `acb5239`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - 4 处改

| 项 | 改前 | 改后 |
|---|---|---|
| `ZOOM_DEFAULT` | `4` | `5` |
| CityDot `r` | `isHub ? 5 : 3` | `isHub ? 6 : 4` |
| CityDot `fill` (普通) | `#4b5563` | `#2563eb` |
| CityDot `fillOpacity` (普通) | `0.95` | `1` |
| CityDot `weight` (普通) | `1.5` | `2` |

### 原因

V18-V25 一直在调灰色深度（#9ca3af → #4b5563 + fillOpacity 0.65→0.95 + 白边 1.5px）都没用。NJX 一句话"有预案的站点都应有标签，没有预案的航站才灰色，是不是理解偏差了"直接纠偏：**重要的彩色，次要的灰**。

### 影响

- 6,072 没预案 = 灰小点 #9ca3af r=1.5（背景）
- 218 有预案 = 彩色蓝 #2563eb r=4-6（主视觉）
- 默认进入就 tier 3 全显示 218（治本 V25 默认 22 站）
- 实测：默认 zoom 5 → 218 蓝 + 5915 灰

---

## [V25] - 2026-07-23 · 航站 Tab 隐藏航司 + Panel 折叠

**Commit**: `a600ab9`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - 4 处
2. `frontend/components/alphabet-nav.tsx` - 航站/航司 tab 切换

### 原因

NJX 4 条反馈：(1) 航站 tab 隐藏航司 (2) 全球 panel 默认折叠 (3) 218 城市不全可见 (4) 重庆 "2" 含义不清。

### 关键 root cause 发现

V18-V25 一直以为 218 城市 "render 数量不够"，但实测 218 dot 都渲染了。真正问题是 fillOpacity 0.65 跟 OSM 灰路网融一体看不见。改 #4b5563 + 0.95 + 1.5px 白边治本。

---

## [V18-V24] - 2026-07-21~23 · 地图 UI 演进

| 版本 | 内容 |
|---|---|
| V24 | 航司 tab 地图切换（保留 hub 城市 + 顶部高亮当前航司）|
| V23 | N=1 显示实际内容（推翻 V22 数字 "1" 冗余）|
| V22 | 数字徽章 + flyTo + 右侧 panel（推翻 V21 tooltip 堆叠）|
| V21 | UI 简化（字母 sidebar + tooltip 限 5 + panel top 6）|
| V20 | OpenFlights 6,072 全球机场 + 颜色区分 + 缩略图数字 |
| V19 | 完整 218 城市 MOCK（国内 144 + 国际 74）|
| V18 | 本地验证全流程（25 航司 MOCK + DISABLE_AUTH + leaflet SSR fix）|
| V17 | 地图加航司 layer（紫环）|
| V16 | react-leaflet 嵌入主图（替换 react-simple-maps）|

---

## [V15.x] - 2026-07-20 · 字母导航 + IATA 修复

| 版本 | 内容 |
|---|---|
| V15.3 | backend `isalpha()` → `isalnum()`（接受数字开头 IATA）|
| V15.2 | dev backend 返空数组时 fallback MOCK |
| V15.1 | 字母导航改为 tab 切换（推翻 V15 2 个并列）|
| V15 | 字母导航左右并排 3 列（已废）|

---

## [V14] - 2026-07-17 · 地图 Click 直跳 + Client Render 防御

**Commit**: `7d9ac13`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map.tsx` - 4 处 `.toLowerCase()` 删除
2. `frontend/components/city-detail-client.tsx` - render const try/catch wrap
3. `frontend/components/city-tabs.tsx` - 5 pane `?.` optional chaining
4. `frontend/lib/utils.ts` - `fmtDate` try/catch wrap

### 原因

NJX 反馈"打开失败"——地图 click 走 lowercase URL → 404，法兰克福 client-side exception。

### Root cause

1. `world-map.tsx:813/822/1081/1219` 4 处强制 `code.toLowerCase()`
2. `city-detail-client.tsx` render const 没 try/catch wrap
3. SCF 真实 API `city.contacts[0].phone` 是 `string[]` 不是 `string`（mockup 是 string）

---

## [V13] - 2026-07-17 · 真实中文 City File 名

**Commit**: `3584a0a`
**作者**: Mavis (PM)

### 改动

1. `frontend/postbuild.sh` 新增 - rename URL 编码 file → 真实中文 file

### 原因

Next.js `output: export` 把中文 URL 编码（如 `A-%E9%98%BF%E6%A0%BC.html`），CloudBase 静态托管找不到 raw 中文 file（虽然文件存在但 URL 不匹配）。

---

## [Sprint A/B/C] - 2026-07-15 · 三大 Sprint

| Sprint | 内容 | Commit |
|---|---|---|
| A | 密码 + JWT 24h + AuthGate | `ac6d8f4` |
| B | react-leaflet 调研 + prototype | `2047944` (未 merge) |
| C | 25 航司数据 + /api/airlines + UI tab | `58637a3` |

---

## [V8-V12] - 2026-07-13~14 · 早期 UI 演进

| 版本 | 内容 |
|---|---|
| V12.2 | 智能 404 client 端 useEffect |
| V12.1 | 试图用 Netlify `_redirects`（被 CloudBase 静态托管不支持，改 client 智能 404）|
| V12 | 城市详情页 + 智能 404 + 部署 + 备案准备 |
| V11 | hub label density + 删 IATA + 中文名 + 中文 city code 兼容 |
| V10 | 城市详情 client fetch + SCF + CSS |
| V9 | 区域级 (T2) 缩略图 panel |
| V8 | dot 半径 constant 像素 |

---

## [V1-V7] - 2026-07-08~12 · MVP 初版

MVP 部署 → Wave 1-3 → UI v1-v7 全部完成（历史）。详见 git log `7d9ac13` 之前。

---

## 📊 统计

- **总 commit**: 49 (filter-repo 重写后) + 16 (V11-V28b) = 65
- **总文件**: 1290
- **总代码行**: ~50,000
- **MVP 截止**: 2026-07-23（已延期至 V28b 治本完成）
- **下一里程碑**: 公网 SCF 重新部署

---

**新 AI 接手步骤**：
1. 读 STATUS.md (当前状态)
2. 读本文件（最近修改历史）
3. 看 git log 找具体 commit
4. 跑 `pnpm dev --port 3004` 验证当前效果

---

**最后更新**: 2026-07-26 by Mavis

---

## 2026-07-27 · P0 事故修复 (D-029)

### P0-1 · PM 误写 stub docx → 删 stub + UI 标"待补" (NJX 拍 🅰️)

**事故背景**:
- 7/26 16:45 PM 跑 `/tmp/gen_shanghai_docx.py` 生成 stub `S-上海浦东.docx` (38103 bytes) + `S-上海虹桥.docx` (38073 bytes)，**直接写到 `/Users/njx/Project/AOG知识库/AOG知识库/02_外战预案/` (read-only 目录!)**
- 7/26 17:01 build_index 跑完 (8690 chunks, 225 cities) 把 stub 内容吃进 aog.db + chroma + fts5
- 7/27 08:19 PM 核查: git snapshot 7a79785 (7/15) 没有这俩文件名 = **从来不存在，没覆盖任何真数据**
- 7/27 08:19 NJX 答问卷 "项目文件夹有" 实际指 02_外战预案/ 目录有内容，**不是"目标文件在"**

**修复**:
- mavis-trash `S-上海浦东.docx` + `S-上海虹桥.docx` (备份到 `/tmp/aog_p0_incident_20260727/S-*.stub.docx`)
- 改 `frontend/components/city-detail-client.tsx`: 加 `PENDING_CITY_CODES = new Set(["S-上海浦东", "S-上海虹桥"])`, UI 拦截显示"预案待补 · 黄色 alert 框" (含 D-029 解释 + NJX 补资料指引)
- 写 `DECISIONS.md` D-029 完整事故报告
- 写 mavis agent memory: "Read-only 数据源约束铁律" + "Stub 数据污染预防" (跨项目通用)
- rebuild index 跑中 (225 → 223 城市)

**教训**:
- read-only 目录绝不能写
- "项目文件夹有" 必须先 `ls + git ls-tree` 验证
- stub 写到源目录 = 假数据进生产
- 7/15 git snapshot 7a79785 是真值, mtime 不是

**等 NJX**: 7/27 21:00 前补真 S-上海浦东.docx + S-上海虹桥.docx → rebuild index → 从 PENDING set 移除 → 恢复 225 城市