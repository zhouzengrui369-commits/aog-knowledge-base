# /api/experiences limit + offset + exclude content_md — 部署证据

**部署时间**: 2026-07-17 11:24 (SCF UpdateFunctionCode 成功 + cold start OK)
**Fix commit**: c840b73 (worktree) → a5ea5db (merge main no-ff)
**SCF ZIP**: /tmp/aog-api-deploy-v5.zip (13.27MB inline, b64 18.5M chars)
**公网 Backend**: https://njx-copilot-d6gs7642f8fa17122.service.tcloudbase.com/api
**公网 Frontend**: https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com

---

## 背景

**症状**: `GET /api/experiences` 返 15 经验 + 完整 content_md → body 6MB+ → 触发 SCF HTTP 6MB 上限 → 前端列表页 502。

**根因**:
- 当前 list endpoint 返完整 `Experience` model（含 `content_md`）
- 15 条经验 × 平均 400KB content_md = ~6MB body
- SCF API Gateway 硬上限 6MB HTTP response

**决策** (NJX 2026-07-17 11:18 拍板):
- `limit` (default 3, max 15) + `offset` (default 0)
- list 返 `ExperienceSummary` (不含 content_md, 保留 summary + 其他字段)
- 单条 `/api/experience/{id}` 仍返完整（含 content_md）

---

## 改动

### 1. `aog-web/backend/aog_web/models/experience.py` (新增 ExperienceSummary)

```python
class ExperienceSummary(BaseModel):
    """经验列表轻量子集 - 不含 content_md"""
    id: str
    title: str
    category: Category
    status: Status
    tags: List[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=200)
    related_pn: List[str] = Field(default_factory=list)
    source_path: str = ""
    updated_at: str = ""
```

### 2. `aog-web/backend/aog_web/api/experiences.py` (重写 list endpoint)

```python
MAX_LIST_LIMIT = 15
DEFAULT_LIST_LIMIT = 3

@router.get("/experiences", response_model=List[ExperienceSummary])
async def list_experiences(
    request: Request,
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(0, ge=0),
) -> List[ExperienceSummary]:
    client = get_sqlite_client()
    all_exps = await client.list_experiences(category=category, status=status, q=q)
    sliced = all_exps[offset : offset + limit]
    return [ExperienceSummary.model_validate(e) for e in sliced]  # Pydantic 自动 strip content_md
```

`/api/experience/{exp_id}` 单条 endpoint 不动（仍返完整 dict 含 content_md）。

### 3. Pydantic 验证 (smoke test)

```python
s = ExperienceSummary.model_validate({
    'id':'exp-001', 'title':'t', 'category':'流程', 'status':'现行',
    'tags':[], 'summary':'s', 'content_md':'X'*30000,
    'related_pn':[], 'source_path':'', 'updated_at':'2026-07-17',
})
# keys = ['category', 'id', 'related_pn', 'source_path', 'status', 'summary', 'tags', 'title', 'updated_at']
# content_md 已 strip ✓
```

---

## 部署链路 (踩坑: SCF 私桶 assume-role 失败 → 改 inline ZipFile)

### Step 1: build.sh 物理 copy
```bash
cd /Users/njx/Project/AOG知识库/aog-web/functions/aog-api
bash build.sh
# rsync backend/aog_web → functions/aog-api/aog_web (不含 __pycache__)
```

### Step 2: zip (含 vendor/)
```bash
zip -r /tmp/aog-api-deploy-v5.zip . -x "*.pyc" -x "*/__pycache__/*"
# size = 13,911,092 B (13.27MB, 远低于 SCF 50MB 上限)
```

### Step 3: COS upload (备用, 未被 SCF 使用)
```bash
python3 /tmp/upload_aog_zip.py
# COS_KEY = scf-deploy/aog-api/aog-api-deploy-v5.zip
# 1.8s ok, size 13,911,092, etag ded95dc1fdc8bc6
```

