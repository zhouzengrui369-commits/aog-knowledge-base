# MiniMax Code Contract — GOAL-AOG-ISSUE12-R4

## Role

You are the local deployment and technical-evidence runner. ChatGPT owns source fixes. Do not repair code locally.

## Authority input

Use only the exact candidate SHA that Parent PM records in the R4 Draft PR after all required GitHub workflows pass.

```text
REPOSITORY=zhouzengrui369-commits/aog-knowledge-base
BRANCH=chatgpt/issue12-p0-runtime-closure-r4
CANDIDATE_SHA=<PARENT_PM_EXACT_SHA>
LOCAL_REPO=/Users/njx/Project/AOG知识库
```

If branch, fetched object, local HEAD, dirty state, or candidate SHA do not match the handoff, return `BLOCKED_IDENTITY_DRIFT`.

## Reuse, do not reinvent

Read and reuse `reports/MINIMAX-LOCAL-DEPLOYMENT.md`, existing venvs, node_modules, release scripts, and start commands where compatible. This R4 contract narrows that document: MiniMax deploys and gathers technical receipts; Codex owns independent browser/product/VoiceOver acceptance.

## Forbidden

- source/test/document edits;
- commit, amend, rebase, merge, push or force-push;
- real knowledge-source modification;
- verification-status changes;
- CloudBase/COS writes;
- credential output;
- mock mode;
- silent online fallback after a fail-closed Gate.

## Required technical run

1. Fetch and materialize the exact candidate in a clean worktree.
2. Prove `HEAD == CANDIDATE_SHA` and clean tracked/untracked state before run.
3. Confirm required secrets exist without printing values.
4. Set `ALLOW_MOCK=false`, `STRICT_LLM=true`, `SYNC_ENABLED=false`, frontend mock/debug false.
5. Rebuild release data for this SHA with `aog-web/scripts/build-data-release.sh`.
6. Prove:
   - source failures = 0;
   - 8-query RAG = PASS;
   - PII-7a v2 forbidden hits = 0;
   - wiki source/sanitized/FTS5 counts equal and >0;
   - release manifest exists.
7. Start backend on `127.0.0.1:8088` and frontend on `127.0.0.1:3000` using that release.
8. API smoke: auth verify, stats, experiences, one VERIFIED city, one UNVERIFIED city.
9. Run the existing 20-case real MiniMax RAG pressure suite; required result `0/20` failures.
10. Capture sanitized service logs and exact release hashes.
11. Re-prove clean worktree and exact candidate HEAD after run.

## R4-specific smoke assertions

Using API/SSE only, prove before Codex starts:

- an UNVERIFIED target returns `UNVERIFIED / 不可用于操作`;
- protected UNVERIFIED content is absent from public response;
- the stream contains no `event: think`;
- the stream contains no `<think>`, `<thinking>`, `<reasoning>` or provider-private reasoning text;
- a VERIFIED control response contains only VERIFIED references;
- error is terminal and is not followed by done.

Do not use private contact values in the receipt; report semantic pass/fail only.

## Receipt

Return:

```text
GOAL=AOG-ISSUE12-R4
STATUS=PASS|PARTIAL_PASS|BLOCKED|FAIL
CANDIDATE_SHA=
LOCAL_HEAD=
WORKTREE_CLEAN_BEFORE=
WORKTREE_CLEAN_AFTER=
RELEASE_DIR=
RELEASE_MANIFEST_SHA256=
AOG_DB_SHA256=
FTS5_SHA256=
RAG_8_QUERY=
PII_FORBIDDEN_HITS=
RAG_20_CASE=
BACKEND_START=
FRONTEND_START=
UNVERIFIED_BOUNDARY_SMOKE=
PRIVATE_REASONING_ABSENT=
VERIFIED_REFERENCE_SMOKE=
ERROR_TERMINAL_SMOKE=
SANITIZED_LOG_PATHS=
REMAINING_BLOCKERS=
```

A MiniMax PASS is technical deployment evidence only. It does not close Codex Product Experience or Human Owner gates.
