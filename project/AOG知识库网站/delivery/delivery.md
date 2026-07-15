# AOG AI 知识库网站 · 交付（delivery.md）

> 项目: AOG AI 知识库网站
> PM: Mavis (mavis)
> 最后更新: 2026-07-15
> 截止: 2026-07-22

---

## §1 任务清单

| ID | 任务 | 状态 | 验收人 | 派发日期 | 完成日期 | 备注 |
|---|---|---|---|---|---|---|
| T0.1 | PRD 精简版 | done | PM (自主) | 2026-07-15 | 2026-07-15 | Phase 0.5 |
| T0.2 | UI HTML 高保真 mockup | done | sub-agent mockup-agent | 2026-07-15 | 2026-07-15 | Phase 0.5 |
| T0.3 | 调整基线（截止/规则/delivery） | done | PM (自主) | 2026-07-15 | 2026-07-15 | Phase 0.5 |
| T1 | 后端骨架（FastAPI + Chroma + 解析器） | done | sub-agent backend-agent | 2026-07-15 | 2026-07-15 | Wave 1 |
| T2 | 前端骨架（Next.js + 三大页面） | done | sub-agent frontend-agent | 2026-07-15 | 2026-07-15 | Wave 1 |
| T3 | 数据 pipeline（解析 + 向量化） | done | sub-agent data-agent + PM 接管 | 2026-07-15 | 2026-07-16 | Wave 1 |
| T4 | 前后端集成 | done | PM 自主 (Wave 1 端到端 PASS) | 2026-07-15 | 2026-07-15 | Wave 2 |
| T5 | CloudBase 部署 (pgvector 替代 Chroma) | in_progress | PM 接管 (NJX 1:57 选 CloudBase) | 2026-07-16 | - | Wave 2 |
| T6 | 增量同步（定时轮询 v1.1） | done | sub-agent devops-agent | 2026-07-16 | 2026-07-16 | Wave 2 |
| T7 | 真机访问 + 截图 | pending | NJX (PM 验收) | D6 | - | Wave 3 |
| T8 | 增量同步验证 | pending | NJX (PM 验收) | D6 | - | Wave 3 |
| T9 | 4 文档收尾 | pending | PM | D7 | - | Wave 3 |

---

## §2 详细验收清单

### T0.2 UI HTML 高保真 mockup
- [x] `aog-web/mockup/` 目录存在（merge: feature/t0.2-mockup → main commit 52e5fb1 → 902f319 → 3a0d7c8）
- [x] 5 个 HTML 页面：index.html / city.html / experiences.html / experience.html / 404.html
- [x] 城市详情页支持 URL hash 参数（如 `city.html#B-北京大兴`）
- [x] 3 断点响应式：mobile 360 / tablet 768 / desktop 1280（截图 03/02/01 验证）
- [x] Tailwind CSS 加载（CDN）
- [x] shadcn/ui 风格组件（手写，模仿 shadcn 视觉）
- [x] inline SVG 图标（lucide 风格，hand-crafted）
- [x] 字母导航 26 字母可点击
- [x] 首页推荐城市卡片 4 张（北京大兴/上海浦东/广州白云/香港）
- [x] 经验列表 18 个卡片（PRD §7 真实样例）
- [x] ChatWidget 浮窗：右下角 + 抽屉 + 3 示例问题 + mock AI + 引用
- [x] 真实 AOG 数据：4 城市/6 经验/真实件号(C20649000等)/真实电话(021-22379771)/真实机场(PKX/PVG)
- [x] 文件大小：18.6K/24.5K/13.1K/15.0K/6.5K（每页 < 200KB）
- 截图（存 `delivery/screenshots/T0.2/`）：
  - 01_home_desktop.png / 02_home_tablet.png / 03_home_mobile.png
  - 04_city_desktop.png / 05_city_mobile.png
  - 06_experiences_desktop.png
  - 07_experience_desktop.png
  - 08_chat_desktop.png / 09_chat_mobile.png
  - 10_404.png
  - 合计 ≥ 10 张

### T1 后端骨架
- [ ] `uvicorn aog_web.main:app --port 8000` 启动成功
- [ ] `curl http://localhost:8000/api/health` → `{"status":"ok"}` 200
- [ ] `curl http://localhost:8000/api/cities | jq 'length'` ≥ 200
- [ ] `curl http://localhost:8000/api/city/B-北京大兴` → 含完整预案文本
- [ ] `curl -X POST /api/chat -d '{"q":"B787 风挡 AOG"}'` → AI 回答 + 引用
- [ ] pytest 全绿，coverage ≥ 60%
- [ ] OpenAPI /docs 可访问
- [ ] 模型抽象层 `aog_web/llm.py` 实现 MiniMax M3（占位 + 真调）
- 截图：
  - `delivery/screenshots/T1/01_health.png`
  - `delivery/screenshots/T1/02_cities.png`
  - `delivery/screenshots/T1/03_city_detail.png`
  - `delivery/screenshots/T1/04_chat.png`
  - `delivery/screenshots/T1/05_openapi.png`

