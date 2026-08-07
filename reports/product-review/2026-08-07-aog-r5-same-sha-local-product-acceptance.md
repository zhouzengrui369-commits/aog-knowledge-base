# AOG Knowledge Base R5 · Codex Same-SHA Local Product Acceptance

- Date: 2026-08-07 (Asia/Taipei)
- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Pull request under acceptance: #16
- Frozen candidate: `a8ed848dbac3e07ddac3bf84187e3b7444a549c2`
- Candidate branch: `chatgpt/aog-knowledge-review-engine-r5`
- Base: `main@62d53b42e7994131a762f93db0e0410e4a917ce3`
- PR state required during acceptance: `OPEN_DRAFT`
- Contract status: **READY_PENDING_MINIMAX_EXACT_SHA_RECEIPT**

## 1. Acceptance identity

The previous candidate `89f9cc6486920e8d449d22671a0974cae037325f` and its browser conclusions are retired for Same-SHA acceptance purposes.

PR #16 is frozen at:

```text
FROZEN_CANDIDATE_SHA=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
```

No product/source commit may be added to PR #16 after this freeze until the MiniMax local receipt and Codex browser acceptance finish. Any head movement invalidates the receipt and requires a new freeze.

GitHub workflows observed on the frozen head:

| Workflow | Run | Result |
|---|---:|---|
| parent-pm-governance | 31153554806 | success |
| production-readiness | 31153554808 | success |
| aog-ci | 31153554823 | success |
| staging-validation | 31153554798 | success |

These are source/CI evidence only. They are not local runtime or product-experience proof.

## 2. Current Owner product policy

The acceptance model separates knowledge visibility, AI retrievability and operational authority.

```text
knowledge visibility != verification status
AI retrievability != operational authority
```

### 2.1 Authenticated knowledge browsing

If sanitized source/candidate content exists, an authenticated user may read and search it across verification states including `VERIFIED`, `UNVERIFIED`, `STALE` and other supported states.

Every surfaced item must preserve its `verification_status`; the UI must not visually or semantically upgrade non-VERIFIED knowledge to VERIFIED.

### 2.2 Authenticated AI retrieval

Authenticated AI may retrieve and summarize sanitized knowledge across verification states. Every reference must retain the source `verification_status`.

The model may explain what a non-VERIFIED source says, but must not convert that content into authoritative execution guidance.

### 2.3 Operational authority

Only `VERIFIED` knowledge may be represented as:

- confirmed operational guidance;
- guaranteed inventory or availability;
- approved dispatch/release/maintenance action;
- confirmed SLA or response-time commitment.

For non-VERIFIED knowledge the answer must preserve uncertainty and the need for human/Owner review.

### 2.4 PII policy

- non-public phone numbers and email addresses must be redacted;
- free-text PII in `content_md`, warehouse, logistics and other narrative fields must be sanitized before review or AI presentation;
- public contact data follows the existing permission model only;
- screenshots/evidence must not contain private contact values.

### 2.5 Public/unauthenticated surface

Public or unauthenticated surfaces remain stricter and must not expose pending candidate knowledge.

### 2.6 Private reasoning

Provider private reasoning remains non-public. No `<think>`, `<thinking>`, `<reasoning>`, chain-of-thought event, system prompt or private internal reasoning may reach the user-visible response/evidence.

### 2.7 Review authority

R5 does not authorize a client-side review-status mutation path. Same-SHA acceptance must not change Owner data or any review status.

## 3. MiniMax exact-SHA prerequisite

Codex must not begin browser acceptance until MiniMax provides an exact-SHA local receipt for the frozen candidate.

Required MiniMax receipt:

```text
CANDIDATE_SHA=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
PR16_HEAD=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
HEAD_MATCH=YES
WORKTREE=<dedicated path>
WORKTREE_CLEAN=YES
RELEASE_DIR=<exact-SHA release path>
RELEASE_MANIFEST_SHA256=<sha256>
AOG_DB_SHA256=<sha256>
FTS5_SHA256=<sha256>
RELEASE_BUILD_COMMIT=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
BACKEND_URL=<local url>
BACKEND_STATUS=ok
BACKEND_LLM_MODE=live
BACKEND_RAG_BACKEND=fts5
FRONTEND_URL=<local url>
FRONTEND_HTTP=200
RAG_8_QUERY_RESULT=8/8_PASS
RAG_20_CASE_RESULT=20/20_PASS
RAG_20_FAILURES=0
PII_FORBIDDEN_HITS=0
PII_VALUES_SKIPPED=0
SOURCE_KB_WRITE_COUNT=0
CLOUD_WRITE_COUNT=0
CODE_CHANGE_AFTER_FREEZE=0
```

