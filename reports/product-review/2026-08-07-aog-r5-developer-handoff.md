# AOG R5 · MiniMax Exact-SHA Redeploy Handoff

你是 AOG Knowledge Base PR #16 的本地部署与技术验收执行器。远端 Parent PM 已冻结最终候选；本轮不得开发。

## 目标

在当前 Owner 策略下，基于唯一冻结 SHA 创建一个干净、可重放、可交给 Codex 做真实浏览器 Same-SHA 验收的本地运行时。

## 冻结事实

```text
REPOSITORY=zhouzengrui369-commits/aog-knowledge-base
PR=16
PR_BRANCH=chatgpt/aog-knowledge-review-engine-r5
FROZEN_CANDIDATE_SHA=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
BASE=main@62d53b42e7994131a762f93db0e0410e4a917ce3
PR_STATE=OPEN_DRAFT
```

验收开始后禁止推进 PR #16 head。任何新的产品/source commit 都使本轮 receipt 失效。

该 SHA 的 GitHub workflows 已由 Parent PM 核验为 success：

- parent-pm-governance `31153554806`
- production-readiness `31153554808`
- aog-ci `31153554823`
- staging-validation `31153554798`

CI 不是本地运行态 PASS。

## 当前 Owner 策略

```text
knowledge visibility != verification status
AI retrievability != operational authority
```

1. 登录用户可阅读、搜索已脱敏的各 verification status 知识，只要 source/candidate content 存在。
2. 登录 AI 可检索和摘要已脱敏知识；每个 reference 必须保留真实 `verification_status`。
3. 非 VERIFIED 内容不得成为确认操作指引、保证库存、批准动作或 SLA。
4. 非公开电话、邮箱以及 content/warehouse/logistics 等自由文本 PII 必须脱敏。
5. public/unauthenticated surface 更严格，不得暴露 pending candidate content。
6. private reasoning、system prompt、chain-of-thought 不得外泄。
7. 不允许客户端擅自把 review status 升级为 VERIFIED。

## 绝对禁止

- 不改源码；
- 不改测试/fixture/评分器/PII allowlist；
- 不 commit/push；
- 不 merge PR #16；
- 不把 PR 转 Ready；
- 不修改 Owner 数据或 review status；
- 不执行腾讯云/COS/Hosting/DNS 写操作；
- 不 release；
- 不用 mock 替代真实 MiniMax 20-case；
- 不保存 Secret、Cookie、JWT、密码；
- 不把真实非公开联系人、电话、邮箱、完整敏感正文或完整模型回答写入 evidence；
- 不复用旧 SHA 的浏览器结论冒充当前候选。

## Step 1 — 创建专用干净 worktree

主仓库按实际路径定位；推荐：

```bash
REPO="/Users/njx/Project/AOG知识库"
CANDIDATE="a8ed848dbac3e07ddac3bf84187e3b7444a549c2"
WORKTREE="/Users/njx/Project/aog-r5-same-sha-a8ed848"

cd "$REPO"
git fetch origin

git cat-file -e "${CANDIDATE}^{commit}" || {
  echo "BLOCKED_CANDIDATE_NOT_FETCHED"
  exit 2
}

if [ -e "$WORKTREE/.git" ]; then
  cd "$WORKTREE"
  test "$(git rev-parse HEAD)" = "$CANDIDATE" || {
    echo "BLOCKED_EXISTING_WORKTREE_WRONG_SHA"
    exit 2
  }
else
  git worktree add --detach "$WORKTREE" "$CANDIDATE"
  cd "$WORKTREE"
fi
```

如果需要复用主仓库已有 `node_modules`，只能用 symlink，并只通过该 worktree 的本地 exclude 排除：

```bash
mkdir -p "$(git rev-parse --git-dir)/info"
printf '%s\n' 'aog-web/frontend/node_modules' >> "$(git rev-parse --git-dir)/info/exclude"
```

不要修改产品 `.gitignore`。

最终必须：

```bash
test "$(git rev-parse HEAD)" = "$CANDIDATE"
test -z "$(git status --porcelain --untracked-files=all)"
```

否则立即：

```text
BLOCKED_CANDIDATE_IDENTITY_OR_WORKTREE
```

## Step 2 — Source identity before build

只读 Owner source tree。不要打印文件正文或联系人值。

按项目现有方法生成 source-tree identity，并保存 hash 值：

```text
SOURCE_TREE_HASH_BEFORE=<sha256>
```

不得修改 source tree。

## Step 3 — Exact-SHA release bundle

只使用 frozen candidate 和 Owner 已存在的本地知识源，重新执行仓库当前 `build-data-release.sh` 合同。

