# Codex Contract — GOAL-AOG-KNOWLEDGE-R5 Local Acceptance

## Role

Independent real-operation/product-experience tester. Do not edit source or Git history.

## Start Gate

Begin only after Parent PM gives an exact R5 candidate and MiniMax returns a coherent local technical receipt for the same SHA.

```text
CANDIDATE_SHA=<PARENT_PM_EXACT_SHA>
MINIMAX_CANDIDATE_SHA=<same>
FRONTEND=http://127.0.0.1:3000
BACKEND=http://127.0.0.1:8088
```

## Required journeys

### Knowledge review usability

- login and open `知识审核` from main navigation;
- confirm pending queue loads without manual URL editing;
- inspect counts/status filters;
- open at least one real UNVERIFIED record with candidate content;
- verify source/version/confidence/review metadata are understandable;
- verify candidate body/fleet/parts/logistics/warehouse are visible when they exist;
- verify non-public contacts remain redacted;
- verify candidate contacts are not clickable operational actions;
- verify UI clearly says review-visible does not mean operational/AI eligible;
- verify MISSING records distinguish "source missing" from "content hidden".

### Operational boundary comparison

For the same pending city:

- review page shows sanitized candidate content;
- normal city page still hides operational content;
- normal page has a clear `进入知识审核（只读）` route;
- AI question about that non-VERIFIED city stays fail-closed and does not use the review candidate.

### VERIFIED control

Use an existing real VERIFIED city without changing data status. Confirm the operational journey remains usable and references are VERIFIED.

### Issue #12 focused retest

Re-run reference reachability, session continuity, stream terminal behavior, keyboard and VoiceOver requirements against the exact same candidate.

## Evidence

Return sanitized screenshots/recordings, final URLs, candidate SHA, session/reference/stream matrices and findings P0-P3. Do not expose secrets or private contact values.

## Verdict

```text
PRODUCT_EXPERIENCE=PASS|NOT_READY
CANDIDATE_SHA=
MINIMAX_RECEIPT_MATCH=
REVIEW_QUEUE=
PENDING_CONTENT_VISIBLE=
REVIEW_METADATA=
NON_PUBLIC_CONTACT_REDACTION=
READ_ONLY_BOUNDARY=
NORMAL_PENDING_FAIL_CLOSED=
STRICT_AI_VERIFIED_ONLY=
VERIFIED_CONTROL=
REFERENCE_REPLAY=
SESSION_MATRIX=
STREAM_MATRIX=
KEYBOARD=
VOICEOVER=
P0_COUNT=
P1_COUNT=
P2_COUNT=
REMAINING_BLOCKERS=
```

Codex PASS makes the local Owner gate eligible; it does not authorize Tencent Cloud deployment or release.