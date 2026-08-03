# PLAN — Focused Remediation R1

## Phase 0 — Freeze source truth

1. Read Issue #12 in full.
2. Bind work to `main@b390629d1684d62a8d0d8c7f4126b4b928633bd8`.
3. Do not consume or publish real contacts, passwords or runtime payloads.

## Phase 1 — Backend safety boundary

1. Add a verification policy service that resolves city status from SQLite and annotates every RAG hit.
2. Block generation for an explicitly targeted non-VERIFIED city.
3. Filter non-eligible city-linked hits before context construction.
4. Replace implicit reference fallback with an explicit route table.
5. Emit SSE status events and make error terminal.

## Phase 2 — Frontend continuity and state

1. Add a typed streaming client with AbortSignal support.
2. Add a strict phase transition reducer.
3. Persist only sanitized chat state in sessionStorage, namespaced by auth session ID and bounded by TTL.
4. Rotate/clear the client auth session on login, logout and failed verification.
5. Keep refs intermediate, render unsupported refs as non-clickable, and expose slow/cancel/retry controls.
6. Add accessible send/clear/cancel controls.

## Phase 3 — Tests

1. Backend verification and route-contract tests.
2. Backend stream event ordering/error-terminal tests.
3. Frontend state/session/reference/accessibility tests.
4. Run existing backend and frontend regression suites through GitHub Actions.

## Phase 4 — Candidate and focused retest handoff

1. Freeze the final branch SHA.
2. Require a clean local worktree and a reproducible build artifact SHA-256.
3. Run only the focused retest matrix from Issue #12.
4. Run the real MiniMax 20-case suite at `0/20` failures.
5. Keep Human Owner Gate `NOT_ELIGIBLE` until runtime P0 evidence passes.