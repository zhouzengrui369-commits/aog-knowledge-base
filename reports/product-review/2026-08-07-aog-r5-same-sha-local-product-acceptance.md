# AOG Knowledge Base R5 · Codex Same-SHA Local Product Acceptance

- Date: 2026-08-07 (Asia/Shanghai)
- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Pull request: #16
- Acceptance contract candidate: `89f9cc6486920e8d449d22671a0974cae037325f`
- Current PR head observed through GitHub: `a8ed848dbac3e07ddac3bf84187e3b7444a549c2`
- Verdict: **BLOCKED**
- Blockers: `CANDIDATE_IDENTITY_OR_WORKTREE`, `BLOCKED_GITHUB_HEAD_DRIFT`

## Executive decision

This round cannot produce a Same-SHA product-acceptance PASS, PARTIAL PASS, or FAIL for the current PR head.

The acceptance contract freezes SHA `89f9cc6...`, while PR #16 currently points at `a8ed848...`. GitHub comparison shows the PR head is 18 commits ahead of the contract candidate and changes backend review/AI behavior, frontend review behavior, tests, project status, and the active Goal.

The local candidate worktree is still at the frozen SHA but is not clean. It contains one untracked `node_modules` symlink and eight untracked audit/report artifacts. Per the contract, either condition requires immediate stop. No product journey, operational mutation test, RAG pressure run, PII gate, cloud action, or release action was continued after the identity blockers were confirmed.

GitHub CI is green on the current PR head, but CI is not Same-SHA runtime or product-experience proof.

## Identity evidence

```text
EXPECTED_CANDIDATE_SHA=89f9cc6486920e8d449d22671a0974cae037325f
LOCAL_WORKTREE=/Users/njx/Project/aog-r5-local-deploy
LOCAL_HEAD=89f9cc6486920e8d449d22671a0974cae037325f
LOCAL_HEAD_MATCH=YES
LOCAL_BRANCH=DETACHED
LOCAL_WORKTREE_CLEAN=NO
LOCAL_UNTRACKED_ENTRY_COUNT=9

PR_NUMBER=16
EXPECTED_PR_HEAD=89f9cc6486920e8d449d22671a0974cae037325f
OBSERVED_PR_HEAD=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
PR16_HEAD_MATCH=NO
HEAD_DRIFT_COMMITS=18
PR_STATE=OPEN_DRAFT
BASE=main@62d53b42e7994131a762f93db0e0410e4a917ce3
```

Current-head GitHub workflows observed:

| Workflow | Run | Result |
|---|---:|---|
| parent-pm-governance | 31153554806 | success |
| production-readiness | 31153554808 | success |
| aog-ci | 31153554823 | success |
| staging-validation | 31153554798 | success |

These checks prove only source/CI status on `a8ed848...`.

## Contract drift

PR #16 now states a different Owner product policy from the attached acceptance contract:

- authenticated users may browse sanitized knowledge across verification states;
- authenticated AI may retrieve and summarize sanitized knowledge across verification states;
- references must preserve `verification_status`;
- only VERIFIED knowledge may be represented as confirmed operational guidance, guaranteed inventory, approved action, or SLA;
- public/unauthenticated surfaces remain stricter;
- private reasoning remains non-public.

The old contract instead requires non-VERIFIED AI to use deterministic policy and withhold candidate content entirely. These are materially different product rules. Reusing the old expected outputs against the new head would generate a false failure or a false pass.

## Prior untracked audit artifact

An untracked local audit report and seven screenshots exist under `reports/audit-2026-08-07/`. They are not accepted as evidence for the current PR head because:

1. they are not committed durable truth;
2. they bind themselves to the old SHA;
3. they were produced before the current 18-commit head drift;
4. one screenshot is explicitly PII-related and must not be uploaded without a separate sanitization review.

The prior artifact reports a possible non-public PII exposure on the old candidate. That finding must be treated as a focused retest hypothesis on the new frozen head, not as a current-head conclusion.

## Required output block

