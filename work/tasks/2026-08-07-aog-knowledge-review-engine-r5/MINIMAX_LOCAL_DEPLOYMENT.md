# MiniMax Code Contract — GOAL-AOG-KNOWLEDGE-R5

## Role

Local deployment and technical-evidence runner only. ChatGPT owns source changes. Do not repair code locally.

## Authority

Use only the exact R5 candidate SHA posted by Parent PM on the R5 Draft PR after every required GitHub workflow passes.

```text
REPOSITORY=zhouzengrui369-commits/aog-knowledge-base
BRANCH=chatgpt/aog-knowledge-review-engine-r5
CANDIDATE_SHA=<PARENT_PM_EXACT_SHA>
LOCAL_REPO=/Users/njx/Project/AOG知识库
MODE=LOCAL_ONLY
```

## Reuse existing local assets

Read and reuse `reports/MINIMAX-LOCAL-DEPLOYMENT.md`, existing venvs/node_modules, build-data-release scripts and prior local launch knowledge where compatible. Do not create a second deployment system.

## Forbidden

- source/test/doc edits;
- commit/push/merge/rebase/amend;
- verification-status changes;
- real source-data writes;
- CloudBase/COS/Tencent Cloud writes;
- printing secrets;
- mock mode.

## Required local run

1. Fetch exact candidate and materialize a clean worktree/detached checkout.
2. Prove local HEAD = candidate SHA and clean tree before run.
3. Reuse/install dependencies only as necessary.
4. Build a fresh release with `aog-web/scripts/build-data-release.sh` bound to candidate SHA.
5. Prove 8-query RAG PASS, PII forbidden hits=0 and release manifest identity.
6. Start backend on `127.0.0.1:8088` with real local release and live provider.
7. Start frontend on `127.0.0.1:3000` with mock/debug disabled.
8. Login using existing local credential without printing it.
9. Technical smoke:
   - `/api/review/cities` unauthenticated = 401;
   - authenticated `/api/review/cities` = 200 and contains non-VERIFIED backlog;
   - authenticated review detail for a real pending city returns candidate content;
   - the same normal `/api/city/{code}` remains fail-closed/hidden;
   - strict chat emits no private reasoning and uses VERIFIED-only context;
   - existing 20-case real MiniMax pressure suite = 0/20 failures.
10. Verify `/review` and one `/review/city/{code}` return/render successfully enough for Codex to start.
11. Re-prove exact HEAD and clean worktree after run.

## Receipt

```text
GOAL=AOG-KNOWLEDGE-R5
STATUS=PASS|PARTIAL_PASS|BLOCKED|FAIL
CANDIDATE_SHA=
LOCAL_HEAD=
WORKTREE_CLEAN_BEFORE=
WORKTREE_CLEAN_AFTER=
RELEASE_MANIFEST_SHA256=
AOG_DB_SHA256=
FTS5_SHA256=
RAG_8_QUERY=
PII_FORBIDDEN_HITS=
RAG_20_CASE=
BACKEND=http://127.0.0.1:8088
FRONTEND=http://127.0.0.1:3000
REVIEW_UNAUTH_401=
REVIEW_QUEUE_200=
PENDING_DETAIL_VISIBLE=
NORMAL_PENDING_FAIL_CLOSED=
STRICT_AI_VERIFIED_ONLY=
PRIVATE_REASONING_ABSENT=
SANITIZED_LOG_PATHS=
REMAINING_BLOCKERS=
```

Success status for MiniMax is `PASS_TECHNICAL_LOCAL_READY_FOR_CODEX`. It does not authorize cloud deployment, merge or release.