```bash
cd "$WORKTREE"
export APP_COMMIT_SHA="$CANDIDATE"
export ALLOW_MOCK=false
export STRICT_LLM=true
export SYNC_ENABLED=false
export RELEASE_DIR="$(mktemp -d /tmp/aog-r5-a8ed848.XXXXXX)"

bash aog-web/scripts/build-data-release.sh
```

如果项目要求 `AOG_KB_ROOT` 或已有 wiki sanitized snapshot，按当前仓库合同和 Owner 已存在的本地源配置；不得修改 Owner source，也不得导入新的真实数据。

必须得到仓库当前 release contract 的完整 bundle，并验证 manifest build commit 为 frozen candidate。

重新计算：

```bash
shasum -a 256 \
  "$RELEASE_DIR/release-manifest.json" \
  "$RELEASE_DIR/aog.db" \
  "$RELEASE_DIR/fts5_index.db"
```

记录：

```text
RELEASE_DIR=
RELEASE_MANIFEST_SHA256=
AOG_DB_SHA256=
FTS5_SHA256=
RELEASE_BUILD_COMMIT=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
```

不要把 manifest 正文或知识正文复制到 evidence。

## Step 4 — 重点 PII 回归

旧候选存在“可能暴露 non-public PII”的审核假设。必须在新 frozen SHA 上重新验证，禁止继承旧结论。

覆盖至少：

- review detail structured contacts；
- `content_md` free text；
- warehouse free text；
- logistics free text；
- authenticated normal knowledge browsing；
- AI answer；
- AI reference snippet/card。

验证：

```text
NONPUBLIC_PHONE_VISIBLE_COUNT=0
NONPUBLIC_EMAIL_VISIBLE_COUNT=0
FREE_TEXT_PRIVATE_PHONE_VISIBLE_COUNT=0
FREE_TEXT_PRIVATE_EMAIL_VISIBLE_COUNT=0
AI_PII_REINTRODUCTION_COUNT=0
```

Public contact 数据只按现有 permission model 判断，不得擅自把 public 数据重新分类。

Evidence 只能保存计数、status、route hash 和脱敏截图；不能保存真实 private values。

## Step 5 — Required automated/runtime gates

不修改 case、fixture、评分器、阈值和 allowlist。

### RAG 8-query

运行仓库当前 8-query regression：

```text
RAG_8_QUERY_RESULT=8/8_PASS
```

### 真实 MiniMax 20-case

使用 frozen backend + frozen FTS5 + real MiniMax：

```text
RAG_20_CASE_RESULT=20/20_PASS
RAG_20_FAILURES=0
```

禁止 mock、skip、降阈值。

### PII Gate

运行仓库当前 PII Gate。成功条件按当前仓库 contract；至少回报：

```text
PII_FORBIDDEN_HITS=0
PII_VALUES_SKIPPED=0
```

若当前正式 gate 对 `values_skipped` 定义不同，必须原样报告仓库规则，不得静默改判定。

## Step 6 — 启动 exact-SHA backend

只检查 Secret 是否存在，不输出值。

```bash
for name in MINIMAX_API_KEY JWT_SECRET AOG_VIEW_PASSWORD; do
  test -n "${!name:-}" || { echo "BLOCKED_MISSING_${name}"; exit 2; }
done
```

按仓库当前路径启动 backend，核心环境：

```bash
export SQLITE_PATH="$RELEASE_DIR/aog.db"
export AOG_DB_PATH="$RELEASE_DIR/aog.db"
export FTS5_PATH="$RELEASE_DIR/fts5_index.db"
export RAG_BACKEND=fts5
export ALLOW_MOCK=false
export STRICT_LLM=true
export SYNC_ENABLED=false
export APP_COMMIT_SHA="$CANDIDATE"
```

启动后 health 必须只记录：

```text
BACKEND_URL=http://127.0.0.1:8088
BACKEND_STATUS=ok
BACKEND_LLM_MODE=live
BACKEND_RAG_BACKEND=fts5
```

不得保存 Secret 或完整配置响应。

## Step 7 — 启动 exact-SHA frontend

按仓库当前前端合同启动，必须：

```text
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8088
NEXT_PUBLIC_ALLOW_MOCK=false
NEXT_PUBLIC_DEBUG=false
NEXT_PUBLIC_DEBUG_THOUGHTS=false
```

记录：

```text
FRONTEND_URL=http://127.0.0.1:3000
FRONTEND_HTTP=200
```

确认 `/review`、普通知识浏览路径和 AI 助手实际可访问，但不要替 Codex 做最终产品体验 PASS。

## Step 8 — Owner-policy smoke checks

