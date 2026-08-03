# MiniMax Code 本地部署与验收指令

> 模式：只跑、只验、只记录；未经 Owner 另行批准不得修改源码、提交 Git、上传 COS 或部署 CloudBase。

## 角色

你是 AOG Knowledge Base 的本地部署与验收执行器。GitHub 远程开发已经完成代码修改；你的职责是从指定 main SHA 重建本地产物、启动真实后端与前端、执行真实数据和真实 MiniMax Provider 验收，并输出可复核证据。

## 硬边界

- 不改源码；
- 不生成补丁；
- 不 commit、push、merge；
- 不覆盖已有本地部署记录，先读取并复用现有 venv、node_modules、`.env.local`、release 目录和启动脚本；
- 不打印或提交 MiniMax、COS、JWT、访问密码；
- 不写 Owner 的只读知识源；
- 不使用 mock；
- 任一身份、依赖、数据、PII 或 Provider Gate 失败立即停止，按原错误回报。

## 1. Git 身份门

```bash
cd /Users/njx/Project/AOG知识库
git fetch origin
git checkout main
git pull --ff-only origin main

FINAL_SHA=$(git rev-parse HEAD)
git status --porcelain
```

必须满足：

```text
git status = clean
FINAL_SHA = Owner/ChatGPT 最终交付 SHA
```

不得自行切换到旧 PR、integration 或 review 分支。

## 2. 环境与密钥门

只检查是否存在，不回显值：

```bash
for name in MINIMAX_API_KEY JWT_SECRET AOG_VIEW_PASSWORD; do
  test -n "${!name:-}" || { echo "BLOCKED_MISSING_$name"; exit 2; }
done
```

本地必须设置：

```bash
export ALLOW_MOCK=false
export STRICT_LLM=true
export SYNC_ENABLED=false
export NEXT_PUBLIC_ALLOW_MOCK=false
export NEXT_PUBLIC_DEBUG=false
export NEXT_PUBLIC_DEBUG_THOUGHTS=false
```

## 3. Python 与前端依赖

优先复用现有环境；缺失时才安装。

```bash
cd aog-web/backend
python3.11 -m venv .venv  # 仅在 .venv 不存在时
. .venv/bin/activate
python -m pip install -e .
python -m pip install pytest pytest-asyncio aiosqlite sqlalchemy fastapi 'uvicorn[standard]' pypinyin python-frontmatter python-docx openpyxl pypdf markdown-it-py
python -m compileall -q aog_web

cd ../pipeline
python3.11 -m venv .venv  # 仅在 .venv 不存在时
. .venv/bin/activate
python -m pip install -e .

cd ../frontend
corepack enable
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm lint
pnpm test
pnpm build
```

## 4. 真实数据发布门

不要复用旧 commit 生成的 release hash。

```bash
cd /Users/njx/Project/AOG知识库
export AOG_KB_ROOT="/Users/njx/Project/AOG知识库/AOG知识库"
export APP_COMMIT_SHA="$FINAL_SHA"
export RELEASE_DIR="$(mktemp -d /tmp/aog-local-final.XXXXXX)"
bash aog-web/scripts/build-data-release.sh
```

必须确认：

- source files failed = 0；
- 8-query RAG = PASS；
- PII-7a v2 forbidden hits = 0；
- wiki source/sanitized/FTS5 count 相等且大于 0；
- `release-manifest.json` 已生成；
- 不修改源 wiki 和 Owner 原始知识库。

将 release 文件路径配置给后端，但不得上传 COS。

## 5. 启动真实本地服务

终端 A：

```bash
cd /Users/njx/Project/AOG知识库/aog-web/backend
. .venv/bin/activate
export SQLITE_PATH="$RELEASE_DIR/aog.db"
export AOG_DB_PATH="$RELEASE_DIR/aog.db"
export FTS5_PATH="$RELEASE_DIR/fts5_index.db"
export RAG_BACKEND=fts5
export ALLOW_MOCK=false
export STRICT_LLM=true
export SYNC_ENABLED=false
uvicorn aog_web.main:app --host 127.0.0.1 --port 8088
```

