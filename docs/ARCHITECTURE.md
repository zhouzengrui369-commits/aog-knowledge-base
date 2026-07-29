# AOG Knowledge Base - 系统架构

> 最后更新: 2026-07-29 14:30 GMT+8
> 适用版本: V30 + 本 PR P0 修复
> 相关文档: [STATUS.md](../STATUS.md) · [TODO.md](../TODO.md) · [CHANGELOG.md](../CHANGELOG.md) · [DECISIONS.md](../DECISIONS.md) · [PROJECT_STATE.yaml](../PROJECT_STATE.yaml)

---

## 1. 总体架构 (5 层)

```
┌────────────────────────────────────────────────────────────┐
│ L1: 用户层 (Browser / Mobile)                              │
│   - Next.js 15 SSG + CSR                                    │
│   - 域名: https://aog.njx.com (CloudBase 静态托管 + CDN)   │
│   - 移动端 375×800 适配                                     │
└────────────────────────────────────────────────────────────┘
                            ↕ HTTPS (TJSON)
┌────────────────────────────────────────────────────────────┐
│ L2: API Gateway + SCF 函数 (CloudBase SCF)                 │
│   - 函数: aog-api (Python 3.11, 60s timeout, 512MB)         │
│   - URL: https://...service.tcloudbase.com → /api/*        │
│   - 入口: functions/aog-api/main.py (inline ASGI + lifespan)│
│   - 限制: 100MB 代码 + 100MB /tmp 临时存储                  │
└────────────────────────────────────────────────────────────┘
                            ↕ 内部调用
┌────────────────────────────────────────────────────────────┐
│ L3: FastAPI 后端 (CloudBase SCF 容器内)                    │
│   - 入口: aog_web/main.py (lifespan + CORS + 8 routers)    │
│   - LLM: MiniMax M3 (https://api.MiniMax.chat/v1)         │
│   - RAG: FTS5 + BM25 (主) / Chroma (dev fallback)          │
│   - 持久化: SQLite (aog.db) + COS (fts5_index.db / chroma) │
│   - CORS: aog.njx.com, localhost:3000                      │
└────────────────────────────────────────────────────────────┘
                            ↕ 内部调用
┌────────────────────────────────────────────────────────────┐
│ L4: Pipeline 数据构建 (本地跑, 定期)                       │
│   - 入口: aog-web/pipeline/scripts/build_index.py          │
│   - 输出: aog.db (SQLite) + chroma.sqlite3 (chroma)        │
│   - 入口 (V30): aog-web/pipeline/scripts/export_fts5.py    │
│   - 输出: fts5_index.db (FTS5 + trigram tokenizer)        │
│   - 触发: 本地手动 + CloudBase 函数触发 (POST /api/reindex) │
└────────────────────────────────────────────────────────────┘
                            ↕ 读取 (read-only)
┌────────────────────────────────────────────────────────────┐
│ L5: 原始数据 (NJX 维护, read-only)                          │
│   - AOG知识库/ (Obsidian vault, 02_外战预案/ etc.)         │
│   - RAW/ (原始导出, 维修工程部报告)                        │
│   - 5 文档 (PRD / 立项 / Co-pilot 设计)                    │
│   - PM 绝对不能写 (memory 7/27 D-029 教训)                 │
└────────────────────────────────────────────────────────────┘
```

---

## 2. 数据流 (5 个关键路径)

### 2.1 城市详情查询 (RAG-augmented)

```
User → /city/S-上海浦东
   ↓ SSR
Frontend getCity(code)
   ↓ GET /api/city/{code}
Backend → sqlite_client.get_city(code)
   ↓ SELECT * FROM cities WHERE code=?
aog.db (SQLite)
   ↓ JSON
Backend → JSON Response
   ↓
Frontend render 5 tab
```

### 2.2 AI 行业问答 (5 段式 RAG + LLM)

```
User: "B787 风挡 AOG 怎么处理?"
   ↓ POST /api/chat {q: ...}
Backend api/chat.py
   ↓ 1. 5 段式 fts5 query (wiki/city/city_contacts/exp/core_plan)
   ↓    召数: wiki 3 / city 8 / city_contacts 5 / exp 2 / core 1
   ↓    city 2.0x boost (D-043)
   ↓    specificity 排序 (D-043)
   ↓ 2. 合并去重, 限 12
   ↓ 3. 构造 system prompt (NSM-2 强制 references ≥ 1)
   ↓ 4. LLM call (MiniMax M3 live / Mock fallback)
   ↓
LLM (MiniMax M3) — 流式 SSE
   ↓
Frontend render markdown (V29b 视觉升级)
```

