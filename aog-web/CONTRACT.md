# AOG AI 知识库 · API 契约（CONTRACT.md）

> 项目: AOG AI 知识库网站
> 写者: PM (mavis)
> 最后更新: 2026-07-15
> 适用: T1 后端 / T2 前端 / T3 数据 pipeline 三个 Wave 1 子智能体
> 优先级: **最高** —— 子智能体不修改此文档，有歧义先问 PM

---

## §1 数据模型（共享）

### 1.1 City（航站/城市）

```typescript
interface City {
  code: string;              // 主键, 例 "B-北京大兴"
  name: string;              // "北京大兴"
  airport: string;           // "北京大兴国际机场"
  iata: string;              // "PKX"
  pinyin: string;            // "beijingdaxing"
  region: '华北'|'华东'|'华南'|'华中'|'西南'|'西北'|'东北'
        | '国际-欧洲'|'国际-亚洲'|'国际-美洲'|'国际-中东'|'国际-非洲'|'国际-大洋洲';
  status: '现行'|'暂停'|'已废';
  tags: string[];            // ["AOG预案","国际枢纽","24h响应"]
  fleet: Array<{             // 执飞机型
    model: string;           // "B787"
    short_stay: boolean;     // 短停
    after: boolean;          // 航后
  }>;
  parts: Array<{             // 主要备件
    pn: string;              // 件号 "C20649000"
    name: string;            // "B787 主轮"
    stock: number;           // 库存
    unit: string;            // "个"
  }>;
  contacts: Array<{          // 联系人
    org: string;             // "东航上海总部 AOG"
    phone: string[];         // ["021-22379771","79772","79773"]
    email?: string;
    role: string;            // "7×24"
  }>;
  warehouse: {               // 仓库信息
    location: string;
    main: string[];
  };
  logistics: {               // 物流
    rail: string;
    air: string;
    road: string;
  };
  content_md: string;        // 完整预案 md 文本（≥ 1000 字）
  source_path: string;       // RAW 文件相对路径
  updated_at: string;        // ISO8601
}
```

### 1.2 Experience（保障经验）

```typescript
interface Experience {
  id: string;                // 主键, 例 "exp-001"
  title: string;             // "B787 风挡 AOG 处理流程"
  category: '流程'|'规范'|'案例'|'培训'|'技术'|'管理';
  status: '现行'|'历史'|'待审'|'已废';
  tags: string[];            // ["B787","风挡","案例"]
  summary: string;           // ≤ 200 字
  content_md: string;        // 完整内容 md
  related_pn: string[];      // 相关件号
  source_path: string;
  updated_at: string;
}
```

### 1.3 CorePlan（核心 AOG 预案，不在城市目录里）

```typescript
interface CorePlan {
  id: string;                // "core-20260204"
  title: string;             // "AOG 保障预案 2026-02-04"
  type: 'master'|'checklist'|'manual'|'catalog';
  content_md: string;
  source_path: string;
  updated_at: string;
}
```

### 1.4 ChatRequest / ChatResponse

```typescript
interface ChatRequest {
  q: string;                 // 用户问题
  context_codes?: string[];  // 可选, 限定城市
}

interface ChatResponse {
  answer: string;            // AI 回答 markdown
  references: Array<{        // ★ 强制 ≥ 1, NSM-2 红线
    id: string;              // 引用 id
    title: string;           // "B787 风挡 AOG 处理流程"
    href: string;            // "/experience/exp-001" 或 "/city/B-上海浦东"
    snippet: string;         // 截取片段 200 字内
    score: number;           // 0-1 相关度
  }>;
  model: string;             // "minimax-m3"
  latency_ms: number;        // 服务端处理耗时
}
```

### 1.5 SyncStatus

```typescript
interface SyncStatus {
  status: 'idle'|'running'|'error';
  last_sync: string|null;    // ISO8601
  queue: number;             // 待处理文件数
  indexed_total: number;     // 累计索引文件数
  last_error?: string;
}
```

---

## §2 API 端点（FastAPI 后端必须实现）

### 2.1 健康检查

```
GET /api/health
→ 200 {"status":"ok","version":"1.0.0","uptime_s":1234}
```

### 2.2 城市列表

```
GET /api/cities?region=&status=&letter=
Query:
  - region: 可选, 地区筛选
  - status: 可选, "现行"|"暂停"|"已废"
  - letter: 可选, 首字母 A-Z
→ 200 City[]   (按 pinyin 排序)
→ 400 {error: "invalid query"}
```