### Step 4: SCF UpdateFunctionCode — **踩坑修复**
**❌ 第一次 (v2 with CosBucketName)**: `UpdateFunctionCode OK in 0.3s` (假成功)
- `GetFunction` 查 `Status=UpdateFailed`
- `StatusReasons = [{"ErrorCode":"InvalidParameterValue.CodeConfig", "ErrorMessage":"format codeCosInfo failed: get baseCodeCosInfo tmp token failed assume role failed, secretId/secretKey/token is empty"}]`
- 根因: SCF 内部 assume TCB_QcsRole 失败 (私有 COS 桶读不到), SDK 没 `CosSecretId` 字段 (有 `OsSecretId` 但 SDK 不识别)

**✅ 第二次 (v3 inline ZipFile)**: 绕过 COS 鉴权
- `Code.ZipFile` 字段 = base64(zip_bytes), 限 20MB inline
- v5 zip 13.9MB → b64 18.5M chars → 适配
- `UpdateFunctionCode OK in 3.4s` (`RequestId=054478b8-5c32-4b24-8e76-7b303bd08a11`)
- `GetFunction Status=Active, StatusReasons=[], CodeResult=success`

> **下次部署注意**: zip > 20MB 必须用 COS path, 那时需要修 SCF 内部 assume-role 链路 (查 TCB_QcsRole 权限)。

### Step 5: cold start verify
```bash
curl https://njx-copilot-d6gs7642f8fa17122.service.tcloudbase.com/api/health
# → 200 {"status":"ok","version":"0.1.0","uptime_s":2,"llm_mode":"live","rag_backend":"fts5"}
# cold start 4.7s (warm, 上次 deploy 还在 instance pool)
```

---

## 6 项验收 (全过 ✅)

| # | 验收项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | experiences.py 加 limit/offset + 排除 content_md + ExperienceSummary model | ✅ | 2 files changed, 51 insertions, 7 deletions (commit c840b73) |
| 2 | 物理 copy 到 functions/aog-api/ 一致 | ✅ | build.sh rsync 后, `unzip -p v5.zip aog_web/api/experiences.py` 已是新代码 |
| 3 | zip build 成功 + 上传 COS ok | ✅ | /tmp/aog-api-deploy-v5.zip 13.27MB, COS upload 1.8s (备用, 实际部署用 inline) |
| 4 | SCF UpdateFunctionCode 200 + cold start | ✅ | UpdateFunctionCode OK in 3.4s (RequestId 054478b8), /api/health 200 fts5+live |
| 5 | /api/experiences default limit=3 返 3 真文档 (不超 6MB) | ✅ | **HTTP 200 · body 1096B** · 3 docs · no content_md |
| 5+ | /api/experiences?limit=15 返全 15 (不超 6MB) | ✅ | **HTTP 200 · body 5497B** · 15 docs · no content_md |
| 6 | /api/experiences?limit=10 body < 5MB | ✅ | **HTTP 200 · body 3850B** · 10 docs |
| 6+ | /api/experience/{id} 单条返完整 (有 content_md) | ✅ | **HTTP 200 · body 2748B** · id=exp-e25c39e8 · content_md len=1674 |

### 详细 7 验证 (含回归 + 边界)

```
A1  GET /api/experiences (default limit=3)       → HTTP 200 · 1096B · 0.20s
A2  GET /api/experiences?limit=10                 → HTTP 200 · 3850B · 0.15s
A3  GET /api/experiences?limit=15                 → HTTP 200 · 5497B · 0.13s
A4  GET /api/experiences?limit=15&offset=5        → HTTP 200 · 3669B · 0.14s
A5  GET /api/experience/exp-e25c39e8 (单条)        → HTTP 200 · 2748B · 0.10s
A6  GET /api/health                              → HTTP 200 · fts5 + live
A7  GET /api/experiences?limit=16 (越界 max=15)    → HTTP 422 (Pydantic 拒绝, ✓)

回归:
  POST /api/chat {q:"B787 风挡 AOG 处理"}        → HTTP 200 · 2135B · 4.1s
    references: 5 (3 exp + 2 city fallback, score 0.8 / 0.4)  ← 无回归
  GET  / (frontend)                                → HTTP 200 · 23296B
  GET  /experiences (frontend list page)            → HTTP 200 · 18206B (1.24s, 含 "保障经验" "B787")
```

