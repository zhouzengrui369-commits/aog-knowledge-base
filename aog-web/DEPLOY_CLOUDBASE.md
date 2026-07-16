# AOG AI 知识库 · CloudBase 部署 SOP

> 适用: Wave 2 · T5 (CloudBase Run 容器 + COS 持久化 + 静态托管)
> 写者: PM (mavis) / T5 子智能体
> 截止: 2026-07-23
> 状态: **配置 + 脚本就绪, 待 NJX 实际 deploy**

---

## §0 为什么用 CloudBase (不是 Vercel + Railway)

NJX 2026-07-16 01:58 拍板的取舍:

| 方案 | 优势 | 劣势 | 是否选 |
|------|------|------|--------|
| Vercel + Railway | 全套英文文档, GitHub 集成 | 跨 GFW 偶尔抽风, 两套账单 | ✗ |
| 腾讯云 CloudBase (一站) | 国内访问快, 一套账单, COS/Run 同账号 | 文档英文少, 生态比 Vercel 弱 | ✓ |
| 阿里云 SAE | 阿里云生态 | 没用过, 学习成本 | ✗ |
| 自建 K8s (ACK) | 完全控制 | NJX 一个人扛, 运维太重 | ✗ |

CloudBase = 腾讯云的 BaaS 平台, 一个账号 = Run 容器 + COS 对象存储 + 静态托管 + 云函数 (这次不用) + 数据库 (这次不用).

---

## §1 部署架构图

```
                       NJX 浏览器 (Chrome/Safari)
                                  │
                                  ▼
                ┌────────────────────────────────────┐
                │  CloudBase 静态托管 (Next.js 静态产物)│
                │  域名: https://aog.njx.com           │
                │       (或 https://<envId>.app.tcloudbase.com)│
                └────────────────────────────────────┘
                                  │
                                  │  fetch /api/chat  /api/cities ...
                                  ▼
                ┌────────────────────────────────────┐
                │  CloudBase Run 容器 (FastAPI)       │
                │  镜像: aog-web-backend:latest        │
                │  端口: 8000 (CloudBase Run 注入 $PORT)│
                │  资源: 1 CPU / 2Gi RAM               │
                │  入口: python -m aog_web.scripts.migrate_and_start│
                └────────────────────────────────────┘
                          │                       │
                          │ 读 ./data/chroma/      │ 读 ./data/aog.db
                          ▼                       ▼
                ┌────────────────────────────────────┐
                │  CloudBase COS 桶 (aog-prod-data-7gxxx)│
                │  挂载到 /app/aog-web/backend/data    │
                │  内含: chroma/ + aog.db + sync_state.db│
                └────────────────────────────────────┘
                          ▲
                          │  上传 (本地 build_index 完成后)
                          │
                ┌────────────────────────────────────┐
                │  NJX 本地 macOS                      │
                │  uv run python -m pipeline.build_index│
                │  uv run python tools/sync_to_cos.py  │
                └────────────────────────────────────┘
```

**冷启动流程** (CloudBase Run 容器实例):
1. 新实例从镜像启动 → 跑 `migrate_and_start.py`
2. 检测本地 `./data/` 空 → 调 `download_data_from_cos()`
3. 从 COS 下载 chroma/ (约 50MB) + aog.db (~5MB) + sync_state.db
4. 下载完成 → uvicorn 启动 FastAPI → 服务可用
5. 冷启动总耗时: **~30s** (含 COS 下载) / **~3s** (本地已有, warm start)

---

## §2 前置 (NJX 一次性准备)

### 2.1 腾讯云账号

- [ ] 腾讯云账号 (用 NJX 自己的微信/QQ 注册, 已实名认证)
- [ ] 开通 CloudBase: https://console.cloud.tencent.com/tcb
- [ ] 开通 COS: https://console.cloud.tencent.com/cos (如果没自动开通)

### 2.2 域名 (可选, 强烈推荐)

