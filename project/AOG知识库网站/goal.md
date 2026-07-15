# AOG AI 知识库网站 · 目标（goal.md）

> 项目: AOG AI 知识库网站
> Owner: NJX (OPC)
> PM: Mavis (mavis)
> 最后更新: 2026-07-15
> 截止: 2026-07-22 (1 周 MVP)

---

## §1 一句话定位

把 `/Users/njx/Project/AOG知识库/AOG知识库/` 下 548 个 AOG 业务文档（核心预案 / 外战 220 城市 / 保障经验 / 课件 / 立项 / 组织 / 元数据）变成一个**云端可访问的 AI 知识伙伴**，让航材 AOG 支援工程师在 ≤ 5s 内查到任一航站的应急保障预案，并通过 AI 对话获得基于真实文档的解答。

---

## §2 背景与痛点

| 现状 | 痛点 | 影响 |
|---|---|---|
| 知识库 548 文件已 Obsidian 整理 | 但只能本地访问 | 远程支援 / 现场值班查不到 |
| 220 城市外战预案 docx + 220 md 伴随笔记 | 没有按航站快速检索 | 应急响应慢 5-10 min |
| 03_保障经验 18 个实战案例 | 散落 MOC 下无 AI 检索 | 经验复用率低 |
| AI 知识库已立项（05_项目立项）但未上线 | 工作机 AGC 智能体只本地跑 | 团队成员无法协同 |

**核心痛点**：AOG 应急场景下"找文档慢 5 分钟 = 飞机多停场 5 分钟 = 直接经济损失"。知识库必须可云端访问 + 智能检索 + AI 对话。

---

## §3 用户与场景

### 主用户：航材 AOG 支援工程师 / 值班调度（3-5 人内部）
- **场景 A — 应急现场查预案**：值班接到浦东 AOG 电话 → 5s 内查"上海/浦东"航站预案 → 找到联系人 / 备件 / 物流
- **场景 B — 经验复用**：遇到 BMS9-3 玻璃纤维布问题 → 搜保障经验 → 找到历史案例 + 处理方案
- **场景 C — AI 助手对话**："B787 风挡 AOG 处理流程是什么" → AI 给步骤 + 引用 ≥ 1 个真实文档链接

### 次用户：维修工程部管理层（5-10 人外部/合作方）
- 查 AOG 智能体项目立项 / 成果 / 国际化进展
- 留 Phase 2 设计，本期不实现

---

## §4 北极星指标（North Star Metric）

| 指标 | 目标 | 验证方式 |
|---|---|---|
| **NSM-1 检索时延** | 用户发起航站查询到出结果 ≤ 5s | Lighthouse / curl timing / 截图 |
| **NSM-2 答案有据** | AI 对话每次回答引用 ≥ 1 个真实知识库文档（带链接） | delivery §3.2 验收 |
| **NSM-3 MVP 上线** | 7 天内公网可访问（Vercel + Railway） | 域名解析 + curl 200 |
| **NSM-4 增量同步** | 知识库文件变化到网站更新 ≤ 5 min | 改文件 → 等 5min → 验证 |

**北极星**：**用户在应急现场 5s 内查到任一航站 AOG 预案，且 AI 回答 100% 引用真实文档**。

---

## §5 MVP 范围（v1 — 1 周交付）

### 核心 3 件套（必做）

1. **航站查询**（02_外战预案 220 城市 + 01_AOG预案 14 个核心）
   - 首页输入框 / 字母导航（A-Z 城市首字母）
   - 点击城市 → 预案详情页（md 渲染 + docx/pdf 下载链接）
   - 标签筛选（地区/状态）

2. **保障经验**（03_保障经验 18 个）
   - 列表页：18 个经验文档卡片
   - 详情页：md 渲染 + 原 docx 下载
   - 全文搜索

3. **AI 对话**（MiniMax M3 + RAG）
   - 右下角悬浮对话窗
   - 用户问"浦东 AOG 怎么处理" → RAG 检索 top-5 → LLM 综合回答 + 引用
   - 模型抽象层：先接 MiniMax M3，预留 OpenAI/Claude 接口

### 数据 Pipeline
- 一次性全量 build 脚本（手动触发 + 可 CI 触发）
- 解析 md / docx / xlsx / pdf → 文本 + 元数据
- 向量化（bge-m3 / text-embedding-3-small）→ Chroma 向量库
- 元数据存 SQLite（id / path / category / tags / city / status）

### 增量同步（v1.1 简化）
- **MVP 阶段：定时轮询**（每 5min 扫文件清单 + hash 对比）— Railway 端
- Phase 2 升级：macOS 开发机 fsevents daemon → Railway webhook

### 部署
- **前端**: Vercel (Next.js 15 App Router) + 公网域名
- **后端**: Railway (FastAPI + Chroma + SQLite 持久化)
- **存储**: Railway Volume (挂载 /data 给 Chroma + SQLite)
- **AI**: MiniMax M3 (HTTP API)

### 不在 MVP 范围（Phase 2+）
- 课件 / 项目立项 / 组织人员 / 元数据 4 主题
- 多用户 / 权限
- 用户上传文档
- 移动端原生 app
- 多模型切换 UI（仅 API 层抽象）
- 桌面 app
- 全文搜索高级功能（高亮 / 分面 / 纠错）

---

## §6 验收定义（Definition of Done）

项目 MVP 完成 = 满足以下**全部**：

- [ ] 公网域名打开网站首页 ≤ 2s
- [ ] 输入"北京大兴" → 5s 内出预案详情页
- [ ] 字母导航可点 A-Z 所有有数据的字母
- [ ] 18 个保障经验全部可列表 + 详情访问
- [ ] AI 对话问"B787 风挡 AOG" → 5s 内回答 + 引用 ≥ 1 个真实文档链接
- [ ] 改动 RAW/AOG保障预案20260204.doc → 等 ≤ 5min → 网站检索结果更新
- [ ] Vercel / Railway 部署 dashboard 截图存档
- [ ] 全部截图存 `project/AOG知识库网站/delivery/screenshots/`

---

## §7 风险与降级方案

| 风险 | 触发条件 | 降级方案 |
|---|---|---|
| Railway 部署 Chroma 体积超限 | Chroma index > 1GB | 换 LanceDB（更轻量） |
| MiniMax M3 API 限流 | RPM > 60 | 加 LRU 缓存 + 重试 |
| docx 解析失败 | 复杂表格 / 公式 | 降级到纯文本 + 提示 |
| 1 周内 Vercel/Railway 部署卡住 | deploy 失败 ≥ 3 次 | 降级到本地 dev server demo 验收 |
| 增量同步复杂 | fsevents 跨平台问题 | 留 Phase 2，定时轮询够 MVP |

---

## §8 不做（明确砍掉）

- ❌ 桌面 app（OPC 内部 Web 即可）
- ❌ 多用户系统（MVP 单租户）
- ❌ 文档上传（只读 + 同步现有）
- ❌ 课件/组织/立项 4 主题（数据已在库，但 v1 不上线）
- ❌ 移动端原生（响应式 Web 即可）
- ❌ 多语言（中文 only）
- ❌ 离线模式（云端 only）
- ❌ 评论 / 标注 / 协作

---

## §9 关联

- `plan.md` — 怎么走到这里
- `rules.md` — 怎么走才合规
- `delivery.md` — 走到没走到
- `references/goal-template.md` — 模板来源