### 关键验证 (数据内容)

**A1 (default limit=3) ids**:
```
['exp-93511f1c', 'exp-95693d77', 'exp-593dbe10']
keys = ['category', 'id', 'related_pn', 'source_path', 'status', 'summary', 'tags', 'title', 'updated_at']
has content_md? False  ✓
```

**A2 (limit=10) ids**:
```
['exp-93511f1c', 'exp-95693d77', 'exp-593dbe10', 'exp-b43450fa', 'exp-0e3e728b',
 'exp-be443ab9', 'exp-e8524b59', 'exp-edf85d6b', 'exp-b55d3ade', 'exp-be5dda3d']
```

**A3 (limit=15) ids** (KB 共 15 经验):
```
['exp-93511f1c', 'exp-95693d77', 'exp-593dbe10', 'exp-b43450fa', 'exp-0e3e728b',
 'exp-be443ab9', 'exp-e8524b59', 'exp-edf85d6b', 'exp-b55d3ade', 'exp-be5dda3d',
 'exp-feee4cb1', 'exp-c1c22dff', 'exp-e25c39e8', 'exp-3a73d6ac', 'exp-73b98b84']
```

**A4 (limit=15 offset=5)**: A4[0] = 'exp-be443ab9' = A3[5] ✓ (offset 跳前 5 个)

**A5 (单条 exp-e25c39e8)**:
```
has content_md? True, content_md len=1674
id=exp-e25c39e8, title=B787 风挡AOG处理流程
```

**A7 (limit=16 越界)**:
```json
{"detail":[{"type":"less_than_equal","loc":["query","limit"],
"msg":"Input should be less than or equal to 15","input":"16","ctx":{"le":15}}]}
```

---

## Git chain

```
a5ea5db (HEAD -> main)  merge: /api/experiences 加 limit/offset (NSM-2 endpoint fix)
c840b73 (fix/experiences-limit-offset)  feat(api): /experiences 加 limit/offset + 排除 content_md
eec1039                  docs(plan/goal/delivery): Wave 3 MVP 上线 - 4 文档收尾 + 决策链 + 公网 URL
```

**diff stat**:
```
aog-web/backend/aog_web/api/experiences.py     | 40 ++++++++++++++++++++++-----
aog-web/backend/aog_web/models/experience.py   | 18 +++++++++++++
2 files changed, 51 insertions(+), 7 deletions(-)
```

`worktrees/ep-fix` (branch `fix/experiences-limit-offset`) 保留 (worktree protocol).

---

## 关键工程决策 (下次部署参考)

1. **不要用 CosBucketName 路径** — SCF 内部 assume-role 失败, 但 SDK 返回 OK (假成功, 0.3s).
   验证必须 `GetFunction` 看 `Status=Active` + `CodeResult=success` + `StatusReasons=[]`。
2. **改用 inline ZipFile** — 13.9MB < 20MB 上限, b64 18.5M chars, 3.4s 真成功。
3. **越界 max=15 走 Pydantic** — FastAPI 自动 422, 不需要业务层额外校验。
4. **list 拿全集 + in-memory slice** — 15 条数据, SQL LIMIT 不必要, 过滤/排序都在 service 层 (client.list_experiences)。
5. **content_md strip 走 Pydantic** — `ExperienceSummary.model_validate(e)` 自动 drop 未声明字段, 比手写 dict 排除更稳。

## 后续待办 (低优先, 不阻塞)

- [ ] **zip > 20MB 时**: 需要修复 SCF 内部 assume TCB_QcsRole 读私桶 (CFS 权限/Role 绑定) 或改用预签名 URL
- [ ] **FTS5 + aog.db**: 仍是 28.4MB + 10.1MB, 在 `/tmp` 启动时从 COS 拉 (cold start 30-60s, 当前 4.7s 命中 warm instance)
- [ ] **前端 /experiences 页面**: 当前 static 渲染, 已支持 limit param via query string, 不需要改