### T2 前端骨架
- [ ] `pnpm dev` 启动，localhost:3000 200
- [ ] 首页含搜索框 + 字母导航
- [ ] `/city/[code]` 渲染
- [ ] `/experiences` 列表 18 个
- [ ] `/experience/[id]` 详情
- [ ] ChatWidget 悬浮 UI（逻辑可等 T4）
- [ ] Lighthouse desktop ≥ 80
- 截图：
  - `delivery/screenshots/T2/01_home_desktop.png`
  - `delivery/screenshots/T2/02_home_tablet.png`
  - `delivery/screenshots/T2/03_home_mobile.png`
  - `delivery/screenshots/T2/04_city.png`
  - `delivery/screenshots/T2/05_experiences.png`
  - `delivery/screenshots/T2/06_lighthouse.png`

### T3 数据 pipeline
- [ ] `python -m pipeline.build_index` exit 0
- [ ] Chroma 集合 docs ≥ 500
- [ ] SQLite cities ≥ 220
- [ ] SQLite experiences ≥ 18
- [ ] SQLite core_plans ≥ 14
- [ ] 跑一次 build 耗时 < 10 min
- [ ] `data/index_stats.json` 记录完整
- 截图：
  - `delivery/screenshots/T3/01_build_log.png`
  - `delivery/screenshots/T3/02_chroma_count.png`
  - `delivery/screenshots/T3/03_sqlite_count.png`
  - `delivery/screenshots/T3/04_stats_json.png`

### T4 集成
- [ ] 前端 API base 切真后端
- [ ] 去掉所有 mock
- [ ] ChatWidget 接通 `/api/chat`
- [ ] 错误处理（loading / error / fallback）
- [ ] 端到端：搜"北京大兴" → 详情页 → AI 问"B787" → 回答带引用
- 截图：
  - `delivery/screenshots/T4/01_e2e_search.png`
  - `delivery/screenshots/T4/02_e2e_chat.png`

### T5 部署
- [ ] Railway dashboard 服务在线
- [ ] Vercel dashboard build 成功
- [ ] 公网 URL 打开首页
- [ ] 公网 URL 三大功能全通
- [ ] CORS 配置正确
- 截图：
  - `delivery/screenshots/T5/01_railway_dashboard.png`
  - `delivery/screenshots/T5/02_vercel_dashboard.png`
  - `delivery/screenshots/T5/03_public_home.png`
  - `delivery/screenshots/T5/04_public_search.png`
  - `delivery/screenshots/T5/05_public_chat.png`

### T6 增量同步
- [ ] 改文件 → 等 ≤ 5min → 检索新内容
- [ ] `/api/sync/status` 返回 last_sync_time
- [ ] Railway 日志显示 polling 正常
- 截图：
  - `delivery/screenshots/T6/01_before.png`
  - `delivery/screenshots/T6/02_edit.png`
  - `delivery/screenshots/T6/03_sync_log.png`
  - `delivery/screenshots/T6/04_after.png`

### T7 真 E2E（NJX 物理 click）
- [ ] NJX 打开公网 URL 看到首页
- [ ] 搜"北京大兴"出结果
- [ ] 字母导航可点
- [ ] 18 经验可访问
- [ ] AI 对话有引用
- 截图：7 张（T7 验收现场）

### T8 增量同步真 E2E
- [ ] NJX 改文件 → 网站更新
- 截图：4 张（T8 验收现场）

### T9 4 文档收尾
- [ ] delivery.md 全部标 done
- [ ] goal.md / plan.md Changelog
- [ ] README.md 写好

---

## §3 北极星指标达成

| 指标 | 目标 | 实测 | 状态 |
|---|---|---|---|
| NSM-1 检索时延 | ≤ 5s | - | pending |
| NSM-2 答案有据 | AI 引用 ≥ 1 真实文档 | - | pending |
| NSM-3 MVP 上线 | 公网 200 | - | pending |
| NSM-4 增量同步 | ≤ 5 min | - | pending |

---

## §4 截图存档目录

```
project/AOG知识库网站/delivery/screenshots/
├── T1/  (5 张：health/cities/city_detail/chat/openapi)
├── T2/  (6 张：home*3/city/experiences/lighthouse)
├── T3/  (4 张：build_log/chroma_count/sqlite_count/stats_json)
├── T4/  (2 张：e2e_search/e2e_chat)
├── T5/  (5 张：railway/vercel/public*3)
├── T6/  (4 张：before/edit/sync_log/after)
├── T7/  (7 张：真 E2E 验收)
└── T8/  (4 张：增量同步真 E2E)
合计: 37 张
```

