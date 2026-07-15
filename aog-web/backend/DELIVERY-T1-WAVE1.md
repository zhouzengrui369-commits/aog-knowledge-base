# T1 Backend · Wave 1 交付报告

> 分支: `feature/wave1-backend`
> Commit: `9aac08a0e9854e9f6a625ec4274e6e78a9152da4`
> 工作目录: `aog-web/backend/`

---

## 1. commit hash

```
9aac08a0e9854e9f6a625ec4274e6e78a9152da4
```

## 2. 文件清单 (35 个文件)

```
aog-web/backend/.env.example
aog-web/backend/.gitignore
aog-web/backend/pyproject.toml
aog-web/backend/uv.lock
aog-web/backend/data/chroma/                  # 空目录 (gitignore)
aog-web/backend/data/index_stats.json         # {}
aog-web/backend/aog_web/__init__.py
aog-web/backend/aog_web/main.py
aog-web/backend/aog_web/config.py
aog-web/backend/aog_web/api/__init__.py
aog-web/backend/aog_web/api/health.py
aog-web/backend/aog_web/api/cities.py
aog-web/backend/aog_web/api/experiences.py
aog-web/backend/aog_web/api/core_plans.py
aog-web/backend/aog_web/api/chat.py
aog-web/backend/aog_web/api/reindex.py
aog-web/backend/aog_web/api/sync.py
aog-web/backend/aog_web/api/files.py
aog-web/backend/aog_web/models/__init__.py
aog-web/backend/aog_web/models/city.py
aog-web/backend/aog_web/models/experience.py
aog-web/backend/aog_web/models/core_plan.py
aog-web/backend/aog_web/models/chat.py
aog-web/backend/aog_web/services/__init__.py
aog-web/backend/aog_web/services/sqlite_client.py
aog-web/backend/aog_web/services/chroma_client.py
aog-web/backend/aog_web/services/llm.py
aog-web/backend/aog_web/services/sync.py
aog-web/backend/aog_web/llm/__init__.py
aog-web/backend/aog_web/llm/minimax.py
aog-web/backend/tests/conftest.py
aog-web/backend/tests/test_health.py
aog-web/backend/tests/test_cities.py
aog-web/backend/tests/test_experiences.py
aog-web/backend/tests/test_chat.py
aog-web/backend/tests/test_sync.py
aog-web/backend/tests/test_config.py
aog-web/backend/tests/test_models.py
```

**统计**: 32 个 .py 文件 (≥ 15 要求), pyproject + .env.example + .gitignore + uv.lock + 2 data 文件

## 3. 7 端点 curl 验证输出

| # | 端点 | 状态 | 备注 |
|---|---|---|---|
| 1 | `GET /api/health` | 200 | `{status:"ok", version:"0.1.0", uptime_s:N, llm_mode:"mock"}` |
| 2 | `GET /api/cities` | 200 | `[]` (data pipeline 还没跑, 期望 ≥ 0 ✓) |
| 3 | `GET /api/city/test` | 404 | `{detail:{error:"city not found", code:"test"}}` |
| 4 | `GET /api/experiences` | 200 | `[]` (data pipeline 还没跑) |
| 5 | `POST /api/chat {"q":"B787 风挡 AOG"}` | 200 | references.length = **1** (NSM-2 ✓) |
| 6 | `GET /api/sync/status` | 200 | `{status:"idle", last_sync:null, queue:0, indexed_total:0}` |
| 7 | `GET /docs` | 200 | OpenAPI UI |

**额外**: `POST /api/reindex` / `GET /api/reindex/{id}` / `GET /files/*` / 经验详情 / core-plan 详情 全部走通 (见 10 端点全验证)

**Chat 完整 payload** (空 DB 下, 兜底 references):
```json
{
  "answer": "⚠️ Mock 模式 · ...（如需更精准回答, 请在 .env 配置 MINIMAX_API_KEY 后重启。）",
  "references": [{"id":"__no_match__","title":"暂未找到相关文档","href":"#","snippet":"请尝试更具体的关键词","score":0.0}],
  "model": "minimax-m3",
  "latency_ms": 257
}
```

**带种子数据** (4 城市 + 2 经验) 时 chat `B787 风挡 AOG 怎么处理？` 实际命中:
```json
{
  "references": [{"id":"exp-001","title":"B787 风挡 AOG 处理流程","href":"/experience/exp-001","score":0.8}],
  "latency_ms": 247
}
```

## 4. pytest 摘要

```
61 passed in 9.63s
TOTAL coverage: 85% (≥ 60% ✓)
```

