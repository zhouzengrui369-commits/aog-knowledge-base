# AOG AI 知识库网站 · 规则（rules.md）

> 项目: AOG AI 知识库网站
> PM: Mavis (mavis)
> 最后更新: 2026-07-15

---

## §1 PM 守则（继承自 project-pm skill §0.6）

> **本节优先级最高**，任何 PM / sub-agent 行为与本节冲突 = 错误。

### 1.1 PM 只做 3 件事
1. 写 / 改 / 迭代 goal.md / plan.md / rules.md / delivery.md
2. 向子智能体派发任务（prompt 内嵌「基线项编号 + 验收口径 + 禁红线」）
3. 验收（真机 + 截图 + 对照基线 + 标 done/reject）

### 1.2 PM 禁止做
- ❌ 写业务代码（PM = 调度者）
- ❌ 跑产品命令做 demo（让 sub-agent 跑，PM 只验收）
- ❌ 替 sub-agent 做它的活
- ❌ 弹窗 NJX 当路由器「选 A 还是 B」

### 1.3 PM 自主推进铁律
- NJX 沉默 ≤ 30min = 自动授权
- 基线对应项派发 = PM 自主
- 弹窗 NJX = 仅 2 条件：基线达成 / 死循环（5 次同 task 同 response）

### 1.4 30s 三件套
任何派发 / 验收前必跑：
```bash
pwd && ls -la /Users/njx/Project/AOG知识库/project/AOG知识库网站/
git -C /Users/njx/Project/AOG知识库 rev-parse --abbrev-ref HEAD
git -C /Users/njx/Project/AOG知识库 status --short
```

### 1.5 60s 验收清单
worker done → 60s 内必过 7 项：
- [ ] 30s 三件套
- [ ] 读 goal.md / plan.md / current-goal
- [ ] 基线对应项判别
- [ ] 派发 prompt 含「基线项 + 验收口径 + 禁红线 + 时间预算」
- [ ] ground truth 验证（state.json / curl 200 / 文件 mtime+size / 截图）
- [ ] PASS → 自主进下一项
- [ ] FAIL → 自主 steer ≤ 2 次，2 次后仍 FAIL = 死循环计数

---

## §2 团队规则（子智能体必读）

### 2.1 并行规则
- T1 / T2 / T3 用 git worktree 隔离，路径：
  - `worktrees/backend/`
  - `worktrees/frontend/`
  - `worktrees/pipeline/`
- 各 worktree 独立 commit，PM 统一 merge
- 冲突解决：先到先得，PM 仲裁

### 2.2 API 契约（`aog-web/CONTRACT.md`）
- 所有 API 端点 / Request / Response schema 由 PM 预先定义
- 子智能体**不修改** CONTRACT.md，有歧义先问 PM
- OpenAPI 自动生成在 `http://localhost:8000/docs`

### 2.3 代码规范
- **Python**（后端 + pipeline）：
  - PEP 8 + type hints
  - `pyproject.toml` 配 ruff + mypy
  - 测试用 pytest，coverage ≥ 60%
- **TypeScript**（前端）：
  - ESLint + Prettier
  - 函数组件 + hooks
  - 不用 class 组件
- **依赖锁定**：
  - Python: `uv lock`
  - Node: `pnpm-lock.yaml`

### 2.4 Commit 规范
```
<type>(<scope>): <subject>

<body>

Refs: T-X.Y
```
- type: feat / fix / docs / refactor / test / chore
- scope: backend / frontend / pipeline / docs
- subject: ≤ 50 字，祈使句

### 2.5 文件命名
- 源代码：`snake_case.py` / `kebab-case.tsx`
- 文档：`kebab-case.md`
- 截图：`T-{task}-{step}.png`（存 `delivery/screenshots/`）

### 2.6 文档同步
- 任何 API 变更 → 同步更新 CONTRACT.md
- 任何部署变更 → 同步更新 plan.md §7
- 任何验收项变更 → 同步更新 delivery.md

---

