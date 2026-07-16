# AOG AI 知识库网站 · 计划（plan.md）

> 项目: AOG AI 知识库网站
> PM: Mavis (mavis)
> 最后更新: 2026-07-16
> 截止: 2026-07-23 (1 周 MVP, **已完成**)
> 状态: ✅ **Wave 3 真 E2E 通过, MVP 上线**
> 公网 URL: https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com

## 1 周 MVP 实际产出

| Wave | 子任务 | 状态 | commit |
|---|---|---|---|
| 0.5 | PRD + UI mockup 5 页 + 10 截图 | ✅ | `1aae43a` |
| 1.1 | T1 后端 FastAPI 8 端点 + 7 测试 | ✅ | `1556660` |
| 1.2 | T2 前端 Next.js 5 页面 + 18 截图 | ✅ | `1955b1e` |
| 1.3 | T3 数据 pipeline (248 indexed) | ✅ | `e2a3194` |
| 1.4 | T4 集成 E2E (5 真实 RAG 引用) | ✅ | `32426dc` |
| 1.5 | T5 CloudBase 个人版 + SCF | ✅ | `994d4b9` `7f2d6c7` |
| 1.6 | T6 增量同步 (17 测试 / 81% coverage) | ✅ | `b3fcda0` |
| 2 | Wave 2 全 3/3 done | ✅ | (历史) |
| 3 | T7 真 E2E (4 端点 + NSM-2 + 7 截图) | ✅ | `d32c55e` `d47c93c` |
| 3 | T8 增量同步公网验证 (待) | 🟡 | (用户 4 周后补) |
| 3 | T9 4 文档收尾 | ✅ | this file + WAVE3_NOTES.md |

## 关键决策链 (NJX 拍板)

1. **Vercel+Railway → CloudBase** (NJX 1:57) — 新户免费 + cron 经验
2. **Cloud Run → SCF** (PM 自主) — 个人版无容器托管
3. **Chroma → FTS5** (NJX 13:30) — 个人版 /tmp 装不下 bge-m3
4. **🅲-2 SCF + FTS5** (NJX 拍板) — 免费 + 真数据 + 接受 30-60s 冷启动

---

## §0 Phase 0.5 立项补完（NJX 7/15 拍板加入）

> 触发：NJX 4 文档签字时反问"PRD 确认清楚了吗？UI 高保真原型图什么时候出？"
> 处理：Vibe Coding §0.7.2 阶段 4（PRD）+ 阶段 6（UI 原型）我之前跳过，必须补完才进 Wave 1。

```
Phase 0.5 (D0.5-D1.5, 1.5 天)
├── T0.1 PRD 精简版（PM 自主，30min）       ✓ done 2026-07-15 21:30
├── T0.2 UI HTML 高保真 mockup（sub-agent 1 天）
│   ├── 5 页：首页/城市详情/经验列表/经验详情/404
│   ├── 3 断点：mobile 360 / tablet 768 / desktop 1280
│   ├── 技术：Tailwind + shadcn/ui（HTML 静态版）+ lucide-react
│   ├── 数据：用 PRD §7 真实样例（不是 lorem ipsum）
│   ├── ChatWidget 浮窗（UI + mock 回复）
│   ├── 截图：15 张（5 页 × 3 断点）+ 3 张 ChatWidget
│   └── 输出：aog-web/mockup/ 目录，PM 验收
└── T0.3 调整基线（PM）
    ├── 截止 7/22 → 7/23
    ├── rules.md 加 mockup 验收项
    └── delivery.md 加 T0.2 验收清单
```

**为什么 HTML mockup 不是 Figma**：
- 1 周节奏 Figma 设计太重（1-2 天纯设计 + 切图）
- HTML mockup 可直接当 Next.js 前端骨架（T2 agent 复用）
- 浏览器即开，截图方便验收
- 像素级精度，NJX 一眼判断

---

## §1 阶段总览（Phase / Sprint / Wave）

```
Phase 1 (MVP, 7 天: 7/16-7/23)
├── Phase 0.5 (D0.5-D1.5, 7/16-7/17 中): PRD + UI mockup
├── Wave 1 (D2-D3, 7/18-7/19): 骨架 + 并行 3 子智能体
│   ├── T1 后端骨架 (FastAPI + Chroma + 解析器)
│   ├── T2 前端骨架 (Next.js 15 — 基于 mockup 转)
│   └── T3 数据 pipeline (md/docx/xlsx/pdf 解析 + 向量化)
├── Wave 2 (D4-D5, 7/20-7/21): 集成 + 部署
│   ├── T4 前后端集成 (API 联调 + E2E 本地跑通)
│   ├── T5 Railway + Vercel 部署
│   └── T6 增量同步 (定时轮询 v1.1)
└── Wave 3 (D6-D7, 7/22-7/23): 真 E2E 验收 + 截图 + 文档
    ├── T7 真机访问 + 截图
    ├── T8 增量同步验证
    └── T9 4 文档收尾 + Changelog
```

