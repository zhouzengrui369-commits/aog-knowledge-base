# AOG 系统架构 (ARCHITECTURE)

> **目的**: 记录当前系统架构和关键设计决策，新 AI 接手时能快速理解"为什么这么设计"。
> **维护**: 架构变更时更新。
> **最后更新**: 2026-07-26 by Mavis (PM)

---

## 🏗️ 系统总览

```
┌─────────────────────────────────────────────────────────┐
│  NJX Browser (localhost:3004 / 公网 tcloudbaseapp.com)  │
└─────────────┬───────────────────────────────────────────┘
              │ HTTPS
              ↓
┌─────────────────────────────────────────────────────────┐
│  Next.js 15 Frontend (React 19 + TypeScript)            │
│  ├─ Home (城市列表 + 字母导航 + 航司 tab)                │
│  ├─ WorldMapLeaflet (react-leaflet + OSM tile)         │
│  ├─ CityDetail (单城市预案详情)                          │
│  ├─ AuthGate (DISABLE_AUTH 跳过)                         │
│  └─ AIChat (MiniMax M3 + RAG)                            │
└─────────────┬───────────────────────────────────────────┘
              │ REST API (CORS)
              ↓
┌─────────────────────────────────────────────────────────┐
│  FastAPI Backend (uvicorn, Python 3.11)                 │
│  ├─ /api/health (健康检查)                              │
│  ├─ /api/cities (218 AOG 城市 + 6,072 全球机场)         │
│  ├─ /api/city/{code} (单城市详情)                        │
│  ├─ /api/airlines (25 航司 + base 城市)                  │
│  ├─ /api/auth/login (密码 + JWT 24h)                     │
│  └─ /api/chat (AI chat + RAG + 引用 ≥1 doc NSM-2 红线)  │
└─────────────┬───────────────────────────────────────────┘
              │ async SQLAlchemy 2.0
              ↓
┌─────────────────────────────────────────────────────────┐
│  Storage                                                  │
│  ├─ SQLite + FTS5 (trigram + BM25, 27MB)                 │
│  ├─ Chroma (116MB 向量索引)                              │
│  └─ CloudBase COS 持久化 (aog-prod-data-1343051603)     │
└─────────────────────────────────────────────────────────┘
              │ deploy
              ↓
┌─────────────────────────────────────────────────────────┐
│  Tencent CloudBase (CloudBase Run + 静态托管 + COS)     │
│  ├─ SCF Web Function (Python 3.11)                       │
│  ├─ 静态托管 (frontend/out → CDN)                        │
│  └─ COS Bucket (ap-shanghai)                             │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

### Frontend
- **Next.js 15** App Router + **TypeScript** + **Tailwind CSS** + **shadcn/ui**
- **react-leaflet 4.2.1 + leaflet 1.9.4**（V16 替代 react-simple-maps）
- **OSM tile**（不要 Mapbox 付费）
- **d3-geo + world-atlas + topojson-client + supercluster**（V28 218 城市聚合）
- **lucide-react**（icon 库）
- **framer-motion**（可选动画）

### Backend
- **FastAPI + uvicorn**（异步 Python Web 框架）
- **SQLAlchemy 2.0 async + aiosqlite**（异步 ORM）
- **FTS5**（SQLite 全文搜索，trigram + BM25）
- **PyJWT 2.8.0**（HS256 JWT 24h）
- **httpx**（异步 HTTP 客户端，AI 调 MiniMax M3）

### Storage
- **SQLite + FTS5**（27MB，知识片段全文索引）
- **Chroma**（116MB，向量索引，备选）
- **CloudBase COS**（生产持久化）

### LLM
- **MiniMax M3**（minimax 平台，OpenAI 兼容 API，包月）
- **NSM-2 红线**：AI chat 答案必须含 ≥ 1 个真实文档引用

### Tooling
- **uv**（Python 包管理）
- **pnpm**（Node 包管理）
- **tcb CLI 3.6.2**（CloudBase 部署，Node 24）
- **tencentcloud-sdk-python**（SCF SDK）
- **cos-python-sdk-v5**（COS SDK）
- **Playwright**（chromium headless 自动化验证）
- **gh CLI 3.x**（GitHub CLI，已登录 `zhouzengrui369-commits`）

### Deploy
- **SCF Web Function**（Python 3.11）+ **CloudBase 静态托管**（前端）+ **COS 持久化**
- GitHub: `zhouzengrui369-commits/aog-knowledge-base` (public, 49+ commits)

---

## 📂 代码结构

```
aog-web/
├── frontend/                     # Next.js 前端
│   ├── app/
│   │   ├── globals.css          # Tailwind + 地图 tooltip 样式
│   │   ├── home-data.tsx        # 城市列表 + 字母导航 (主入口)
│   │   └── page.tsx             # 首页
│   ├── components/
│   │   ├── world-map-leaflet.tsx  # 🗺️ 核心 UI (V28b 治本)
│   │   ├── alphabet-nav.tsx    # 字母导航 + 航司 tab
│   │   ├── airline-hub-badge.tsx # 航司 hub 紫环 + 数字徽章
│   │   ├── airline-hub-panel.tsx # 航司 hub 右侧 panel
│   │   └── city-detail-client.tsx # 城市详情 client
│   ├── lib/
│   │   ├── city-stats.ts        # 城市静态数据 (lat/lon + view_count)
│   │   ├── city-stats.json     # 218 城市 coords + 24 城市 view_count
│   │   ├── types.ts             # TypeScript 类型
│   │   └── utils.ts             # 工具函数
│   └── public/
│       └── data/global-airports.json # OpenFlights 6,072 机场
│
├── backend/                     # FastAPI 后端
│   ├── main.py                  # FastAPI app + routers
│   ├── routers/
│   │   ├── cities.py            # /api/cities + /api/city/{code}
│   │   ├── airlines.py          # /api/airlines
│   │   ├── auth.py              # /api/auth/login
│   │   └── chat.py              # /api/chat (RAG)
│   ├── data/
│   │   ├── aog.db               # SQLite 主库
│   │   ├── fts5_index.db        # FTS5 全文索引
│   │   └── chroma/              # Chroma 向量索引
│   └── .env                     # 环境变量
│
├── functions/aog-api/           # SCF 部署副本
│   └── aog_web/                 # 跟 backend/ 镜像（不被 git 追踪）
│
├── pipeline/                    # 数据 pipeline
│   ├── data/
│   │   └── AOG知识库/RAW/       # 原始 docx 文件 (read-only)
│   └── scripts/                 # docx 解析 + ETL
│
├── docs/                        # 📚 文档（本目录）
│   └── ARCHITECTURE.md          # 本文件
│
├── STATUS.md                    # 当前状态快照
├── TODO.md                      # 待办事项
├── CHANGELOG.md                 # 修改历史
├── DECISIONS.md                 # 重大决策
├── README.md                    # 项目入口
└── DEPLOY_CLOUDBASE.md          # CloudBase 部署 SOP
```

---

## 🎯 关键设计决策

### 1. Next.js 15 + React 19 + react-leaflet 4.2.1

- **V16 决策** (NJX 拍 🅰️)：用 react-leaflet 替换 react-simple-maps
- **理由**：react-simple-maps 渲染静态 SVG，OSM tile 不可用。react-leaflet 渲染真实 OSM tile，可交互
- **风险**：react-leaflet 内部用 React 17 API，React 19 strict mode 报错
- **workaround**：`dynamic({ssr: false})` + 重启 dev

### 2. 地图颜色分层（V26 治本）

- **V18-V25 治标方向错**：一直调灰色深度（#9ca3af → #4b5563 + fillOpacity 0.65→0.95 + 白边 1.5px）
- **V26 治本**：6,072 没预案 = 灰小点（背景），218 有预案 = 彩色（主视觉）
- **原则**：重要的彩色，次要的灰，不要全灰

### 3. supercluster 数字聚合（V28 治本）

- **V27 治标**：zoom 5 全部 218 label 渲染，100+ 城市挤一起重叠
- **V28 治本**：218 城市走 supercluster，zoom 5-7 数字聚合，zoom 8 全散开
- **V28b**：radius 50→80（聚合更狠，治本 "5.0 还是有点挤"）

### 4. V13 治本：城市文件名 URL 编码 → 真实中文

- **问题**：Next.js `output: export` 把中文 URL 编码，CloudBase 找不到 raw 中文 file
- **修法**：postbuild.sh 遍历 `out/city/`，把 `A-%E9%98%BF%E6%A0%BC.html` rename 成 `A-阿姆斯特丹（暂停）.html`

### 5. V14 治本：地图 click 直跳 + client render 防御性

- **问题 A**：`world-map.tsx` 强制 `code.toLowerCase()` → 地图 click 走 lowercase URL → 404
- **问题 B**：SCF API `phone` 是 `string[]` 不是 `string` → client-side "Application error"
- **修法**：4 处 `.toLowerCase()` 删除 + client render try/catch wrap + `Array.isArray()` 兼容

### 6. Sprint A：密码 + JWT 24h + AuthGate

- **NJX 拍 🅰️**：SCF 后端鉴权（不用客户端 JS 简单验证）
- **实施**：密码 `13456789` + PyJWT 2.8.0 HS256 24h + 前端 AuthGate 拦截
- **V18 dev 跳过**：`NEXT_PUBLIC_DISABLE_AUTH=1` 早期 return children

### 7. Sprint C：25 航司 + /api/airlines

- **NJX 拍 🅰️**：本地扒 20+ 航司 + /api/airlines endpoint
- **实施**：民航局 + 维基 + 各航司官网扒 25 航司（CA 国航/MU 东航/CZ 南航等），含 base 城市
- **V18 dev 跳过**：dev backend 用 MOCK

### 8. CloudBase 部署架构

- **前端**：Next.js static export → `out/` → CloudBase 静态托管
- **后端**：FastAPI → 打包到 `functions/aog-api/` → SCF Web Function (Python 3.11)
- **持久化**：SQLite + FTS5 + Chroma → COS Bucket `aog-prod-data-1343051603`
- **冷启动**：SCF 30s 冷启动（用 SCF Web 函数 + COS 持久化避免重复加载）

### 9. NSM-2 红线：AI chat 必须含 ≥ 1 真实文档引用

- **原因**：避免 LLM 幻觉，保护 NJX 业务可靠性
- **实施**：RAG 检索 top-k 文档，prompt 强制要求引用至少 1 个文档
- **验证**：Playwright 测 chat 响应必须含 `references` 字段

### 10. macOS + dev 环境的特殊性

- **APFS case-insensitive**：A-澳门.html + a-澳门.html 不能共存，V13 真实中文 file 名治本
- **TCC EPERM**：LaunchAgent 写 NAS 报 EPERM，1 天 MVP 别碰 LaunchAgent + 写盘
- **Vite error overlay**：Next.js 15 + React 19 + leaflet 已知问题，dev only，restart works

---

## 🔧 关键代码路径

### 地图核心：`frontend/components/world-map-leaflet.tsx`

- 1590 行（V28b 治本后）
- 关键函数：
  - `WorldMapLeaflet` (主组件, line 660)
  - `CityDot` (单城市 marker, line 230)
  - `ClusterMarker` (supercluster 数字 bubble, line 620)
  - `AirlineHubBadge` (航司 hub 紫环, line 385)
  - `AirlineHubPanel` (航司 hub 右侧 panel)
- 关键状态：
  - `zoom` (1-8, V28 maxZoom 7 supercluster)
  - `tier` (1-3 by zoom, V26 改默认 5 = tier 3)
  - `aogCluster` (V28 218 城市 supercluster, radius 80)
  - `globalClusterFeatures` (V20 6,072 全球机场 supercluster)
  - `airlineHubsByCity` (Sprint C 25 航司 base 城市)

### 后端核心：`backend/main.py`

- FastAPI app + 5 routers
- 关键 endpoint：
  - `GET /api/health` - 健康检查
  - `GET /api/cities` - 218 城市 + 6,072 全球机场
  - `GET /api/city/{code}` - 单城市详情
  - `GET /api/airlines` - 25 航司
  - `POST /api/auth/login` - 密码 + JWT
  - `POST /api/chat` - AI chat + RAG

### 数据 pipeline：`pipeline/scripts/`

- 原始数据：`/Users/njx/Project/AOG知识库/AOG知识库/RAW/` (read-only)
- docx 解析 + ETL → SQLite + FTS5 + Chroma
- 关键：FTS5 trigram + BM25 混合查询

---

## 🌍 部署架构

### 本地 dev
- 前端: `pnpm dev --port 3004` (Next.js 15, dev mode, hot reload)
- 后端: `uvicorn backend.main:app --port 8000` (FastAPI, reload)
- 数据库: `backend/data/aog.db` + `backend/data/fts5_index.db`
- 静态资源: `frontend/public/data/global-airports.json` (707KB)
- API base: `http://localhost:8000/api` (DISABLE_AUTH=1)