- [ ] 备案域名 (e.g. `aog.njx.com`) — 国内服务器必须 ICP 备案, ~7-15 天
  - 备案入口: https://console.cloud.tencent.com/beian
  - 没有域名时, 用 CloudBase 临时域名 `<envId>.app.tcloudbase.com` (够 MVP 演示)
- [ ] DNS 解析到 CloudBase (CloudBase 控制台给 CNAME, 复制到 DNSPod)

### 2.3 工具 (本机)

- [ ] `tcb` CLI: `npm install -g @cloudbase/cli` (或直接用控制台, 不用 CLI)
- [ ] Docker Desktop (本地 build 镜像用, 容器跑不跑无所谓)

### 2.4 凭证准备

NJX 需要准备 4 样东西, **不要 commit 到 git**:

| 名称 | 来源 | 用途 |
|------|------|------|
| `envId` | CloudBase 控制台 → 环境概览 | 部署目标环境 |
| `COS_BUCKET` | COS 控制台 → 桶列表 → 创建新桶 | 数据持久化桶名 |
| `COS_SECRET_ID` | CAM 控制台 → 用户 → API 密钥 | 读写 COS |
| `COS_SECRET_KEY` | 同上 | 读写 COS |

> **最小权限原则**: CAM 子账号只授权 `QcloudCOSFullAccess` 给特定桶, 不给主账号密钥.

---

## §3 步骤 1 — 创建 CloudBase 环境

### 3.1 创建环境

```
1. 登录 https://console.cloud.tencent.com/tcb
2. 点击 "新建环境"
3. 填写:
   - 环境名称: aog-prod
   - 计费模式: 按量付费 (推荐, 新户有 1 个月免费额度)
   - 区域: 上海 (ap-shanghai) - 跟 COS 桶同区, 走内网
4. 等待创建完成 (~2min)
5. 在 "环境概览" 页面记录 envId (形如 aog-prod-7gxxxxxxxx)
```

### 3.2 创建 COS 桶

```
1. 登录 https://console.cloud.tencent.com/cos
2. 点击 "创建桶"
3. 填写:
   - 名称: aog-prod-data-7gxxxxxxxx (跟 envId 配套, 一眼认)
   - 地域: 上海 (ap-shanghai) ★ 必须跟 CloudBase 同区
   - 访问权限: 私有读写 (不要公共读, 里面有 chroma 数据)
   - 其他默认
4. 创建完成后, 在桶列表点开 → 记录桶名
```

### 3.3 把 COS 桶挂到 CloudBase Run 容器

这一步在 **步骤 2 创建容器时一起配** (在 cloudbaserc.json mounts 字段), 不需要单独操作.

---

## §4 步骤 2 — 后端 CloudBase Run 部署

### 4.1 构建镜像 (本地 macOS)

```bash
cd /Users/njx/Project/AOG知识库/worktrees/cloudbase

# 1. build 后端镜像
docker build \
  -f aog-web/aog-web-backend.Dockerfile \
  -t aog-web-backend:latest \
  -t aog-web-backend:$(git rev-parse --short HEAD) \
  .

# 2. 验证镜像 (可选)
docker run --rm -p 8000:8000 \
  -e MINIMAX_API_KEY=__test__ \
  -e COS_BUCKET=test-bucket \
  -e COS_SECRET_ID=AKIDtest \
  -e COS_SECRET_KEY=test \
  aog-web-backend:latest \
  echo "image boots OK"
```

> **build 加速技巧**: 第一次 build ~3min, 改代码后增量 build ~10s (uv layer + code layer 分离).

### 4.2 push 镜像到 TCR 或 CloudBase Run

CloudBase Run 支持 2 种镜像来源:

| 方式 | 操作 | 适用 |
|------|------|------|
| 推送到 TCR (腾讯云镜像仓库) | `docker push ccr.ccs.tencentyun.com/aog-prod/aog-web-backend:v1` | 团队多人 |
| CloudBase Run 直接 build (上传 Dockerfile) | CloudBase 控制台 → 容器服务 → 上传代码 | 个人项目, 这次用这个 |

**推荐 (这次用)**: CloudBase Run "直接 build" 模式, 不用单独管 TCR.