### 2.3 城市详情

```
GET /api/city/{code}
Path:
  - code: 城市 code, URL-encoded (例 "B-北京大兴")
→ 200 City
→ 404 {error: "city not found", code: "..."}
```

### 2.4 经验列表

```
GET /api/experiences?category=&status=&q=
Query:
  - category: 可选
  - status: 可选
  - q: 可选, 全文搜索关键词
→ 200 Experience[]  (按 updated_at desc)
```

### 2.5 经验详情

```
GET /api/experience/{id}
Path:
  - id: 经验 id
→ 200 Experience
→ 404 {error: "experience not found"}
```

### 2.6 核心预案

```
GET /api/core-plans
→ 200 CorePlan[]

GET /api/core-plan/{id}
→ 200 CorePlan
```

### 2.7 AI 对话（RAG + MiniMax M3）

```
POST /api/chat
Content-Type: application/json
Body: ChatRequest
→ 200 ChatResponse
→ 429 {error: "rate limit"}     // 触发限流
→ 502 {error: "upstream LLM error"}
→ 503 {error: "model unavailable"}

性能要求:
  - P50 latency ≤ 3s
  - P95 latency ≤ 5s
  - references.length 强制 ≥ 1 (NSM-2)
```

### 2.8 重建索引（仅 dev/admin）

```
POST /api/reindex
Body: { "paths": ["/abs/path/file.md"] }  // 可选, 不传 = 全量
→ 202 {job_id: "..."}
→ 200 {job_id: "...", status: "queued"}

GET /api/reindex/{job_id}
→ 200 {job_id, status: "running"|"done"|"error", progress: 0-100, error?: string}
```

### 2.9 同步状态

```
GET /api/sync/status
→ 200 SyncStatus
```

### 2.10 静态文件（原 docx/pdf 下载）

```
GET /files/{relative_path}
Path:
  - relative_path: RAW/ 或 AOG知识库/ 下的相对路径
→ 200 file (octet-stream)
→ 404 {error: "file not found"}

注: 后端代理, 不暴露绝对路径
```

---

## §3 后端实现约束（T1）

### 3.1 技术栈
- Python 3.14 + FastAPI + uvicorn
- Chroma (持久化到 `./data/chroma`)
- SQLite (元数据到 `./data/aog.db`)
- 依赖: `pyproject.toml` 用 uv 管理

### 3.2 项目结构

```
aog-web/backend/
├── pyproject.toml
├── aog_web/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py            # 环境变量 / 路径
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── cities.py
│   │   ├── experiences.py
│   │   ├── core_plans.py
│   │   ├── chat.py
│   │   ├── reindex.py
│   │   ├── sync.py
│   │   └── files.py
│   ├── models/              # Pydantic schemas (= §1 数据模型)
│   │   ├── city.py
│   │   ├── experience.py
│   │   ├── core_plan.py
│   │   └── chat.py
│   ├── services/
│   │   ├── chroma_client.py # 向量检索
│   │   ├── sqlite_client.py # 元数据查询
│   │   ├── llm.py           # 模型抽象层（MiniMax M3 + future）
│   │   └── sync.py          # 增量同步
│   └── llm/
│       └── minimax.py       # MiniMax M3 实现
├── data/                    # gitignore
│   ├── chroma/
│   ├── aog.db
│   └── index_stats.json
└── tests/
    ├── test_health.py
    ├── test_cities.py
    ├── test_experiences.py
    ├── test_chat.py
    └── test_sync.py
```

### 3.3 环境变量（.env, 不 commit）

```
MINIMAX_API_KEY=xxx           # 必填
MINIMAX_BASE_URL=https://api.MiniMax.chat/v1
MINIMAX_MODEL=minimax-m3
CHROMA_PATH=./data/chroma
SQLITE_PATH=./data/aog.db
KNOWLEDGE_BASE_PATH=/Users/njx/Project/AOG知识库/AOG知识库
RAW_PATH=/Users/njx/Project/AOG知识库/RAW
SYNC_INTERVAL_S=300
LOG_LEVEL=INFO
```

### 3.4 LLM 抽象层

```python
# aog_web/services/llm.py
from typing import Protocol

class LLM(Protocol):
    async def chat(self, messages: list[dict], **kw) -> str: ...

class MiniMaxM3:
    """MiniMax M3 实现"""
    def __init__(self, api_key: str, model: str = "minimax-m3"):
        ...

# 注册表
_REGISTRY = {"minimax-m3": MiniMaxM3}

def get_llm(name: str = None) -> LLM:
    name = name or settings.llm_model
    return _REGISTRY[name](...)
```