### 公网 (CloudBase)
- 前端: `https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com`
  - 当前仍跑 Jul 17 老版本（V12 SCF Fix A）
  - 待部署: V13-V28b 全部新功能
- 后端: `https://njx-copilot-d6gs7642f8fa17122.service.tcloudbase.com/api`
  - 当前 SCF `76cca2c` (Jul 17)，缺 `/api/airlines` + `/api/auth/login`
- COS: `aog-prod-data-1343051603` (ap-shanghai)
- 静态托管 CDN: 10 分钟缓存（V12 治本，CDN 全部行 1年 → 10分钟）

### 凭证 (mode 600)
```
envId:              njx-copilot-d6gs7642f8fa17122
AppId:              1343051603
GitHub:             zhouzengrui369-commits (account)
SecretId:           <TENCENT_SECRET_ID> (本地 .env 真实凭证, 不进 git)
SecretKey:          <TENCENT_SECRET_KEY> (本地 .env 真实凭证, 不进 git)
MINIMAX_API_KEY:    <MINIMAX_API_KEY> (本地 .env 真实凭证, 不进 git)
MINIMAX_BASE_URL:   https://api.MiniMax.chat/v1
MINIMAX_MODEL:      minimax-m3
COS_BUCKET:         aog-prod-data-1343051603
COS_REGION:         ap-shanghai
Uin:                100040900162
Account:            南极熊 (周堉瑞)
```

---

## 📊 性能数据

- 页面加载: 1.5s (V12 优化)
- 城市搜索: 200ms
- 地图渲染: 500ms
- AI chat: 4s (含 RAG 检索 + LLM 调用)
- 静态资源: 707KB global-airports.json (gzipped ~150KB)

---

**新 AI 接手步骤**：
1. 读 README.md (项目入口)
2. 读 STATUS.md (当前状态)
3. 读本文件 (架构 + 关键设计)
4. 跑 `pnpm dev --port 3004` 看效果
5. 读核心代码: `frontend/components/world-map-leaflet.tsx`
6. 改 UI 前看 DECISIONS.md（避免重复讨论已定方向）

---

**最后更新**: 2026-07-26 by Mavis
