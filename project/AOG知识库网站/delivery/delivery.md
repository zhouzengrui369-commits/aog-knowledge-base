# AOG AI 知识库网站 · 交付（delivery.md）

> 项目: AOG AI 知识库网站
> PM: Mavis (mavis)
> 最后更新: 2026-07-15
> 截止: 2026-07-22

---

## §1 任务清单

| ID | 任务 | 状态 | 验收人 | 派发日期 | 完成日期 | 备注 |
|---|---|---|---|---|---|---|
| T1 | 后端骨架（FastAPI + Chroma + 解析器） | pending | sub-agent backend-agent | D2 | - | Wave 1 |
| T2 | 前端骨架（Next.js + 三大页面） | pending | sub-agent frontend-agent | D2 | - | Wave 1 |
| T3 | 数据 pipeline（解析 + 向量化） | pending | sub-agent data-agent | D2 | - | Wave 1 |
| T4 | 前后端集成 | pending | sub-agent integrator | D4 | - | Wave 2 |
| T5 | Railway + Vercel 部署 | pending | sub-agent devops-agent | D4-5 | - | Wave 2 |
| T6 | 增量同步（定时轮询 v1.1） | pending | sub-agent devops-agent | D5 | - | Wave 2 |
| T7 | 真机访问 + 截图 | pending | NJX (PM 验收) | D6 | - | Wave 3 |
| T8 | 增量同步验证 | pending | NJX (PM 验收) | D6 | - | Wave 3 |
| T9 | 4 文档收尾 | pending | PM | D7 | - | Wave 3 |

---

## §2 详细验收清单

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