### 4.3 CloudBase Run 控制台操作

```
1. 登录 https://console.cloud.tencent.com/tcb → 进入 aog-prod 环境
2. 左侧菜单 → 容器服务 → 点击 "新建服务"
3. 配置:
   - 服务名: aog-web-backend
   - 镜像: 选择 "本地构建" → 上传 aog-web-backend.Dockerfile + aog-web/backend/ 目录
   - 端口: 8000
   - 启动命令: python -m aog_web.scripts.migrate_and_start
   - 资源配置: 1 CPU / 2Gi RAM
4. 环境变量 (按 .env.cloudbase.example 填, 真实值):
   MINIMAX_API_KEY=<NJX 填>
   MINIMAX_BASE_URL=https://api.MiniMax.chat/v1
   MINIMAX_MODEL=minimax-m3
   CHROMA_PATH=/app/aog-web/backend/data/chroma
   SQLITE_PATH=/app/aog-web/backend/data/aog.db
   SYNC_STATE_DB_PATH=/app/aog-web/backend/data/sync_state.db
   COS_BUCKET=aog-prod-data-7gxxxxxxxx
   COS_REGION=ap-shanghai
   COS_SECRET_ID=<NJX 填>
   COS_SECRET_KEY=<NJX 填>
   KNOWLEDGE_BASE_PATH=/app/data/AOG知识库
   RAW_PATH=/app/data/RAW
   SYNC_ENABLED=false
   SYNC_INTERVAL_S=300
   LOG_LEVEL=INFO
   CORS_ALLOW_ORIGINS=https://aog.njx.com,https://<envId>.app.tcloudbase.com
   PORT=8000
   PYTHONUNBUFFERED=1
5. 挂载 COS 桶:
   - 名称: aog-data
   - 挂载路径: /app/aog-web/backend/data
   - 来源: COS 桶 aog-prod-data-7gxxxxxxxx
6. 弹性策略: 最小 0 实例 (省钱, 冷启动 30s 用户可接受) / 最大 3 实例
7. 点击 "创建并部署" → 等待 build + deploy (~5min)
```

### 4.4 健康检查

部署完成后, CloudBase Run 会给一个默认域名 `<service-name>.<envId>.app.tcloudbase.com`.

```bash
# 1. 健康检查
curl https://aog-web-backend.aog-prod-7gxxx.app.tcloudbase.com/api/health
# 期望: {"status":"ok","version":"1.0.0","uptime_s":42}

# 2. 城市列表
curl https://aog-web-backend.aog-prod-7gxxx.app.tcloudbase.com/api/cities | jq length
# 期望: >= 220

# 3. AI 问答
curl -X POST https://aog-web-backend.aog-prod-7gxxx.app.tcloudbase.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"q":"B787 风挡"}' | jq '.references | length'
# 期望: >= 1
```

**如果 city 数量为 0 或 chat 报 "no references"**: COS 下载失败, 看 CloudBase Run 日志 (步骤 7 监控).

---

## §5 步骤 3 — 前端 CloudBase 静态托管

### 5.1 本地 build (NJX 在 macOS 跑)

```bash
cd /Users/njx/Project/AOG知识库/worktrees/cloudbase/aog-web/frontend

# build 时注入后端 API 地址 (替换为 CloudBase Run 实际域名)
export NEXT_PUBLIC_API_BASE=https://aog-web-backend.aog-prod-7gxxx.app.tcloudbase.com
pnpm install
pnpm build
# 产物在 .next/ 和 out/ (或 .next/static/ + public/)
```

### 5.2 上传到 CloudBase 静态托管

**方式 A (推荐)**: 用 tcb CLI

```bash
npm install -g @cloudbase/cli
tcb login
tcb hosting deploy .next aog-web-frontend
# 或: tcb hosting deploy ./out aog-web-frontend
```

**方式 B**: CloudBase 控制台

```
1. 左侧菜单 → 静态网站托管
2. 点击 "上传文件" → 选 .next/ 整个目录
3. 默认域名: https://aog-web-frontend-<envId>.app.tcloudbase.com
```