### 3.5 验收硬指标
- `uvicorn aog_web.main:app --port 8000` 启动成功
- `curl http://localhost:8000/api/health` → 200
- `curl http://localhost:8000/api/cities | jq length` ≥ 220
- `curl http://localhost:8000/api/city/B-北京大兴` → 200 + 完整字段
- `curl -X POST /api/chat -d '{"q":"B787 风挡"}'` → 200 + references.length ≥ 1
- `pytest --cov=aog_web --cov-report=term-missing` → coverage ≥ 60%
- `http://localhost:8000/docs` (OpenAPI) → 200

---

## §4 前端实现约束（T2）

### 4.1 技术栈
- Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui
- 状态: Zustand (轻量)
- HTTP: fetch (no axios)
- 包管理: pnpm

### 4.2 项目结构

```
aog-web/frontend/
├── package.json
├── pnpm-lock.yaml
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── app/
│   ├── layout.tsx
│   ├── page.tsx                       # 首页
│   ├── city/
│   │   └── [code]/
│   │       └── page.tsx               # 城市详情
│   ├── experiences/
│   │   ├── page.tsx                   # 18 经验列表
│   │   └── [id]/
│   │       └── page.tsx               # 经验详情
│   ├── not-found.tsx                  # 404
│   └── api/                           # Next.js API routes (proxy 后端, 可选)
├── components/
│   ├── chat-widget.tsx                # ChatWidget
│   ├── city-card.tsx
│   ├── experience-card.tsx
│   ├── alphabet-nav.tsx
│   ├── search-bar.tsx
│   └── ui/                            # shadcn components
│       ├── button.tsx
│       ├── card.tsx
│       ├── badge.tsx
│       └── sheet.tsx
├── lib/
│   ├── api.ts                         # API client (与 §2 契约一致)
│   └── utils.ts
└── public/
```

### 4.3 API Client（`lib/api.ts`）

```typescript
// 必须与 §2 契约 1:1 对应
export async function getCities(params?: {...}): Promise<City[]>
export async function getCity(code: string): Promise<City>
export async function getExperiences(params?: {...}): Promise<Experience[]>
export async function getExperience(id: string): Promise<Experience>
export async function chat(req: ChatRequest): Promise<ChatResponse>
```

### 4.4 设计 token 迁移

从 mockup 抽到 `tailwind.config.ts`：
```ts
// 继承 mockup 的颜色/间距/圆角
colors: {
  primary: { 50: '...', 100: '...', ..., 900: '...' },
  ink: { 50: '...', ..., 900: '...' },
},
borderRadius: { sm: '4px', md: '8px', lg: '12px' },
```

### 4.5 URL 编码策略

- 城市 code 含中文：`/city/B-北京大兴` → 用 `encodeURIComponent` 在 router 里转
- 经验 id 用 `exp-001` 形式（不含中文）

### 4.6 验收硬指标
- `pnpm dev` 启动，`curl http://localhost:3000` → 200
- 4 页面（首页/城市详情/经验列表/经验详情）全渲染
- ChatWidget 接通 `/api/chat`
- Lighthouse desktop ≥ 80 / mobile ≥ 60
- 响应式截图 3 张

### 4.7 mockup 复用策略

agent **必须**复用 `aog-web/mockup/` 已有：
- 颜色 token（迁移到 tailwind.config.ts）
- 组件结构（mockup 中的卡片/标签/按钮 → shadcn 组件）
- 数据结构（cities.js / experiences.js → 模拟数据，再换真 API）
- ChatWidget UI（mockup chat-widget.html → components/chat-widget.tsx）

**不要从零写** — 先 copy mockup 改造。

---

## §5 数据 pipeline 约束（T3）

### 5.1 技术栈
- Python 3.14 + 解析器（python-docx / openpyxl / pypdf / markdown-it-py）
- 嵌入: sentence-transformers (bge-m3) 或调 embedding API
- 写入: Chroma + SQLite（与 T1 schema 一致）

### 5.2 项目结构