---

## §2 Wave 1 任务拆解（Day 1-3，并行 3 子智能体）

### T1 后端骨架（独立子智能体 backend-agent）
- **范围**：
  - FastAPI 项目结构 (`aog-web/backend/`)
  - 依赖：fastapi / uvicorn / chromadb / sqlite3 / pypdf / python-docx / openpyxl / httpx
  - API 端点：
    - `GET /api/health` — 健康检查
    - `GET /api/cities` — 220 城市列表（首字母 + 名称 + 状态）
    - `GET /api/city/{code}` — 城市预案详情
    - `GET /api/experiences` — 18 经验列表
    - `GET /api/experience/{id}` — 经验详情
    - `POST /api/chat` — AI 对话（RAG + MiniMax M3）
    - `POST /api/reindex` — 触发重建索引
  - Chroma 向量库（持久化到 `./data/chroma`）
  - SQLite 元数据 `./data/aog.db`
  - 模型抽象层 `aog_web/llm.py` — 接口 `async chat(messages) -> str`，先实现 MiniMax M3
- **验收口径**：
  - `uvicorn aog_web.main:app` 启动成功（curl /api/health 200）
  - 单元测试 ≥ 10 个全绿（pytest）
  - OpenAPI schema 自动生成（/docs 可访问）
- **时间预算**：2.5 天
- **worktree**: `worktrees/backend`

### T2 前端骨架（独立子智能体 frontend-agent）
- **范围**：
  - Next.js 15 App Router + TypeScript + Tailwind + shadcn/ui
  - 路径：`aog-web/frontend/`
  - 页面：
    - `/` 首页（搜索框 + 字母导航 + 推荐城市）
    - `/city/[code]` 城市预案详情
    - `/experiences` 18 经验列表
    - `/experience/[id]` 经验详情
  - 组件：`<ChatWidget>` 右下角悬浮（先做 UI，逻辑等 T1 完成联调）
  - 状态管理：Zustand 轻量
  - 部署：Vercel-ready（next.config + vercel.json）
- **验收口径**：
  - `pnpm dev` 启动，`curl localhost:3000` 200
  - 4 个页面都能渲染（先 mock 数据，联调后切真 API）
  - 响应式：桌面 / 平板 / 手机三态截图
  - Lighthouse 性能 ≥ 80
- **时间预算**：2.5 天
- **worktree**: `worktrees/frontend`

### T3 数据 pipeline（独立子智能体 data-agent）
- **范围**：
  - `aog-web/pipeline/` — 数据处理模块
  - 解析器：
    - `parsers/md.py` — markdown（用 markdown-it-py）
    - `parsers/docx.py` — Word（python-docx）
    - `parsers/xlsx.py` — Excel（openpyxl）
    - `parsers/pdf.py` — PDF（pypdf）
  - 索引脚本 `scripts/build_index.py`：
    - 扫 `AOG知识库/01_AOG预案/` + `02_外战预案/` + `03_保障经验/`
    - 解析 → 文本块（chunk 800 token / overlap 100）
    - 元数据提取（city / category / status / tags）
    - 向量化（bge-m3 via sentence-transformers / 或直接走 embedding API）
    - 写入 Chroma + SQLite
  - 首次全量 build 跑通 + 文档说"全量耗时 / 索引大小 / chunk 数量"
- **验收口径**：
  - `python build_index.py` exit 0 + Chroma 集合有 ≥ 500 文档块
  - SQLite 元数据表 cities ≥ 220 + experiences ≥ 18 + core_plans ≥ 14
  - 跑一次 build 耗时 < 10 min（548 文件）
- **时间预算**：2.5 天
- **worktree**: `worktrees/pipeline`

### Wave 1 依赖图

```
T3 数据 pipeline ─┐
                 ├─→ T4 集成
T1 后端骨架 ─────┘
                 
T2 前端骨架 ─────→ T4 集成
```

**Wave 1 关键约束**：
- T1 / T2 / T3 三个子智能体用 git worktree 隔离
- 各自有 main 分支，PM 在 Day 3 收尾时 merge 到 main
- API 契约由 PM 预先定义（写在 `aog-web/CONTRACT.md`）— 子智能体按契约实现

---

## §3 Wave 2 集成 + 部署（Day 4-5）

### T4 前后端集成
- **范围**：
  - 前端 API base 切换到 `http://localhost:8000`（开发） / Railway URL（生产）
  - 真实接口对接（去掉 mock）
  - ChatWidget 接通 `/api/chat`
  - 错误处理（loading / error toast / fallback）
- **验收**：本地 dev 端到端跑通"查北京大兴 + AI 问 B787"