### 5.3 绑定自定义域名 (可选)

```
1. 静态网站托管 → 域名管理 → 添加域名
2. 填 aog.njx.com
3. CNAME 解析到 控制台给的 cname.xxx.app.tcloudbase.com
4. SSL 证书: CloudBase 自动签, 等 10-30min
```

### 5.4 验证

```bash
curl https://aog.njx.com
# 期望: HTML 含 "AOG" 关键字

# 浏览器打开 → ChatWidget 提问 "B787" → 应答 200 + 引用 ≥ 1
```

---

## §6 步骤 4 — 数据同步流程 (NJX 日常操作)

> 这是 NJX 重建索引后的标准流程, 1-2min 跑完.

### 6.1 本地 build_index 重建

```bash
cd /Users/njx/Project/AOG知识库/worktrees/cloudbase

# 触发全量重建 (改动 AOG知识库/ 后必跑)
cd aog-web
uv run --project pipeline python -m pipeline.build_index
# 跑完输出: data/index_stats.json + 8686 chunks
```

### 6.2 上传 COS

```bash
# 凭证通过环境变量提供, 永远不写进文件
export COS_BUCKET="aog-prod-data-7gxxxxxxxx"
export COS_REGION="ap-shanghai"
export COS_SECRET_ID="AKIDxxx"
export COS_SECRET_KEY="xxx"

cd aog-web
uv run --project backend python tools/sync_to_cos.py

# 输出示例:
#   UPLOADED (52428800 bytes): chroma/chroma.sqlite3
#   UPLOADED (8388608 bytes): aog.db
#   UNCHANGED (4096 bytes): index_stats.json
# done. uploaded=2, skipped/unchanged=1
```

### 6.3 触发 CloudBase Run 容器重启

CloudBase Run 容器是临时文件系统, **必须重启实例**才能让 migrate_and_start.py 检测到 COS 新数据 (本地 data/ 没数据, 自动下载).

```
方式 A: CloudBase 控制台 → 容器服务 → aog-web-backend → 滚动重启
方式 B: 等下次冷启动 (低峰期通常几分钟一次)
方式 C: tcb CLI: tcb run restart aog-web-backend
```

### 6.4 增量数据 (T6 同步状态)

注意: CloudBase Run **关闭了增量同步** (SYNC_ENABLED=false). 原因:
- 容器临时, 多实例并发 watcher 会冲突
- 增量数据是开发体验, 不是生产要求

生产数据更新 = 本地 build_index + sync_to_cos + 重启容器. 周期: NJX 手动触发 (MVP 阶段).

---

## §7 步骤 5 — 监控与日志

### 7.1 CloudBase Run 日志

```
控制台 → 容器服务 → aog-web-backend → 日志
```

关键日志 (migrate_and_start.py 输出的):

```
[boot] COS config: {'configured': True, 'bucket': 'aog-prod-data-7gxxx', ...}
[storage_cos] local data already exists, skip COS download (warm start)
# 或
[storage_cos] downloading from COS bucket=aog-prod-data-7gxxx region=ap-shanghai ...
[storage_cos] downloaded N files under chroma/
[boot] COS warmup done, first-boot data ready
AOG Web Backend ready.
```

异常日志:

```
[boot] COS warmup FAILED: NoSuchBucket  ← COS 桶名错
[boot] COS warmup FAILED: 403 Forbidden  ← 密钥权限不够
[storage_cos] failed to download chroma/x: AccessDenied  ← 同上
```

### 7.2 COS 访问日志

```
COS 控制台 → aog-prod-data-7gxxx → 日志管理 → 访问日志
可看 sync_to_cos.py 上传记录 + 容器下载记录
```

### 7.3 健康检查端点 (推荐加 /api/health 看 COS 状态)

后端已在 lifespan 里 log 了 chroma count / data 路径, 健康检查端点 `/api/health` 保持轻量.

如需把 COS 状态暴露给前端 (debug), 已在 `storage_cos.py` 提供 `describe_cos_config()`, PM 可选加到 health 响应.

---