### 2.3 数据更新 (本地 pipeline)

```
NJX 编辑 AOG知识库/02_外战预案/B-北京大兴.docx
   ↓
cd aog-web/pipeline && uv run python -m pipeline.build_index --paths AOG知识库/02_外战预案/
   ↓
pipeline/build_index.py
   ↓ 1. docx → md (pandoc)
   ↓ 2. md → chunks (langchain)
   ↓ 3. chunks → embedding (chroma default, dim=1024 ⚠️)
   ↓ 4. upsert chroma collection
   ↓ 5. upsert aog.db (CityRow / ExperienceRow / CorePlanRow)
   ↓
python -m scripts.export_fts5 --chroma ./data/chroma --sqlite ./data/aog.db --out ./data/fts5_index.db
   ↓ 1. SELECT all chunks FROM chroma
   ↓ 2. CREATE FTS5 tables (trigram tokenizer, D-038)
   ↓ 3. INSERT chunks (c0, title, source_path, source_id, source_type, ...)
   ↓ 4. write build_manifest table (tokenizer/build_commit/source_manifest/chunk_count/db_size)
   ↓
tools/sync_to_cos.py
   ↓ 1. cp fts5_index.db → COS bucket
   ↓ 2. cp aog.db → COS bucket
   ↓
NJX tcb fn deploy (重启 SCF 容器)
   ↓ 1. 容器启动 lifespan
   ↓ 2. download fts5_index.db from COS → /tmp/fts5_index.db
   ↓ 3. download aog.db from COS → /tmp/aog.db
   ↓
Backend ready (live)
```

### 2.4 Provider 失败处理 (P0-4 后)

```
Backend startup
   ↓ check ALLOW_MOCK + MINIMAX_API_KEY
   ↓
   ┌────────────────────────────────────┐
   │ ALLOW_MOCK=false + KEY 空          │
   │   → log.error + raise RuntimeError │
   │   → SCF container restart          │
   │   → CloudBase 标记 unhealthy       │
   └────────────────────────────────────┘
   ↓
   ┌────────────────────────────────────┐
   │ ALLOW_MOCK=false + KEY 存在        │
   │   → live LLM, 正常                 │
   └────────────────────────────────────┘
   ↓
   ┌────────────────────────────────────┐
   │ ALLOW_MOCK=true + KEY 空           │
   │   → Mock LLM (⚠️ Mock 模式 banner) │
   │   → 仅 dev 本地, 不进 production  │
   └────────────────────────────────────┘
```

### 2.5 数据可信度 9 字段 (P0-5 后)

```
docx 录入 (NJX 操作)
   ↓ docx YAML frontmatter 提取
   - source_document
   - source_location
   - source_version
   - updated_at
   - reviewed_at
   - reviewed_by
   - review_status (VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED)
   - confidence
   - environment
   - pii_classification
   ↓
pipeline/build_index.py
   ↓
SQLite INSERT INTO cities (..., source_document, source_location, ..., review_status, ...)
   ↓
Frontend city detail
   ↓ display
   - 来源: AOG知识库/02_外战预案/B-北京大兴.docx
   - 最后更新: 2026-07-15
   - 审核: NJX (2026-07-15)
   - 状态: ✅ VERIFIED
   - 置信度: 0.95
   - PII: 内部
```

---

## 3. 关键设计决策 (D-XXX 摘要)

