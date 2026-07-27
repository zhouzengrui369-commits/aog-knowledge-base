# AOG AI 知识库网站

> 项目: AOG (Aircraft On Ground) AI 知识库 — 航空公司维修 + 航材供应链数智化
> 阶段: Wave 2 · T5 CloudBase 部署配置 (PM 2026-07-16 拍板)
> 截止: 2026-07-23 MVP
> 生产环境: 腾讯云 CloudBase (Run 容器 + COS 持久化 + 静态托管)

---

## 🚀 部署链接 (部署后填)

| 入口 | URL |
|------|-----|
| 前端 (静态托管) | `https://aog.njx.com` (待部署) / `https://<envId>.app.tcloudbase.com` (临时) |
| 后端 API | `https://aog-web-backend.<envId>.app.tcloudbase.com` |
| 健康检查 | `https://aog-web-backend.<envId>.app.tcloudbase.com/api/health` |
| OpenAPI 文档 | `https://aog-web-backend.<envId>.app.tcloudbase.com/docs` |

**部署详细 SOP**: [DEPLOY_CLOUDBASE.md](./DEPLOY_CLOUDBASE.md)

---

## 🛠 本地开发 5 步

```bash
# 1. clone + 进 worktree
cd /Users/njx/Project/AOG知识库/worktrees/cloudbase

# 2. 后端依赖 (uv)
cd aog-web/backend
uv sync
cp .env.example .env  # 然后填 MINIMAX_API_KEY (没填也能跑, 用 Mock LLM)

# 3. 数据 (T3 pipeline 已经 build 过, 直接用; 没数据时跑)
cd ../pipeline
uv sync
uv run python -m pipeline.build_index    # 重建索引 (~3min)

# 4. 启后端
cd ../backend
uv run uvicorn aog_web.main:app --reload --port 8000
# → http://localhost:8000/api/health

# 5. 启前端 (新 terminal)
cd ../frontend
pnpm install
pnpm dev
# → http://localhost:3000
```

---

## 📦 项目结构

```
aog-web/
├── README.md                       # ← 本文件
├── DEPLOY_CLOUDBASE.md             # ← 部署 SOP
├── CONTRACT.md                     # API 契约 (PM 写, agent 读)
├── cloudbaserc.json                # CloudBase 主配置 (容器 + 静态托管)
├── .cloudbaserc                    # 用户级配置 (envId, 不 commit 真实)
├── aog-web-backend.Dockerfile      # 后端容器镜像
├── aog-web-frontend.Dockerfile     # 前端镜像 (可选, 推荐本地 build)
├── backend/                        # FastAPI + Chroma + SQLite
│   ├── aog_web/
│   │   ├── services/
│   │   │   ├── chroma_client.py    # T1 Chroma 检索
│   │   │   ├── sqlite_client.py    # T1 元数据
│   │   │   ├── llm.py              # T1 LLM 抽象
│   │   │   ├── sync.py             # T6 增量同步
│   │   │   └── storage_cos.py      # T5 COS 预热 (新增)
│   │   └── scripts/
│   │       └── migrate_and_start.py # T5 启动入口 (COS + uvicorn)
│   ├── .env.example
│   ├── .env.cloudbase.example      # T5 生产 env 模板 (新增)
│   └── pyproject.toml              # T5 加了 cos-python-sdk-v5
├── frontend/                       # Next.js 15 (T2)
├── pipeline/                       # T3 build_index.py
├── mockup/                         # T0.2 HTML 原型
└── tools/
    └── sync_to_cos.py              # T5 本地 → COS 上传 CLI (新增)
```

---

## 🔑 关键设计决策 (Wave 2 T5 拍板)

| 决策 | 选择 | 理由 |
|------|------|------|
| 部署平台 | 腾讯云 CloudBase (非 Vercel+Railway) | NJX 2026-07-16 拍板, 国内访问快 + 一套账单 |
| 后端形态 | CloudBase Run 容器 (非 SCF 云函数) | FastAPI 不用改, 跟本地 dev 一致 |
| 数据持久化 | CloudBase COS 桶 (非 pgvector) | 保留 T1 Chroma + T3 pipeline, 工作量最低 |
| 冷启动策略 | 容器启动时从 COS 下载 chroma + aog.db | 30s 一次冷启动, 用户可接受 |
| 增量同步 | **生产关闭** (SYNC_ENABLED=false) | 容器临时, 多实例并发会冲突 |
| 数据更新流程 | 本地 build_index → sync_to_cos → 重启容器 | NJX 手动触发, 周期 1-2 周 |
| 凭证管理 | 控制台环境变量 + CAM 子账号, 永不 commit | 最小权限原则 |
| 前端部署 | CloudBase 静态托管 (非容器) | 静态文件 + CDN 加速, 比容器便宜 10x |

---

## 📋 Wave 2 任务分工

- T1 (后端) — feature/wave1-backend ✓
- T2 (前端) — feature/wave1-frontend ✓
- T3 (数据 pipeline) — feature/wave1-pipeline ✓
- T4 (集成验证) — done 2026-07-15
- **T5 (CloudBase 部署) ← 当前 worktree** — feature/wave2-cloudbase
- T6 (增量同步) — done 2026-07-15

---

## ⚠️ 红线 (不要做)

- ❌ 不要 commit 真实 SecretId/Key (用控制台环境变量)
- ❌ 不要触碰 AOG知识库/ 或 RAW/ 源数据
- ❌ 不要重写 chroma_client.py (现有 Chroma 兼容 COS 路径)
- ❌ 不要 commit backend/data/ (在 .gitignore, COS 是 source of truth)
- ❌ 不要 merge 到 main (PM merge)

---

## 📚 相关文档

- [DEPLOY_CLOUDBASE.md](./DEPLOY_CLOUDBASE.md) — 部署 SOP (NJX 必读)
- [CONTRACT.md](./CONTRACT.md) — API 契约 (8 端点 + 4 数据模型)
- [../project/AOG知识库网站/goal.md](../project/AOG知识库网站/goal.md) — 北极星
- [../project/AOG知识库网站/PRD.md](../project/AOG知识库网站/PRD.md) — 产品需求
- [../project/AOG知识库网站/plan.md](../project/AOG知识库网站/plan.md) — Wave 1 任务
- [../project/AOG知识库网站/rules.md](../project/AOG知识库网站/rules.md) — 团队规则
- [../project/AOG知识库网站/delivery/delivery.md](../project/AOG知识库网站/delivery/delivery.md) — 验收清单

---

## 🔍 产品体验评审基线（独立验收）

> 本节由独立产品体验评审官线程维护，**不**修改产品代码、UI、文案、测试、数据或部署。

- 通用核心章程：[docs/acceptance/PRODUCT_EXPERIENCE_REVIEWER_CORE.md](../docs/acceptance/PRODUCT_EXPERIENCE_REVIEWER_CORE.md) · v1.0.0
- AOG 项目体验档案：[docs/acceptance/PRODUCT_EXPERIENCE_PROFILE.md](../docs/acceptance/PRODUCT_EXPERIENCE_PROFILE.md) · v1.0.0
- 评审报告目录：[reports/product-review/](../reports/product-review/)

最近一次评审：

- 报告：`reports/product-review/2026-07-26-aog-product-experience-review.md`
- 结论（独立盲测基线 V14 main）：`NOT_READY` · 6 P0 / 9 P1 / 平均 2.20/5

下一轮按整改优先级定向复验 P0（API 拼接收尾 / RAG 维度 / LLM key / SCF 重新部署）。