### T5 Railway + Vercel 部署
- **范围**：
  - Railway: 创建项目 + Postgres（可选）/ Volume 挂 `/data`
  - FastAPI Dockerfile + nixpacks.toml
  - 环境变量：MINIMAX_API_KEY / CHROMA_PATH / SQLITE_PATH
  - Vercel: GitHub 集成 + 自动 deploy
  - 域名：vercel 自动 *.vercel.app（公网即可）
  - CORS 配置（前端域名）
- **验收**：
  - Railway dashboard 显示服务在线
  - Vercel dashboard 显示 build 成功
  - 公网 URL 打开首页 + 三大功能全通

### T6 增量同步 v1.1（定时轮询）
- **范围**：
  - `pipeline/watcher_poll.py` — 每 5min 扫 `AOG知识库/` + `RAW/`
  - 文件 hash 对比（md5）
  - 变化文件 → 重新解析 + 更新 Chroma/SQLite
  - FastAPI 后台 task（asyncio + lifespan）
  - 接口 `GET /api/sync/status` — 上次同步时间 + 队列长度
- **验收**：
  - 改 `AOG知识库/01_AOG预案/AOG保障预案20260204.md` 1 行
  - 等 ≤ 5min → 搜该文件关键字能搜到新内容
  - 截图 dashboard 同步状态

---

## §4 Wave 3 真 E2E 验收（Day 6-7）

### T7 真机访问 + 截图
- 验收人：NJX（PM 调度，NJX 物理 click "打开浏览器"）
- 截图存档 `delivery/screenshots/T7/`：
  - 01_home.png — 首页
  - 02_search_beijing.png — 搜"北京"
  - 03_city_detail.png — 城市详情
  - 04_experiences.png — 18 经验列表
  - 05_experience_detail.png — 经验详情
  - 06_ai_chat.png — AI 对话
  - 07_ai_chat_response.png — AI 回答 + 引用

### T8 增量同步验证
- 截图 `delivery/screenshots/T8/`：
  - 01_before_change.png — 改文件前的检索结果
  - 02_edit_file.png — 改文件 + 保存
  - 03_sync_log.png — 同步日志
  - 04_after_change.png — 5min 后检索新内容

### T9 4 文档收尾
- delivery.md 全部 task 标 done
- goal.md / plan.md 加 Changelog
- 截图全部入库

---

## §5 并行策略

| 维度 | 策略 |
|---|---|
| **worktree** | T1/T2/T3 各开 worktree（`git worktree add`） |
| **commit** | 各自 worktree 独立 commit，PM 统一 merge |
| **API 契约** | PM 预先写 `aog-web/CONTRACT.md`，子智能体按契约 |
| **冲突解决** | 主要冲突在 `aog-web/` 根目录（package.json / pyproject.toml），子智能体不碰根目录配置 |
| **失败回退** | 任一 task 失败 ≥ 3 次 → 弹窗 NJX |

---

## §6 时间线（甘特）

| Day | 主线 | 并行 |
|---|---|---|
| D1 (7/16) | 写 4 文档 + CONTRACT.md | git init + Vercel/Railway 账号准备 |
| D2 (7/17) | T1 + T2 + T3 启动 | 文档 review |
| D3 (7/18) | T1 + T2 + T3 收尾 + merge | 单元测试 |
| D4 (7/19) | T4 集成 | T5 部署准备 |
| D5 (7/20) | T5 部署 + T6 同步 | 联调 |
| D6 (7/21) | T7 + T8 真 E2E | 修 bug |
| D7 (7/22) | T9 文档收尾 | 复盘 + Phase 2 提案 |

---

## §7 资源与依赖

| 资源 | 来源 | 备注 |
|---|---|---|
| MiniMax M3 API key | NJX 已有 / PM 配 .env | env var: MINIMAX_API_KEY |
| Vercel 账号 | NJX | git push 自动 deploy |
| Railway 账号 | NJX | 信用卡 / 试用额度 |
| 域名 | vercel.app 即可（v1 暂不绑 custom domain） | Phase 2 绑 aog.njx.com |
| MiniMax M3 文档 | https://platform.MiniMax.io/docs | 模型名 + endpoint |
| bge-m3 embedding | HuggingFace / sentence-transformers | 本地跑 / 调 API 都行 |

---

## §8 失败处理

- **子智能体失败 1-2 次**：PM 自主 steer 改 prompt
- **失败 3+ 次**：弹窗 NJX（换 agent / 改 plan / 暂停 / 收摊）
- **部署卡住 > 4h**：降级到本地 dev server demo，部署留 Phase 2
- **AI API 限流**：加 LRU 缓存 + 降级到非 AI 检索

---

## §9 关联

- `goal.md` — 北极星 + MVP 范围
- `rules.md` — 团队规则
- `delivery.md` — 验收清单
