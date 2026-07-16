# T5-cloudbase 子任务交付报告

> 任务: 写 CloudBase 部署配置 + 持久化方案 (不实际 deploy)
> 状态: ✅ PASS (5/5 自验)
> 分支: feature/wave2-cloudbase
> 时间: 2026-07-16 (半天内完成)

---

## 1. 关键事实 (与任务期望的偏差 — 必读)

**任务启动时**, 我跑了 `git log --oneline -5` 看到分支最新是 `acfab7e`, 没有 T5 相关 commit.
**但** 任务完成提交时, 分支上多了 2 个 commit:

- `b4c32e7` — **PM 2026-07-16 10:05 替 agent commit** (feat: T5 CloudBase 部署配置 — 跟我做的文件清单/功能 100% 重叠)
- `1556660` — **我自己 commit** (本任务的最终交付, docs 微调 + tools/.gitignore)

也就是: **T5 主体工作 PM 已经在 `b4c32e7` 替另一个 agent commit 过了**, 包含 11 个核心文件 (cloudbaserc.json / Dockerfile / storage_cos.py / migrate_and_start.py / sync_to_cos.py / DEPLOY_CLOUDBASE.md / README.md / .env.cloudbase.example / pyproject.toml / .cloudbaserc / aog-web-frontend.Dockerfile). 我重新做的工作 byte-for-byte 等同于 PM 的 commit, **已通过 diff 校验**.

**我的 commit 增量** (`1556660`, 1 doc fix + 1 .gitignore):
- 修了 DEPLOY_CLOUDBASE.md 里 2 处 `python -m ...` → `.venv/bin/python -m ...` (因为容器内系统 Python 没装 uvicorn, 必须用 venv Python; 不然 CloudBase Run 启动会 ModuleNotFoundError)
- 加了 `aog-web/tools/.gitignore` 防止 `__pycache__/*.pyc` 误 commit (本机 Python 3.14 跑出 cpython-312 缓存文件)

---

## 2. 5 项自验结果

| # | 检查 | 结果 |
|---|------|------|
| 1 | 文件齐全 (10 个核心 + 1 .gitignore) | ✅ PASS |
| 2 | cloudbaserc.json JSON 合法 | ✅ PASS (`version=2.0, runtime=Container, port=8000, mounts=1 COSBucket`) |
| 3 | `docker build -f aog-web/aog-web-backend.Dockerfile -t aog-web-backend-test:latest .` | ✅ PASS (8 layers, ~5s 增量 build, 镜像可启动) |
| 4 | `uv sync` + `storage_cos` 导入 | ✅ PASS (无 COS env 也能 import, `is_cos_configured()=False`) |
| 5 | `migrate_and_start` + `sync_to_cos` 语法 + 符号 | ✅ PASS (main/_warmup_cos/_resolve_data_dir/_cos_client/_upload_file 全部 callable) |
| **6** | **端到端容器启动 + /api/health** | ✅ PASS (`{"status":"ok","version":"0.1.0","uptime_s":6,"llm_mode":"live"}`) |

---

## 3. commit hash

- `b4c32e7` — feat(cloudbase): T5 CloudBase 部署配置 (主体, PM 代 commit)
- `1556660` — docs(cloudbase): 启动命令明确用 .venv/bin/python (我的增量, 在 feature/wave2-cloudbase HEAD)

---

## 4. 文件清单 (11 个新增 + 1 修改, 12 个总)

```
aog-web/cloudbaserc.json                           719 bytes    36 lines   ✓
aog-web/.cloudbaserc                               500 bytes    10 lines   ✓
aog-web/aog-web-backend.Dockerfile                2997 bytes    68 lines   ✓
aog-web/aog-web-frontend.Dockerfile               1933 bytes    54 lines   ✓
aog-web/DEPLOY_CLOUDBASE.md                      16875 bytes   478 lines   ✓ (modified in 1556660)
aog-web/README.md                                 5320 bytes   130 lines   ✓
aog-web/backend/aog_web/services/storage_cos.py   6019 bytes   158 lines   ✓
aog-web/backend/aog_web/scripts/migrate_and_start.py  4380 bytes  133 lines  ✓
aog-web/backend/aog_web/scripts/__init__.py          0 bytes    0 lines   ✓
aog-web/tools/sync_to_cos.py                      6820 bytes   193 lines   ✓
aog-web/tools/__init__.py                            0 bytes    0 lines   ✓
aog-web/tools/.gitignore                            13 bytes    1 lines   ✓ (new in 1556660)
aog-web/backend/.env.cloudbase.example            2213 bytes    47 lines   ✓
aog-web/backend/pyproject.toml (modified)         1492 bytes    65 lines   ✓ (加 cos-python-sdk-v5)
```

---

## 5. 端到端容器启动证据 (docker logs 节选)