| 决策 | 选择 | 原因 |
|------|------|------|
| 部署平台 | 腾讯云 CloudBase | NJX 7/16 拍板, 国内访问快 |
| 后端形态 | SCF Python 函数 (非 Run 容器) | 冷启动 30s 接受, 简于 Run 容器 |
| 数据持久化 | COS 桶 | 保留 T1 Chroma + T3 pipeline, 工作量最低 |
| 增量同步 | 生产关闭 (SYNC_ENABLED=false) | 容器临时, 多实例并发会冲突 |
| 检索 (V28b+) | FTS5 + BM25 + trigram | 不用 embedding, 维度问题彻底回避 (D-038) |
| 检索 (本地 dev) | FTS5 (主) / Chroma (fallback) | chroma 集合 dim=1024 已废用, 等清理 |
| LLM | MiniMax M3 (https://api.MiniMax.chat/v1) | NJX 主线 provider |
| URL 规范 (P0-2) | base 不带尾 /api, path /api/... | 消除 double-prefix |
| Mock (P0-4) | dev 允许, production 禁 | UI 显式 "Provider 未配置" banner |
| 数据可信度 (P0-5) | 9 字段 + 6 状态枚举 | NJX 7/29 授权 |
| PII (P0-6) | role_class 3 级 + REDACTED 兜底 | 7/27 评 P1-11 关闭 |

---

## 4. 已知限制 (技术债)

| 限制 | 现状 | 计划 |
|------|------|------|
| chroma 集合 dim=1024 vs chroma default=384 dim 不匹配 | 87MB 在生产, 已废用 | P0-3 后清, 释放 87MB |
| SyncService 5min 跑一次, ollama embed 偶发 timeout | SCF 禁用 SYNC, dev 本地仍跑 | 改 sentence-transformers 本地, 本地 fix |
| 84 城市 stock 全 0 (备件 template) | docx 抽取 bug | P0-5 后 dedup |
| 5 航司联系表重复 (北京/哈尔滨 99% 相同) | docx 抽取 bug | P0-5 后 dedup |
| warehouse 重复 5 次 (抽取 bug) | pipeline bug | P0-5 后修 |
| exp-001/exp-002 SSG 404 | SSG 4 个, 后端 3 个 | P0-7 后删 1 个 |

---

## 5. 安全 & 合规

| 项 | 现状 | 责任 |
|------|------|------|
| Secret 管理 | CloudBase 控制台 env var, 永不 commit | NJX (CAM 子账号) |
| PII (个人手机号) | 7/27 评 P1-11 裸露 | P0-6 REDACTED 兜底 (本 PR) |
| 凭证轮换 | MiniMax API key 定期轮换 | NJX |
| SCF 余额 | InsufficientBalance (7/29 实测) | NJX 充值 |
| CORS | aog.njx.com, localhost:3000 | P0-2 验证 |
| Auth | Sprint A 密码 + JWT 24h (本地优先) | 生产待评估 (P1-11 AMBIGUOUS) |

---

## 6. 监控 & 告警

| 项 | 现状 | 计划 |
|------|------|------|
| SCF 冷启动 30-60s | 用户接受, frontend 静态化绕过 | 监控 + 优化 |
| SyncService 错误 | 7/27 评 P0-6 残余, SCF 禁用 | SCF 部署时关闭, dev 本地继续 |
| 索引 stale | last_sync in index_stats 表 | P0-7 后加 UI 监控 |
| 公网余额 | 无告警, 缺钱函数被禁 | P0-7 后加余额监控 |

---

## 7. 跨项目规则 (NJX 立的 OPC 基线)

- **5 文档基线** (7/26 立): PROJECT_STATE.yaml + STATUS.md + TODO.md + docs/ARCHITECTURE.md + CHANGELOG.md + DECISIONS.md, 任何新 AI 接手 10 分钟能继续
- **read-only 数据源铁律** (7/27 D-029): AOG知识库/ / RAW/ / NAS 知识库, PM 绝对不能写, 任何"补数据"走 staging + NJX 物理 cp
- **stub 污染预防 4 步** (7/27 D-029): stub 命名带 .stub. 后缀, 放 /tmp/staging_*, build_index path 排除 .stub., UI mock fallback 红框
- **项目根路径**: `/Users/njx/Project/AOG知识库/` (AOG), `/Users/njx/openclaw/copilot/` (openclaw), `/Volumes/南极熊/03知行合一/opc/` (OPC), NAS 必须 `cp -X` 去 macOS metadata
- **凭证管理** (7/26): CloudBase `.env` mode 600, NJX 物理 OAuth
- **12 周 OPC 飞轮** (2026-06-10 立): openclaw 60% / 航材 25% / 知识库 15%, 不平均用力, sprint 启动协议不再问"接下来做什么"

---
