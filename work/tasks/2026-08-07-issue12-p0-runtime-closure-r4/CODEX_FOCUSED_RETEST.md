# Codex Contract — GOAL-AOG-ISSUE12-R4 Focused Retest

## Role

You are the independent real-operation tester and product-experience auditor. You do not repair source code under test.

## Start Gate

Do not begin until MiniMax returns a coherent technical deployment receipt and Parent PM supplies the same exact candidate SHA.

Required identity:

```text
REPOSITORY=zhouzengrui369-commits/aog-knowledge-base
CANDIDATE_SHA=<PARENT_PM_EXACT_SHA>
MINIMAX_RECEIPT_SHA=<same candidate>
FRONTEND=http://127.0.0.1:3000
BACKEND=http://127.0.0.1:8088
```

If deployed SHA differs, return `BLOCKED_CANDIDATE_IDENTITY_MISMATCH`.

## Forbidden

- source/test edits;
- Git commit/push/merge;
- changing verification status or real Owner data;
- exposing passwords, private contacts or provider secrets in screenshots/reports;
- CloudBase writes or release actions.

## Focused journeys

### A. P0 verification boundary

1. Cold/warm login as permitted by the local test environment.
2. Ask an operational question targeting an UNVERIFIED city.
3. Verify the answer explicitly shows `UNVERIFIED / 不可用于操作` or equivalent approved boundary.
4. Verify no protected personnel/contact/inventory/logistics/timing/plan-body content is disclosed.
5. Verify no model-generated operational workaround appears.
6. Verify the reference points only to the city/status surface or another approved non-operational source.

### B. VERIFIED control

1. Ask the same structural question against an approved VERIFIED control city available in the current release data.
2. Verify every operational fact is grounded in a VERIFIED reference.
3. Open every clickable reference and confirm semantic match and non-404 result.
4. Unsupported references must be visibly non-clickable.

Do not create or upgrade VERIFIED data to make this test pass. If the Owner dataset has no eligible VERIFIED control, return `BLOCKED_DATA_READINESS`.

### C. Private reasoning boundary

During normal and slow streams inspect UI, DOM and network/SSE transcript:

- no `event: think`;
- no `<think>`, `<thinking>`, `<reasoning>` tags;
- no provider-private reasoning prose;
- the visible progress UI may show high-level phases/elapsed progress only.

### D. Session continuity matrix

Test:

- cold session;
- warm session;
- close/reopen AI panel;
- reference round-trip;
- refresh after completed answer;
- refresh during in-flight generation;
- explicit clear conversation;
- logout;
- expired session;
- session rotation/new login.

Verify no cross-identity session leakage.

### E. Stream terminal matrix

Exercise normal, intentionally slow, timeout/error and cancel paths. Confirm:

- refs are intermediate and do not end loading;
- generating remains visible before first public token;
- slow state offers cancel/retry guidance;
- cancelled/error cannot be overwritten by late done;
- focus returns to the question input after terminal actions.

### F. Accessibility

Using keyboard and VoiceOver:

- input has a usable accessible name;
- `发送问题` is announced;
- disabled-state help is understandable;
- Enter submits when allowed;
- focused send button + Space submits when allowed;
- Cancel, Clear, Close and references have understandable names;
- live-region updates are not excessively noisy and do not expose private reasoning.

## Evidence

Return sanitized evidence bound to the exact candidate:

- candidate SHA;
- MiniMax receipt identity;
- environment/browser/OS;
- screenshot or recording paths and hashes where practical;
- final URLs/status for reference replay;
- session matrix table;
- stream event transcript with private values removed;
- accessibility tree / VoiceOver observation;
- findings P0–P3 with exact repro steps.

## Verdict

```text
PRODUCT_EXPERIENCE=PASS|NOT_READY
P0_COUNT=
P1_COUNT=
P2_COUNT=
CANDIDATE_SHA=
UNVERIFIED_BOUNDARY=
VERIFIED_CONTROL=
PRIVATE_REASONING_ABSENT=
REFERENCE_REPLAY=
SESSION_MATRIX=
STREAM_MATRIX=
KEYBOARD=
VOICEOVER=
FOCUSED_RETEST_VERDICT=
REMAINING_BLOCKERS=
```

Only `P0_COUNT=0` and all required focused journeys complete can make the Human Owner Gate eligible. Codex PASS does not authorize merge/release by itself.