MiniMax 只做技术 smoke，不给 Codex 产品结论。

### Authenticated cross-status knowledge

验证登录用户能够读取 sanitized non-VERIFIED knowledge when content exists，并且 status 保留。

### References

验证 reference payload 包含 `verification_status`。

### Non-VERIFIED authority

对 non-VERIFIED sanitized knowledge 做一个非敏感问题，验证 AI 可以检索/摘要，但输出不声称：

- 已确认操作指引；
- 保证库存；
- 批准动作；
- confirmed SLA。

### Private reasoning

验证用户可见输出中：

```text
<think>=0
<thinking>=0
<reasoning>=0
event:think=0
system-prompt exposure=0
```

这些是技术 smoke，不替代 Codex browser acceptance。

## Step 9 — Source identity and final clean state

重新计算：

```text
SOURCE_TREE_HASH_AFTER=<sha256>
```

必须：

```text
SOURCE_TREE_HASH_BEFORE == SOURCE_TREE_HASH_AFTER
SOURCE_KB_WRITE_COUNT=0
REVIEW_STATUS_MUTATION_COUNT=0
CLOUD_WRITE_COUNT=0
```

然后：

```bash
cd "$WORKTREE"
test "$(git rev-parse HEAD)" = "$CANDIDATE"
test -z "$(git status --porcelain --untracked-files=all)"
```

必须：

```text
FINAL_SHA_MATCH=YES
FINAL_WORKTREE_CLEAN=YES
CODE_CHANGE_AFTER_FREEZE=0
GIT_COMMIT_COUNT=0
GIT_PUSH_COUNT=0
```

## Step 10 — Codex acceptance contract

Codex 当前 Same-SHA 合同路径：

```text
reports/product-review/2026-08-07-aog-r5-same-sha-local-product-acceptance.md
```

该文件位于 PR #18 docs-only review branch；它冻结的 candidate 必须等于本任务的 `a8ed848...`。

完成本地 exact-SHA receipt 后，**只通知 Codex 开始真实浏览器验收**。不要自行把 Codex/Owner/Tencent Gate 标为 PASS。

## 最终严格输出

```text
VERDICT=PASS_TECHNICAL_LOCAL_READY_FOR_CODEX | BLOCKED | FAIL
CANDIDATE_SHA=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
PR16_HEAD=
HEAD_MATCH=
WORKTREE=
WORKTREE_CLEAN=
RELEASE_DIR=
RELEASE_MANIFEST_SHA256=
AOG_DB_SHA256=
FTS5_SHA256=
RELEASE_BUILD_COMMIT=
BACKEND_URL=
BACKEND_STATUS=
BACKEND_LLM_MODE=
BACKEND_RAG_BACKEND=
FRONTEND_URL=
FRONTEND_HTTP=
AUTHENTICATED_CROSS_STATUS_KNOWLEDGE_SMOKE=
REFERENCE_STATUS_PRESERVED_SMOKE=
NONVERIFIED_OPERATIONAL_AUTHORITY_BLOCKED_SMOKE=
NONPUBLIC_PHONE_VISIBLE_COUNT=
NONPUBLIC_EMAIL_VISIBLE_COUNT=
FREE_TEXT_PRIVATE_PHONE_VISIBLE_COUNT=
FREE_TEXT_PRIVATE_EMAIL_VISIBLE_COUNT=
AI_PII_REINTRODUCTION_COUNT=
PRIVATE_REASONING_ABSENT=
RAG_8_QUERY_RESULT=
RAG_20_CASE_RESULT=
RAG_20_FAILURES=
PII_FORBIDDEN_HITS=
PII_VALUES_SKIPPED=
SOURCE_TREE_HASH_MATCH=
SOURCE_KB_WRITE_COUNT=0
REVIEW_STATUS_MUTATION_COUNT=0
CLOUD_WRITE_COUNT=0
CODE_CHANGE_AFTER_FREEZE=0
GIT_COMMIT_COUNT=0
GIT_PUSH_COUNT=0
FINAL_SHA_MATCH=
FINAL_WORKTREE_CLEAN=
CODEX_ACCEPTANCE_CONTRACT_PATH=reports/product-review/2026-08-07-aog-r5-same-sha-local-product-acceptance.md
CODEX_SAME_SHA_LOCAL_PRODUCT_ACCEPTANCE=PENDING
OWNER_LOCAL_CUSTOMER_VALUE_GATE=HOLD
TENCENT_CLOUD_GATE=HOLD
REMAINING_BLOCKERS=
```

完成后通知 Codex：对 `a8ed848dbac3e07ddac3bf84187e3b7444a549c2` 重新执行真实浏览器 Same-SHA acceptance。