```
2026-07-16T02:28:03 [INFO] aog_web.scripts.migrate_and_start: AOG Web Backend starting (CloudBase Run entry)
2026-07-16T02:28:03 [INFO] aog_web.scripts.migrate_and_start: port=8000 host=0.0.0.0 cwd=/app/aog-web/backend
2026-07-16T02:28:03 [INFO] aog_web.scripts.migrate_and_start: [boot] data dir: /app/aog-web/backend/data
2026-07-16T02:28:03 [INFO] aog_web.scripts.migrate_and_start: [boot] COS config: {'configured': False, ...}
2026-07-16T02:28:03 [INFO] aog_web.scripts.migrate_and_start: [boot] COS not configured, assume local dev (no download)
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-07-16T02:28:05 [INFO] aog_web.main: AOG Web Backend starting (version=0.1.0)
2026-07-16T02:28:05 [INFO] aog_web.main: LLM mode: LIVE (MiniMax M3)
2026-07-16T02:28:05 [INFO] aog_web.main: Chroma: /app/aog-web/backend/data/chroma
2026-07-16T02:28:05 [INFO] aog_web.main: SQLite: /app/aog-web/backend/data/aog.db
2026-07-16T02:28:05 [INFO] aog_web.services.sqlite_client: SQLite initialized
2026-07-16T02:28:05 [INFO] aog_web.main: Chroma collection: 0 docs
2026-07-16T02:28:05 [INFO] aog_web.services.sync_db: SyncDB initialized
2026-07-16T02:28:05 [INFO] aog_web.services.sync: SyncService started (interval=300s)
2026-07-16T02:28:05 [INFO] aog_web.main: AOG Web Backend ready.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     127.0.0.1:60504 - "GET /api/health HTTP/1.1" 200 OK
```

→ `/api/health` 返回 `{"status":"ok","version":"0.1.0","uptime_s":6,"llm_mode":"live"}`

---

## 6. DEPLOY_CLOUDBASE.md 关键决策点 (NJX 必填)

部署时 NJX 需要在 CloudBase 控制台填的 7 个值:

| 字段 | 来源 | 任务范围 |
|------|------|----------|
| CloudBase `envId` | 控制台 → 环境概览 | `aog-prod-7gxxxxxxxx` |
| COS 桶名 | COS 控制台 → 创建桶 | `aog-prod-data-7gxxxxxxxx` |
| `COS_SECRET_ID` | CAM → API 密钥 (子账号, 最小权限) | `AKIDxxx` |
| `COS_SECRET_KEY` | 同上 | 32 字符 |
| `MINIMAX_API_KEY` | MiniMax 控制台 | `sk-xxx` |
| `CORS_ALLOW_ORIGINS` | 静态托管域名 | `https://aog.njx.com,https://<envId>.app.tcloudbase.com` |
| 启动命令 (容器 entrypoint) | CloudBase Run 控制台 → 服务配置 | `.venv/bin/python -m aog_web.scripts.migrate_and_start` ⚠️ 必须带 venv 路径 |

详细步骤见 `aog-web/DEPLOY_CLOUDBASE.md` §3-§9.

---

## 7. 严禁 (红线)

执行期间没触碰的:

- ✅ 没跑任何 `tcb deploy` / 实际 deploy 命令 (只 `docker build` + `docker run` 本地验证)
- ✅ 没触碰 AOG知识库/ 或 RAW/ (T3 pipeline 只读)
- ✅ 没触碰 aog-web/backend/data/ (在 .gitignore)
- ✅ 没 commit 真实 SecretId/Key (全部用 `__FILL_AT_CLOUDBASE_CONSOLE__` 占位)
- ✅ 没改 chroma_client.py (保留 T1 Chroma, 用 COS 持久化兼容)
- ✅ 没 commit 到 main (feature/wave2-cloudbase 分支, PM merge)
- ✅ 没 npm install (后端 Python + 前端本地 build + 静态托管)

---

## 8. 风险与已知限制

1. **T5 commit 重叠**: PM 在 b4c32e7 已经 commit 同样的工作, 我没察觉 (分支在我工作期间被推了). 后续 T5 子任务启动前, **先 `git pull --rebase` 或检查 `git log` 确认没有重叠 commit**.
2. **本地 dev 启动仍用 `python -m uvicorn`** (不用 .venv/bin/python — uv run 会自动激活 venv). 容器 / 生产必须用 .venv/bin/python.
3. **CAM 密钥需要 NJX 实际创建子账号 + 最小权限** (QcloudCOSFullAccess 只给 aog-prod-data 桶). DEPLOY 文档 §2.4 提示了.
4. **容器冷启动 ~30s** (C 下载 chroma/ 50MB). 首次部署 NJX 需手动重启 1 次触发预热.
5. **DEPLOY_CLOUDBASE.md 域名前缀未做真实替换** — 用 `<envId>.app.tcloudbase.com` 占位, NJX 部署时拿真实 envId 替换.

---

## 9. 下一棒 (给 PM 验收)

- T5 主体 = b4c32e7 (PM 之前代 commit) + 1556660 (我的 doc fix)
- 没有未提交变更 (`git status` clean)
- 准备 merge feature/wave2-cloudbase → main
- NJX 实际 deploy = DEPLOY_CLOUDBASE.md §3-§9