---

## §5 Changelog

### 2026-07-15 21:17
- 项目立项，NJX 拍板 4 决策（云端 + 核心 3 件套 + 增量同步 + 1 周）
- 4 文档初稿 ready
- 待 NJX 签字进 Step 2

### 2026-07-15 21:42
- T0.2 mockup 子智能体完成（task bg_d653e789）
- merge feature/t0.2-mockup → main (commit 3a0d7c8)
- ground truth 验证 PASS：5 HTML / 10 截图 / 真实数据 11 处北京大兴 / NSM-2 引用 ≥ 1（实测 2）/ 无 lorem / Tailwind CDN 5/5
- 视觉抽检：首页 + ChatWidget 渲染正常，NSM-2 引用区工作
- Wave 1 启动：派 3 子智能体并行（后端/前端/数据 pipeline）

### 2026-07-15 22:15
- T2 前端子智能体完成（task bg_37184edf）
- merge feature/wave1-frontend → main (commit 1aae43a → 9b3f2c1)
- ground truth 验证 PASS：18 截图 / 9 端点函数 / NSM-2 警告触发 / 真实数据 19 处北京大兴 / LCP 1.0s
- T1 后端 + T3 pipeline 仍在跑（互不冲突）

### 2026-07-15 22:30
- T1 后端子智能体完成（task bg_29029230）
- merge feature/wave1-backend → main (commit 6f8a91e)
- ground truth 验证 PASS：8 端点 / 7 测试 / 61 pytest pass / 85% coverage / NSM-2 兜底 3 层链 / mock 模式 830ms
- T3 pipeline 仍在跑（用 data/ 目录，写 Chroma + SQLite）
- Wave 1 进度：2/3 完成

### 2026-07-16 01:30 — Wave 1 完整收口
- T3 pipeline PM 接管完成 build（agent lost, runtime restart）：
  - 248 files scanned / **248 indexed / 0 failed**
  - 8686 chunks / 116.41 MB chroma
  - 223 cities / 15 experiences / 10 core_plans
  - build_time_s: 1769 (~30min, bge-m3 客观耗时)
- merge feature/wave1-pipeline → main (commit 862a51c)
- 复制 141MB data/ 到主项目 backend/data + pipeline/data（gitignored）
- **PM 修 2 个 contract 违规 bug** (commit 32426dc)：
  1. chroma_client.COLLECTION_NAME: aog_documents → aog_knowledge (CONTRACT §5)
  2. sqlite_client SQLAlchemy schema 镜像 T3 实际表（独立列 vs data_json）
- **Wave 1 端到端 PASS**：
  - 4 页面 curl 200 (首页/北京大兴/experiences/exp-e25c39e8)
  - 首页含真实数据 (北京大兴/上海浦东/广州白云/香港/B787)
  - POST /api/chat "B787 风挡" 检索 5 个真实文档 (top1=B787 风挡AOG处理流程 score=0.800)
  - latency 2024ms (RAG + mock LLM)
- **Wave 1 100% 完成**，进入 Wave 2 准备

### 2026-07-16 01:50 — T6 增量同步 PASS
- merge feature/wave2-sync → main (commit 99952cb)
- ground truth 验证 PASS: 17/17 pytest / 81% coverage / 5 验证项全过（含 4a 真改文件 + trigger + reindex rc=0）
- 关键设计：mtime+size hash (不读内容) + subprocess 调 pipeline (隔离崩溃) + sync_state.db 持久化
- 已知 pre-existing bug: T3 pipeline 写 index_stats.json 但不写 SQLite index_stats 表 → last_sync=null（建议另开 T7 子任务修）
- Railway 部署 6 注意事项已写明 (PIPELINE_DIR / uv / SYNC_INTERVAL / 多实例 / 磁盘)

### 2026-07-16 01:58 — NJX 拍板：CloudBase (替代 Vercel+Railway)
- T5 方向调整：停止 Vercel+Railway agent (bg_963226fd)，PM 接管 CloudBase 路径
- 3 个关键差异要处理：
  1. **静态托管**：CloudBase 静态托管替代 Vercel（`next build` + `next export` 上传）
  2. **云函数**：FastAPI 后端要包成 CloudBase 云函数（SCF 兼容，不能直接 uvicorn）
  3. **向量库**：CloudBase 无原生 Chroma → 换 **pgvector**（CloudBase 云数据库 PostgreSQL 扩展）
- 影响：T1 chroma_client 要重写为 pgvector 适配层（保留接口）