## §3 禁红线（违反 = 任务重做）

| ID | 禁红线 | 原因 |
|---|---|---|
| R1 | ❌ mock 数据 / fail-soft CI / 脚本演示作为发布证据 | Vibe Coding 0.7.5 真 E2E |
| R2 | ❌ PM 自己写业务代码 | §1.1 PM 只调度 |
| R3 | ❌ 跳过截图验收 | delivery.md 强制要求 |
| R4 | ❌ 改动 `AOG知识库/` 任何原文件 | 知识库是只读数据源 |
| R5 | ❌ 用 `rm -rf` 删代码目录 | mavis-trash 代替 |
| R6 | ❌ commit 包含 `.env` / API key | 凭证泄露 |
| R7 | ❌ 不读 CONTRACT.md 自创端点 | 前后端集成失败 |
| R8 | ❌ 验收前不跑 30s 三件套 | 错前提决策 |
| R9 | ❌ 后端启动后不 curl 验证 200 | exit 0 ≠ 真活 |
| R10 | ❌ AI 对话回答不引用真实文档 | NSM-2 不达标 |

---

## §4 验收口径

### 4.1 后端 task（T1）验收
- [ ] `uvicorn aog_web.main:app --port 8000` 启动成功
- [ ] `curl http://localhost:8000/api/health` 返回 `{"status":"ok"}`
- [ ] `curl http://localhost:8000/api/cities | jq 'length'` ≥ 200
- [ ] `curl http://localhost:8000/api/city/B-北京大兴` 返回完整预案 md 文本
- [ ] `curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"q":"B787 风挡 AOG"}'` 返回 AI 回答 + 引用
- [ ] pytest 全绿，coverage ≥ 60%
- [ ] OpenAPI /docs 可访问

### 4.2 前端 task（T2）验收
- [ ] `pnpm dev` 启动，`curl http://localhost:3000` 返回 200
- [ ] 首页含搜索框 + 字母导航
- [ ] `/city/B-北京大兴` 渲染（先 mock）
- [ ] `/experiences` 列表 18 个
- [ ] Lighthouse desktop 性能 ≥ 80 / 移动 ≥ 60
- [ ] 响应式截图 3 张（桌面 / 平板 / 手机）

### 4.3 数据 pipeline task（T3）验收
- [ ] `python -m pipeline.build_index` exit 0
- [ ] Chroma 集合 doc 数量 ≥ 500
- [ ] SQLite cities 表 ≥ 220 行
- [ ] SQLite experiences 表 ≥ 18 行
- [ ] 跑一次 build 耗时 < 10 min
- [ ] 生成的 `data/index_stats.json` 记录：build_time / num_chunks / chroma_size_mb

### 4.4 部署 task（T5）验收
- [ ] Railway dashboard 服务在线
- [ ] Vercel dashboard build 成功
- [ ] 公网 URL 首页 200
- [ ] 公网 URL 三大功能全通
- [ ] dashboard 截图存档 `delivery/screenshots/T5/`

### 4.5 增量同步 task（T6）验收
- [ ] 改 1 个文件 → 等 ≤ 5min → 检索新内容出现
- [ ] `/api/sync/status` 返回 last_sync_time + queue
- [ ] Railway 日志显示 polling 跑通

### 4.6 真 E2E 验收（T7-T8）
- [ ] 7 张真机截图（首页/搜索/详情/经验/AI 对话/回答）
- [ ] 4 张增量同步截图（改前/改中/同步日志/改后）
- [ ] 全部存 `delivery/screenshots/`

---

## §5 持续运行规则

- **cron**: 暂不设（v1 不需要自动 cron）
- **monitoring**: Railway / Vercel dashboard 内置
- **backups**: SQLite 每周手动 dump（Phase 2 加自动）
- **logs**: 后端 stdout（Railway 自动收集）

---

## §6 关联

- `goal.md` — 项目目标
- `plan.md` — 任务拆解
- `delivery.md` — 验收清单
- project-pm skill §0.6 — PM 守则来源
