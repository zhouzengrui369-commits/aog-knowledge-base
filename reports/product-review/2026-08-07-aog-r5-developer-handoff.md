# AOG R5 · Developer Handoff Prompt

你是 AOG Knowledge Base PR #16 的开发/部署线程。请根据 Codex 阻塞报告恢复一轮可验收的 Same-SHA 候选。

## 目标

把 PR #16 当前产品策略固化为一个新的冻结候选，并交付可由 Codex 在真实本地 UI 上独立验收的干净运行时。

## 当前事实

- 旧验收合同冻结：`89f9cc6486920e8d449d22671a0974cae037325f`
- 当前 PR head：`a8ed848dbac3e07ddac3bf84187e3b7444a549c2`
- 当前 head 比旧候选前进 18 个 commit
- 旧本地候选工作树不干净：1 个未跟踪 `node_modules` symlink + 8 个未跟踪审计产物
- 当前 head 的 4 个 GitHub workflow 均为 success，但这不是本地运行时/产品体验证明
- 旧候选的未跟踪审计产物提出过 PII 暴露假设；必须在新候选上重新验证，禁止原样上传含敏感内容的截图
- Owner 当前策略已改为：知识可见性、AI 可检索性、操作权威性三者分离

## 必做

1. 在 PR #16 上确定一个最终候选 SHA；开始部署后不得继续推进 PR head。
2. 创建专用干净 worktree，确认：
   - `git rev-parse HEAD` 等于冻结 SHA；
   - `git status --porcelain --untracked-files=all` 为空；
   - `node_modules` symlink 仅通过本地 `.git/info/exclude` 排除，不为此修改产品 `.gitignore`。
3. 生成新的 release bundle，并回报：
   - release dir；
   - release-manifest / aog.db / fts5_index.db SHA256；
   - manifest build commit；
   - backend URL 与 health 的 `status/llm_mode/rag_backend`；
   - frontend URL 与 HTTP 200。
4. 按当前 Owner 策略更新 Codex 验收合同：
   - 登录用户可阅读已脱敏的各 verification status 知识；
   - AI 可检索并摘要已脱敏知识，引用必须保留 `verification_status`；
   - 非 VERIFIED 内容不得被描述为已确认操作指引、保证库存、批准动作或 SLA；
   - 非公开联系人和自由文本电话/邮箱必须脱敏；
   - public/unauthenticated surface 更严格；
   - private reasoning 不外泄；
   - review status 不得由客户端擅自升级。
5. 重点回归旧候选的 PII 暴露假设，覆盖 review detail、warehouse/logistics/content free text、AI answer、reference UI；证据必须去敏。
6. 跑完现有 required gates、RAG 8-query、真实 MiniMax 20-case、PII gate，并保留精简 receipt，不保存完整模型回答。
7. 更新 PR #16 注明 exact candidate SHA、部署 receipt、当前策略合同与待 Codex 验收状态。

## 禁止

- 不得 merge PR #16；
- 不得腾讯云部署或 release；
- 不得修改 Owner 数据或 review status；
- 不得上传真实联系人、电话、邮箱、正文或未去敏截图；
- 不得把 CI green 或 MiniMax PASS 当作 Codex 产品验收 PASS；
- 不得复用旧 SHA 的浏览器结论冒充当前 head 结论。

## 交付给 Codex

严格回报：

```text
CANDIDATE_SHA=
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
RAG_8_QUERY_RESULT=
RAG_20_CASE_RESULT=
RAG_20_FAILURES=
PII_FORBIDDEN_HITS=
PII_VALUES_SKIPPED=
SOURCE_KB_WRITE_COUNT=0
CLOUD_WRITE_COUNT=0
CODE_CHANGE_AFTER_FREEZE=0
CODEX_ACCEPTANCE_CONTRACT_PATH=
REMAINING_BLOCKERS=
```

完成后只通知 Codex 开始新一轮 Same-SHA 本地产品验收，不要自行宣布 Owner Gate 或 Tencent Cloud Gate 通过。