## §8 回滚方案

### 8.1 镜像回滚

```
CloudBase 控制台 → 容器服务 → aog-web-backend → 版本列表
→ 选上一个版本 → 点击 "回滚到此版本"
```

### 8.2 数据回滚 (chroma 出问题)

```bash
# 1. 本地切到上一个 git commit 的 data/ (如果 NJX 把 data 备份到 git/外置)
cd /Users/njx/Project/AOG知识库/worktrees/cloudbase
git checkout HEAD~1 -- aog-web/backend/data/

# 2. 重新上传 COS
cd aog-web
uv run --project backend python tools/sync_to_cos.py --force

# 3. 重启 CloudBase Run 容器
```

更稳妥: NJX 在本地保留每次 build 的 data/ 备份 (e.g. `data.2026-07-16.bak/`), 出问题一键恢复.

### 8.3 配置回滚 (环境变量填错)

```
CloudBase 控制台 → 容器服务 → aog-web-backend → 环境变量
直接修改, CloudBase Run 会自动滚动重启
```

---

## §9 NJX 必填清单 (快速复述)

部署时 NJX 需要在 CloudBase 控制台填的:

| 字段 | 来源 | 示例 |
|------|------|------|
| CloudBase `envId` | 控制台环境概览 | `aog-prod-7gxxxxxxxx` |
| COS 桶名 | COS 控制台 | `aog-prod-data-7gxxxxxxxx` |
| `COS_SECRET_ID` | CAM → API 密钥 | `AKIDxxxxxxxx` |
| `COS_SECRET_KEY` | 同上 | `xxxxxxxx` (32 字符) |
| `MINIMAX_API_KEY` | MiniMax 控制台 | `sk-xxxxxxxx` |
| `CORS_ALLOW_ORIGINS` | 静态托管域名 | `https://aog.njx.com,https://<envId>.app.tcloudbase.com` |
| 静态托管绑定域名 | 备案后的域名 | `aog.njx.com` (需 ICP 备案) |

---

## §10 时间预算与里程碑

| 步骤 | 操作 | 耗时 | NJX 参与 |
|------|------|------|----------|
| 1 | 注册 CloudBase + 实名 + 备案 | 0.5-15 天 (备案最重) | 全程 |
| 2 | 创建环境 + COS 桶 | 5min | 一次性 |
| 3 | 本地 build 镜像 | 3-5min | 一次性 |
| 4 | CloudBase Run 部署 | 5min | 一次性 |
| 5 | 上传前端 + 绑域名 | 10min | 一次性 |
| 6 | 日常数据更新 (build_index + sync_to_cos) | 2-5min | 每次更新 |
| 7 | 监控 + 排错 | 持续 | 异常时 |

---

## §11 严禁 (红线)

执行期间 NJX 跟我都不能:

- ❌ **不直接 `tcb deploy`** — 镜像我已经 build 好, 部署动作 NJX 自己在控制台点 (留出 5min 审 "环境变量" + "挂载" 配置)
- ❌ **不 commit 真实 SecretId/Key** — 全部走控制台环境变量 / CAM 子账号
- ❌ **不触碰 `AOG知识库/` 源数据** — T3 pipeline 只读
- ❌ **不重写 chroma_client.py** — 现有 Chroma 持久化逻辑已经能跑, 没必要换 pgvector
- ❌ **不把 `data/` commit** — backend/data/ 在 .gitignore, 只有 COS 是 source of truth
- ❌ **不 merge 到 main** — feature/wave2-cloudbase 分支, PM merge

---

## §12 验收

- [ ] `/api/health` 返回 200
- [ ] `/api/cities` 返回 ≥ 220
- [ ] `/api/city/B-北京大兴` 返回 200 + 完整字段
- [ ] `/api/chat` 返回 200 + references.length ≥ 1
- [ ] 前端首页加载 < 3s
- [ ] ChatWidget 提问有真实回答 + 引用
- [ ] 域名访问正常 (如有备案)
- [ ] 关闭容器再开 → 30s 内自动恢复服务 (COS 预热)