```text
VERDICT=BLOCKED

CANDIDATE_SHA=89f9cc6486920e8d449d22671a0974cae037325f
PR16_HEAD_MATCH=NO
WORKTREE_CLEAN=NO

RELEASE_BUNDLE_COMPLETE=NOT_RUN_CONTRACT_STOP
RELEASE_MANIFEST_SHA_MATCH=NOT_RUN_CONTRACT_STOP
AOG_DB_SHA_MATCH=NOT_RUN_CONTRACT_STOP
FTS5_SHA_MATCH=NOT_RUN_CONTRACT_STOP
RELEASE_BUILD_COMMIT_MATCH=NOT_RUN_CONTRACT_STOP

BACKEND_LIVE=NOT_RUN_CONTRACT_STOP
FRONTEND_LIVE=NOT_RUN_CONTRACT_STOP

REVIEW_UNAUTH_401=NOT_RUN_CONTRACT_STOP
REVIEW_AUTH_200=NOT_RUN_CONTRACT_STOP
REVIEW_TOTAL=NOT_RUN_CONTRACT_STOP
REVIEW_VERIFIED=NOT_RUN_CONTRACT_STOP
REVIEW_UNVERIFIED=NOT_RUN_CONTRACT_STOP
REVIEW_STALE=NOT_RUN_CONTRACT_STOP
REVIEW_MISSING=NOT_RUN_CONTRACT_STOP

REVIEW_PENDING_DETAIL_VISIBLE=NOT_RUN_CONTRACT_STOP
REVIEW_METADATA_VISIBLE=NOT_RUN_CONTRACT_STOP
REVIEW_READ_ONLY=NOT_RUN_CONTRACT_STOP
REVIEW_NONPUBLIC_PII_REDACTED=NOT_RUN_CONTRACT_STOP
REVIEW_MUTATION_API_PRESENT=NOT_RUN_CONTRACT_STOP

NORMAL_PENDING_FAIL_CLOSED=NOT_RUN_CONTRACT_STOP

STRICT_AI_VERIFIED_ONLY=NOT_APPLICABLE_CONTRACT_SUPERSEDED
UNVERIFIED_AI_FAIL_CLOSED=NOT_RUN_NEW_POLICY_CONTRACT_REQUIRED
PRIVATE_REASONING_ABSENT=NOT_RUN_CONTRACT_STOP
VERIFICATION_UPGRADE_COUNT=NOT_RUN_CONTRACT_STOP

REFERENCE_TOTAL=NOT_RUN_CONTRACT_STOP
REFERENCE_UNEXPECTED_404=NOT_RUN_CONTRACT_STOP
RAW_ID_ROUTE_COUNT=NOT_RUN_CONTRACT_STOP

REVIEW_UI_FINDABILITY=NOT_RUN_CONTRACT_STOP
REVIEW_UI_STATUS_CLARITY=NOT_RUN_CONTRACT_STOP
REVIEW_UI_AUDITABILITY=NOT_RUN_CONTRACT_STOP
REVIEW_UI_NO_OPERATIONAL_CONFUSION=NOT_RUN_CONTRACT_STOP
REVIEW_UI_NO_DEBUG_LEAK=NOT_RUN_CONTRACT_STOP

RAG_8_QUERY_RESULT=NOT_RUN_CONTRACT_STOP
RAG_20_CASE_RESULT=NOT_RUN_CONTRACT_STOP
RAG_20_FAILURES=NOT_RUN_CONTRACT_STOP

PII_FORBIDDEN_HITS=NOT_RUN_CONTRACT_STOP
PII_VALUES_SKIPPED=NOT_RUN_CONTRACT_STOP

SOURCE_KB_WRITE_COUNT=0
CLOUD_WRITE_COUNT=0
CODE_CHANGE_COUNT=0
GIT_COMMIT_COUNT=0
GIT_PUSH_COUNT=0

FINAL_SHA_MATCH=YES
FINAL_WORKTREE_CLEAN=NO

CODEX_SAME_SHA_LOCAL_PRODUCT_ACCEPTANCE=BLOCKED
OWNER_LOCAL_CUSTOMER_VALUE_GATE=HOLD
TENCENT_CLOUD_GATE=HOLD

REMAINING_BLOCKERS=CANDIDATE_IDENTITY_OR_WORKTREE;BLOCKED_GITHUB_HEAD_DRIFT;ACCEPTANCE_CONTRACT_SUPERSEDED
```

`GIT_COMMIT_COUNT` and `GIT_PUSH_COUNT` above refer only to the candidate/product branch under acceptance. Publication of this report occurs on an isolated documentation-only review branch.

## Exit conditions for the next round

1. Freeze one current PR head SHA and do not advance it during acceptance.
2. Provide a dedicated clean local worktree at exactly that SHA.
3. Exclude the local `node_modules` symlink through `.git/info/exclude`; do not change product `.gitignore` solely for the audit.
4. Keep audit/report artifacts outside the candidate worktree until the final clean-state receipt is captured.
5. Issue a revised Codex contract aligned with the current Owner policy.
6. Provide the release directory, manifest hashes, live backend/frontend URLs, and MiniMax exact-SHA deployment receipt.
7. Retest the prior PII hypothesis on the new candidate using redacted evidence only.
8. Keep PR #16 Draft. Do not merge, cloud-deploy, release, mutate review status, or modify Owner source data before Codex and Owner gates close.