```
aog-web/pipeline/
├── pyproject.toml
├── pipeline/
│   ├── __init__.py
│   ├── build_index.py        # 主入口
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── md.py
│   │   ├── docx.py
│   │   ├── xlsx.py
│   │   └── pdf.py
│   ├── extractors/
│   │   ├── city_meta.py      # 从 docx 抽 city/airport/iata/region
│   │   └── experience_meta.py
│   ├── embedder.py           # bge-m3
│   ├── chunker.py            # 800 token / overlap 100
│   └── indexer.py            # 写 Chroma + SQLite
├── scripts/
│   └── run_build.sh
└── data/                     # 输出（同 backend/data/）
```

### 5.3 数据源扫描

只读源:
- `/Users/njx/Project/AOG知识库/AOG知识库/01_AOG预案/` → core_plans
- `/Users/njx/Project/AOG知识库/AOG知识库/02_外战预案/` → cities (220)
- `/Users/njx/Project/AOG知识库/AOG知识库/03_保障经验/` → experiences (18)

**禁止触碰**：
- ❌ `/Users/njx/Project/AOG知识库/AOG知识库/99_抓取日志/`
- ❌ `/Users/njx/Project/AOG知识库/RAW/`
- ❌ `/Users/njx/Project/AOG知识库/AOG知识库/04-07_*`（v1 不索引）

### 5.4 字段提取规则

#### City 提取
- `code`: 文件名第一段 `B-北京大兴.docx` → `B-北京大兴`
- `name`: 文件名去除前缀/状态 → `北京大兴`
- `airport`: 从 docx 内容抽"机场名称"或使用文件名
- `iata`: 从 docx 抽"三字代码"
- `region`: 从目录路径或文件 tags
- `status`: 文件名含"（暂停）" → `暂停`，否则 `现行`
- 其他字段（fleet/parts/contacts/...）: 从 docx 表格/段落提取

#### Experience 提取
- `id`: 哈希标题 → `exp-001`
- `title`: 文件名 → 标题
- `category`: 从 docx 第一个标题或 tags
- `status`: 默认 `现行`
- `summary`: 第一段 ≤ 200 字
- `content_md`: 整个 docx → md

### 5.5 验收硬指标
- `python -m pipeline.build_index` exit 0
- Chroma 集合 doc 数 ≥ 500
- SQLite `cities` 表 ≥ 220 行
- SQLite `experiences` 表 ≥ 18 行
- SQLite `core_plans` 表 ≥ 14 行
- 跑一次 build 耗时 < 10 min
- `data/index_stats.json` 记录完整

### 5.6 输出 schema

**必须与 §1 + T1 模型字段 1:1**：
- City 字段对齐 §1.1
- Experience 字段对齐 §1.2
- CorePlan 字段对齐 §1.3

不能有"额外字段"（避免前端兼容性）。

---

## §6 集成约束（Wave 2 T4）

### 6.1 端到端

```
[前端 pnpm dev :3000]
   ↓ fetch http://localhost:8000/api/...
[后端 uvicorn :8000]
   ↓ 查 Chroma + SQLite
[数据 ./data/]
   ↑ 写于 build_index.py
```

### 6.2 CORS
后端 `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://<vercel-domain>"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 6.3 错误处理
- 前端 fetch 错误 → toast 错误
- 后端 5xx → 500 + `{error: "internal error", request_id: "..."}`
- 4xx → 业务错误（city not found 等）

---

## §7 工作流协调

### 7.1 三个 worktree 隔离

```
worktrees/
├── backend/    (T1 写)   - branch: feature/wave1-backend
├── frontend/   (T2 写)   - branch: feature/wave1-frontend
└── pipeline/   (T3 写)   - branch: feature/wave1-pipeline
```

主项目目录（/Users/njx/Project/AOG知识库）保持 main 分支，PM 统一 merge。

### 7.2 共享文件
- `aog-web/CONTRACT.md`（本文件）—— PM 写，子 agent 读
- `aog-web/data/` —— 三个 agent 共享，pipeline 写，backend 读
- `aog-web/mockup/` —— T2 复用，T1/T3 读

### 7.3 冲突解决
- `pyproject.toml` 在 backend/pipeline/ 各自独立，不冲突
- `package.json` 在 frontend/ 独立
- 共享数据 schema 写在 CONTRACT.md，agent 不改

---

## §8 关联

- `../project/AOG知识库网站/goal.md` — 北极星
- `../project/AOG知识库网站/PRD.md` — 产品需求
- `../project/AOG知识库网站/plan.md` — Wave 1 任务
- `../project/AOG知识库网站/rules.md` — 团队规则
- `../project/AOG知识库网站/delivery/delivery.md` — 验收清单