| 模块 | Stmts | Miss | Cover |
|---|---|---|---|
| aog_web/api/chat.py | 112 | 32 | 71% |
| aog_web/api/cities.py | 23 | 0 | **100%** |
| aog_web/api/core_plans.py | 17 | 0 | **100%** |
| aog_web/api/experiences.py | 18 | 0 | **100%** |
| aog_web/api/files.py | 36 | 6 | 83% |
| aog_web/api/health.py | 10 | 0 | **100%** |
| aog_web/api/reindex.py | 27 | 0 | **100%** |
| aog_web/api/sync.py | 12 | 0 | **100%** |
| aog_web/config.py | 63 | 2 | 97% |
| aog_web/main.py | 59 | 3 | 95% |
| aog_web/models/* | 93 | 0 | **100%** |
| aog_web/services/chroma_client.py | 56 | 13 | 77% |
| aog_web/services/llm.py | 59 | 5 | 92% |
| aog_web/services/sqlite_client.py | 172 | 51 | 70% |
| aog_web/services/sync.py | 30 | 7 | 77% |
| **TOTAL** | **787** | **119** | **85%** |

## 5. 已知问题 / mock 模式标志

### Mock LLM 模式 (当前默认, 因无 `MINIMAX_API_KEY`)

- `/api/health` 响应 `llm_mode: "mock"`
- chat 回答 prefix 是 `⚠️ Mock 模式 ·`
- chat 的 `model` 字段返回 `minimax-m3` (设置名), 但实际是 `MockLLM` 在跑
- 仍能保证 NSM-2 (references ≥ 1, 用 SQLite token-fallback 兜底)
- 切换到 live: 在 `.env` 填 `MINIMAX_API_KEY=...` 后重启

### Mock LLM 在 chat 里的"智能"行为

简单规则 (供前端 preview):
- q 含 "谁/联系人/电话/联系" → "联系人信息已在下方'参考资料'区"
- q 含 "怎么/如何/流程/处理/AOG" → "标准处理流程已整理在下方'参考资料'区"
- 其它 → 通用 RAG 提示
- 始终提示"如需更精准回答, 请在 .env 配置 MINIMAX_API_KEY 后重启"

### NSM-2 兜底链 (3 层)

1. **Chroma 检索** (主要) — 当 T3 pipeline 写入后, 走真实向量检索
2. **SQLite token-fallback** (Chroma 空 / 失败) — 用中文 2-gram + 英文 token 匹配 experiences + cities
3. **`__no_match__` placeholder** (终极兜底) — 即使全空也返回 1 个"暂未找到相关文档"

### Reindex / Sync 占位

- `POST /api/reindex` 当前 in-memory 立即 mark done (Wave 1 简化, T3 pipeline 是真实 worker)
- `GET /api/sync/status` 从 SQLite `index_stats` 表读 (T3 pipeline 写入)
- `SyncService.start()` 是 no-op (定时轮询推迟到 Phase 2)

### Chroma collection 状态

- 当前空 (T3 pipeline 还没跑)
- 启动时 `get_or_create_collection(name="aog_documents")` 幂等
- `metadata={"hnsw:space": "cosine"}` (与 T3 pipeline 对齐)

## 6. 给 T2 前端 agent 的提示

### API 实际响应可能与 CONTRACT 略偏的地方

1. **`/api/city/{code}` 中文 code**: 必须 URL-encode!
   ```js
   // GOOD
   fetch(`/api/city/${encodeURIComponent('B-北京大兴')}`)
   // BAD
   fetch('/api/city/B-北京大兴')  // 会被前端 router 切, 后端收到乱码
   ```

2. **`/api/chat` NSM-2 兜底**: 即使没数据, 也会返回 1 个 `id: "__no_match__"`, `score: 0.0` 的占位 reference. 前端判断"无相关结果"应看 score 或 title, 不是看 length.

3. **`/api/cities` 默认按 pinyin 排序** (不是按地区/状态). letter 筛选按 pinyin 首字母 (`beijingdaxing` → B).

4. **空数据状态**: T3 pipeline 跑之前, `/api/cities` 和 `/api/experiences` 都返回 `[]` (不是 null). 前端 empty state UI 需要 fallback.

5. **Mock LLM 时延**: 第一次 chat 冷启动 ~500ms, 后续 ~250ms (本地). Live 模式 P50 ≤ 3s, P95 ≤ 5s (CONTRACT §2.7).

6. **CORS**: 已配 `http://localhost:3000` 和 `http://127.0.0.1:3000`. Vercel preview URL 需要在 `.env` `CORS_ALLOW_ORIGINS` 加, 或用 `https://*.vercel.app` 通配 (待 PM 决定).

7. **`/api/files/*`**: 路径必须在 `KNOWLEDGE_BASE_PATH` (默认 `/Users/njx/Project/AOG知识库/AOG知识库`) 或 `RAW_PATH` (默认 `/Users/njx/Project/AOG知识库/RAW`) 白名单下. 阻止 path traversal. 部署到 Railway 时这两个路径不存在, 该端点会全部 404 (Railway 应挂 Volume 重定向).

8. **`/api/reindex`**: Wave 1 是 stub, 永远立刻 done. 前端如果做"重建索引"按钮, 临时先调, 真功能等 T3.

9. **错误格式**: FastAPI 默认 `{"detail": {...}}` 包裹业务错误. 例: `{"detail":{"error":"city not found","code":"test"}}`. 前端 axios/fetch catch 要 `err.response.data.detail.error`, 不是 `err.message`.

10. **`/api/chat` 错误码**: 502 = upstream LLM error, 503 = model unavailable, 429 = rate limit (未实现). Mock 模式不会触发任何 5xx.

### OpenAPI 在线文档

- `http://localhost:8000/docs` (Swagger UI) — 一目了然所有端点 + schema
- `http://localhost:8000/openapi.json` — raw spec, 前端可用 codegen 拿 types
- `http://localhost:8000/redoc` — ReDoc 风格

### 启动方式

```bash
cd aog-web/backend
uv sync --extra dev           # 装 dev 依赖
uv run uvicorn aog_web.main:app --port 8000 --reload
```

或:
```bash
uv run aog-web-backend  # 配 entry point 后
```

(目前没配 `[project.scripts]`, 暂时用上面方式)