The dedicated worktree must have `git status --porcelain --untracked-files=all` empty. A local `node_modules` symlink may be excluded only through that worktree's local `.git/info/exclude`; do not modify product `.gitignore` solely for the audit.

## 4. Codex Stage A — independent identity verification

Before any browser journey, Codex independently verifies:

```text
git rev-parse HEAD == a8ed848dbac3e07ddac3bf84187e3b7444a549c2
git status --porcelain --untracked-files=all == empty
PR16 head == a8ed848dbac3e07ddac3bf84187e3b7444a549c2
release manifest build commit == frozen candidate
release-manifest/aog.db/fts5 SHA256 == MiniMax receipt
backend health == status:ok, llm_mode:live, rag_backend:fts5
frontend root == HTTP 200
```

Any mismatch results in `BLOCKED_SAME_SHA_IDENTITY` and stops acceptance.

## 5. Codex Stage B — authenticated knowledge browsing

Use a real browser, not source inspection alone.

### Journey B1 — authentication boundary

- unauthenticated review API/page must not expose pending candidate knowledge;
- authenticated login reaches the review/knowledge surfaces;
- no password, Cookie, JWT or secret is recorded in evidence.

### Journey B2 — cross-status browsing

Find sanitized knowledge across the statuses present in the frozen release.

Acceptance criteria:

- logged-in user can open/read/search sanitized knowledge when content exists;
- each item visibly preserves `verification_status`;
- non-VERIFIED items are not visually labelled or described as VERIFIED;
- source/trust metadata needed to understand status is present;
- review visibility must not silently imply operational approval.

Record only counts, status labels, route hashes and redacted screenshots.

## 6. Codex Stage C — focused PII regression

The old candidate generated a PII-exposure hypothesis. Treat it as a hypothesis to retest on the frozen `a8ed848...` candidate, not as inherited truth.

Test at minimum:

1. review detail contact fields;
2. `content_md` free text;
3. warehouse free text;
4. logistics free text;
5. AI answer text;
6. AI reference cards/snippets;
7. normal knowledge browser surfaces that reuse review data.

Acceptance criteria:

- non-public phone values do not appear in user-visible output;
- non-public email values do not appear in user-visible output;
- free-text phone/email PII is sanitized;
- PII is not reintroduced by AI summarization or references;
- public values are shown only where existing permission policy permits them;
- evidence contains no private contact values.

If any private contact/free-text PII is visible to an unauthorized surface, verdict is `FAIL_PII_BOUNDARY`.

## 7. Codex Stage D — AI status-aware authority

Use real MiniMax through the exact-SHA backend.

Test at least one VERIFIED source when available and at least one non-VERIFIED source with sanitized content.

For every answer/reference record only redacted metadata such as status, reference count and route hash; do not save full sensitive answers.

Acceptance criteria:

### VERIFIED source

- retrieval/summarization allowed;
- references retain `verification_status=VERIFIED`;
- operational language is allowed only to the extent supported by the VERIFIED source.

### Non-VERIFIED source

- retrieval/summarization of sanitized knowledge is allowed;
- each reference retains the real non-VERIFIED status;
- answer must not state or imply that the source is VERIFIED;
- answer must not turn candidate knowledge into confirmed operational guidance;
- no guaranteed inventory/availability statement;
- no approval/release authorization;
- no confirmed SLA commitment;
- uncertainty/review status remains clear.

Any status upgrade by the model is a failure.

## 8. Codex Stage E — private reasoning regression

For both VERIFIED and non-VERIFIED AI paths verify:

```text
<think> count = 0
<thinking> count = 0
<reasoning> count = 0
event:think count = 0
system-prompt exposure = 0
private chain-of-thought exposure = 0
```

Private reasoning in logs must not be copied into evidence.

## 9. Codex Stage F — references

Every clickable AI reference must:

- preserve `verification_status`;
- point to a supported semantic route;
- return a non-404 browser/HTTP result;
- not degrade to a raw document ID route.

Unsupported reference kinds must fail closed as non-clickable with a reason.

Required summary:

```text
REFERENCE_TOTAL=
REFERENCE_AVAILABLE=
REFERENCE_UNAVAILABLE=
REFERENCE_UNEXPECTED_404=0
RAW_ID_ROUTE_COUNT=0
REFERENCE_STATUS_MISSING_COUNT=0
```

## 10. Codex Stage G — required regression gates

Run on the frozen candidate without modifying cases, scoring, allowlists or thresholds:

- existing RAG 8-query regression: require `8/8 PASS`;
- real MiniMax 20-case pressure suite: require `20/20 PASS`, failures `0`;
- existing PII Gate: require `forbidden_hits=0`, `values_skipped=0` unless the repository contract explicitly defines a different current success field;
- existing focused tests relevant to review/AI/PII boundaries.

Do not use mock for the real MiniMax pressure run.

## 11. Source/data immutability

Record a source-tree identity before and after acceptance without publishing source content.

Required:

```text
SOURCE_TREE_HASH_BEFORE == SOURCE_TREE_HASH_AFTER
SOURCE_KB_WRITE_COUNT=0
REVIEW_STATUS_MUTATION_COUNT=0
CLOUD_WRITE_COUNT=0
```

## 12. Product-experience journey

Codex must use the real browser and answer the following from observed runtime behavior:

1. Can an authenticated user find pending/non-VERIFIED knowledge without being told it is missing?
2. Is the status obvious enough that visibility is not confused with approval?
3. Can the user navigate from browse/search to detail and back without losing context?
4. Can the user ask AI about that sanitized knowledge and see status-preserving references?
5. Does the AI remain useful while avoiding confirmed operational claims for non-VERIFIED material?
6. Are PII and private reasoning absent from all visible surfaces?
7. Does the review/knowledge surface provide enough provenance/trust metadata for a human to judge the material?
8. Are known R5 limitations such as the missing durable approve/reject workflow still explicit rather than disguised as complete?

## 13. Evidence discipline

Evidence may contain:

- candidate SHA;
- hashes;
- counts;
- status labels;
- HTTP status;
- route hashes;
- timing;
- redacted screenshots.

Evidence must not contain:

- passwords;
- JWT/Cookies/tokens;
- MiniMax/COS secrets;
- private phone/email/contact values;
- full sensitive knowledge content;
- private reasoning;
- unsanitized old screenshots.

## 14. Verdict rules

Allowed verdicts:

- `PASS`
- `PARTIAL PASS`
- `FAIL`
- `BLOCKED`

`PASS` requires all Same-SHA identity, browsing, status-awareness, PII, private-reasoning, references, RAG and source-immutability gates to pass.

`PARTIAL PASS` may be used only for non-safety product-experience gaps that do not violate the current Owner policy. PII exposure, status upgrade, unauthorized operational authority, private reasoning leakage or SHA mismatch are not PARTIAL PASS conditions; they are FAIL/BLOCKED.

This Codex result is not a merge, Tencent Cloud, release or Owner-final authorization.

## 15. Required output

```text
VERDICT=
CANDIDATE_SHA=a8ed848dbac3e07ddac3bf84187e3b7444a549c2
PR16_HEAD_MATCH=
WORKTREE_CLEAN=
RELEASE_MANIFEST_SHA_MATCH=
AOG_DB_SHA_MATCH=
FTS5_SHA_MATCH=
RELEASE_BUILD_COMMIT_MATCH=
BACKEND_LIVE=
FRONTEND_LIVE=
AUTHENTICATED_CROSS_STATUS_BROWSING=
STATUS_LABEL_PRESERVATION=
NONVERIFIED_OPERATIONAL_AUTHORITY_BLOCKED=
REVIEW_NONPUBLIC_PII_REDACTED=
FREE_TEXT_PII_REDACTED=
AI_PII_REINTRODUCTION_COUNT=
PRIVATE_REASONING_ABSENT=
REFERENCE_TOTAL=
REFERENCE_UNEXPECTED_404=
RAW_ID_ROUTE_COUNT=
REFERENCE_STATUS_MISSING_COUNT=
RAG_8_QUERY_RESULT=
RAG_20_CASE_RESULT=
RAG_20_FAILURES=
PII_FORBIDDEN_HITS=
PII_VALUES_SKIPPED=
SOURCE_KB_WRITE_COUNT=0
REVIEW_STATUS_MUTATION_COUNT=0
CLOUD_WRITE_COUNT=0
CODE_CHANGE_COUNT=0
GIT_COMMIT_COUNT=0
GIT_PUSH_COUNT=0
FINAL_SHA_MATCH=
FINAL_WORKTREE_CLEAN=
CODEX_SAME_SHA_LOCAL_PRODUCT_ACCEPTANCE=
OWNER_LOCAL_CUSTOMER_VALUE_GATE=HOLD
TENCENT_CLOUD_GATE=HOLD
REMAINING_BLOCKERS=
```

Do not merge PR #16, do not deploy Tencent Cloud, do not release, and do not modify Owner data or review status as part of this acceptance.