终端 B：

```bash
cd /Users/njx/Project/AOG知识库/aog-web/frontend
export NEXT_PUBLIC_API_BASE=http://127.0.0.1:8088
export NEXT_PUBLIC_ALLOW_MOCK=false
export NEXT_PUBLIC_DEBUG=false
export NEXT_PUBLIC_DEBUG_THOUGHTS=false
pnpm dev --hostname 127.0.0.1 --port 3000
```

## 6. API 验收

登录后保存 Cookie：

```bash
COOKIE_JAR=$(mktemp)
curl -fsS -c "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"$AOG_VIEW_PASSWORD\"}" \
  http://127.0.0.1:8088/api/auth/login >/dev/null
```

验证：

```bash
curl -fsS -b "$COOKIE_JAR" http://127.0.0.1:8088/api/auth/verify
curl -fsS -b "$COOKIE_JAR" http://127.0.0.1:8088/api/stats
curl -fsS -b "$COOKIE_JAR" 'http://127.0.0.1:8088/api/experiences?limit=15'
curl -fsS -b "$COOKIE_JAR" 'http://127.0.0.1:8088/api/city/B-%E5%8C%97%E4%BA%AC%E5%A4%A7%E5%85%B4'
curl -fsS -b "$COOKIE_JAR" 'http://127.0.0.1:8088/api/city/H-%E8%B5%AB%E5%B0%94%E8%BE%9B%E5%9F%BA'
```

验收点：

- `/api/stats` 与首页数字一致；
- 空壳经验不在列表，直接详情为 404；
- VERIFIED 城市展示可执行数据；
- UNVERIFIED 城市 contacts/fleet/parts 为空且有禁止使用提示；
- 同一城市连续访问后 `view_count` 递增；
- HU 与 JD 名称独立；冲突联系方式不公开；
- Cookie 登录后切换至少 5 个路由不重复输入密码。

## 7. 浏览器黄金旅程

使用真实浏览器操作：

1. 登录；
2. 首页确认动态数字；
3. 打开北京大兴；
4. 切换预案、联系人、备件、物流、仓储；
5. 打开一个 UNVERIFIED 城市，确认可执行数据全部隐藏；
6. 打开保障经验，确认至少 3 条有正文；
7. 输入 B787 风挡问题，确认无 CoT、无 chunk ID、引用可打开、表格正常、回答不截断；
8. 在首页和城市间切换 5 次，确认不重复登录；
9. 打开不存在路径，确认 404 没有错误 PKX/经验数字；
10. 确认全站只有一个浮动 AI 入口和一个首页内联入口。

截图与 inspect 记录写入本地 evidence 目录，不要伪造。

## 8. 20 题 RAG 压测

```bash
cd /Users/njx/Project/AOG知识库/aog-web/pipeline
. .venv/bin/activate
python -m scripts.run_rag_pressure \
  --base-url http://127.0.0.1:8088 \
  --output /tmp/aog-rag-pressure-result.json
```

必须 `0/20` 失败。

## 9. 最终输出格式

只输出 `PASS`、`BLOCKED` 或 `FAIL`，并包含：

```text
FINAL_SHA
RELEASE_DIR
RELEASE_MANIFEST_SHA256
AOG_DB_SHA256
FTS5_SHA256
BACKEND_TESTS
FRONTEND_TESTS
API_STATS_RESULT
EMPTY_EXPERIENCE_RESULT
UNVERIFIED_REDACTION_RESULT
AUTH_5_ROUTE_RESULT
RAG_20_CASE_RESULT
BROWSER_GOLDEN_JOURNEY_RESULT
SCREENSHOT_PATHS
REMAINING_BLOCKERS
```

本地验收通过也不代表 CloudBase 已部署；没有 Owner 明确授权不得执行云端写操作。
