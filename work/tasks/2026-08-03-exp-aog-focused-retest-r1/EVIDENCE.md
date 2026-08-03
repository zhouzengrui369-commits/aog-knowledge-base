# EVIDENCE — EXP-AOG-20260803 Focused Remediation

## Source evidence

- Review source: GitHub Issue #12.
- Baseline: `b390629d1684d62a8d0d8c7f4126b4b928633bd8`.
- Initial verdicts: `NOT_READY`, `BLOCKED_NON_REPRODUCIBLE_CANDIDATE`, `NOT_ELIGIBLE`.
- No test password, contact value or real runtime payload is recorded here.

## EXP-AOG-20260803-001 — Verification hard policy

### Replay

1. Ask about the same city while its city record is `UNVERIFIED`.
2. Repeat after switching the fixture to `VERIFIED`.
3. Inspect retrieval policy log and answer/reference payload.

### Acceptance criteria

- UNVERIFIED target: deterministic `UNVERIFIED / 不可用于操作` answer; no model invocation; no contacts, stock, logistics or plan text.
- VERIFIED target: only matching VERIFIED sources reach model context.
- The model receives code-assigned `verification_status` and cannot promote it.

### Remote evidence

- `aog_web/services/verification_policy.py`
- `aog_web/api/chat_safe.py`
- `tests/test_exp_aog_focused_retest.py`

### Runtime evidence required

- VERIFIED/UNVERIFIED contrast screenshots.
- Sanitized retrieval trace with source IDs/status only.
- Real MiniMax response capture showing no status elevation.

## EXP-AOG-20260803-002 — Reference round-trip

### Replay

1. Produce city, city_contacts, experience, wiki and unknown references.
2. Open every available reference.
3. Observe unsupported references.

### Acceptance criteria

- `city_contacts` routes to `/city/<encoded-code>?tab=contacts`.
- city-linked wiki routes to the city page.
- experience routes to its detail page.
- unknown/core-only references are non-clickable and include a reason.
- no `/<raw-doc-id>` fallback exists.

### Remote evidence

- explicit `ReferenceRoute` mapping;
- nullable `href`, `available`, `source_type`, `verification_status`, `reason` response contract;
- supported/unknown route negative tests.

### Runtime evidence required

- reference click matrix and 0 unexpected 404 recording.
- round-trip screenshot showing conversation retained.

## EXP-AOG-20260803-003 — Session lifecycle

### Replay matrix

- cold start;
- same-tab close/reopen;
- reference round trip;
- refresh;
- explicit clear;
- logout;
- expired authentication;
- login rotation/cross identity.

### Acceptance criteria

- completed messages restore only inside the same auth session namespace;
- active generation restores as interrupted/error, never as done;
- TTL expiry, logout, invalid auth and new login rotation clear chat storage;
- no credential or real contact is written to storage evidence.

### Remote evidence

- `lib/chat-state.ts` session namespace, TTL and terminal recovery;
- `components/auth-gate.tsx` auth session rotation/clear events;
- frontend focused tests.

### Runtime evidence required

- cold/warm/refresh/logout/expired/cross-identity video or screenshots plus storage-key inspection.

## EXP-AOG-20260803-004 — Streaming state machine

### Required traces

- normal;
- slow;
- timeout;
- provider error;
- user cancellation.

### Acceptance criteria

- phase sequence: `queued -> retrieving -> generating -> done`;
- refs event is intermediate and cannot finish loading;
- `error` and `cancelled` are terminal;
- a late done event cannot overwrite error/cancel;
- first-token and total latency are recorded without answer/contact contents.

### Remote evidence

- backend SSE status events;
- terminal-safe frontend SSE client;
- transition tests and backend error-terminal test.

### Runtime evidence required

- five sanitized event timelines and recordings.

## EXP-AOG-20260803-005 — Accessibility

### Acceptance criteria

- send button accessible name is `发送问题`;
- Enter submits through the form;
- Space activates the focused send button;
- focus returns after done/error/cancel;
- VoiceOver announces input, send, cancel, retry and phase changes.

### Remote evidence

- stable aria labels, keyboard help, focus rings and live status region;
- source contract test.

### Runtime evidence required

- accessibility tree screenshot;
- keyboard replay;
- VoiceOver recording.

## Release evidence boundary

Remote code and CI are necessary but not sufficient. A reproducible local candidate requires:

- frozen candidate commit;
- clean worktree;
- frontend build artifact SHA-256;
- focused browser/VoiceOver evidence;
- real MiniMax 20-case result at `0/20` failures.

Until those exist, Human Owner Gate remains `NOT_ELIGIBLE`.