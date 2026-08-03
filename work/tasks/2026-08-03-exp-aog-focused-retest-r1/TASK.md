# TASK — EXP-AOG-20260803 Focused Remediation

## TASK-001 — Verification policy enforcement

**Issue:** `EXP-AOG-20260803-001`  
**Problem:** city detail fails closed while RAG/LLM can still expose and elevate UNVERIFIED city material.  
**Root cause:** retrieval results do not carry an enforced city review decision into context construction, answer policy and references.  
**Acceptance criteria:**

- an UNVERIFIED target city produces a deterministic `UNVERIFIED / 不可用于操作` response without protected contacts, stock, logistics or plan text;
- VERIFIED city sources remain usable;
- model context contains code-assigned verification status and the model cannot upgrade it;
- policy logs contain source IDs/status only, never real contact values.

**Tests:** backend policy unit tests plus focused runtime contrast.  
**Evidence:** sanitized policy trace, answer/reference screenshots, candidate identity.  
**Rollback risk:** over-filtering VERIFIED knowledge.

## TASK-002 — Reference route contract

**Issue:** `EXP-AOG-20260803-002`  
**Problem:** `city_contacts:*` and unknown kinds degrade to `/<raw-doc-id>` and 404.  
**Root cause:** implicit fallback routing.  
**Acceptance criteria:**

- explicit mapping for city, city_contacts, experience and city-linked wiki;
- unsupported kinds produce a non-clickable source with a reason;
- no raw document ID is emitted as a route;
- reference verification status matches answer policy.

**Tests:** supported route mapping and unknown-kind negative tests.  
**Evidence:** route matrix and focused click replay.  
**Rollback risk:** old index metadata may be incomplete.

## TASK-003 — Session lifecycle

**Issue:** `EXP-AOG-20260803-003`  
**Problem:** component-local messages disappear after reference navigation or refresh.  
**Root cause:** no session-scoped persistence or auth lifecycle binding.  
**Acceptance criteria:**

- same-tab close/reopen, reference round trip and refresh restore a completed conversation;
- in-flight messages restore as interrupted, never as done;
- explicit clear, logout, expired auth and identity rotation clear stored conversation;
- storage is session-scoped and TTL-limited.

**Tests:** storage restore, TTL, terminal recovery and auth-clear tests.  
**Evidence:** cold/warm/refresh/logout/cross-session focused replay.  
**Rollback risk:** stale or cross-identity disclosure.

## TASK-004 — Streaming state machine

**Issue:** `EXP-AOG-20260803-004`  
**Problem:** references end loading before the answer is generated.  
**Root cause:** refs callback sets `loading=false`; error can be followed by done.  
**Acceptance criteria:**

- states are `queued/retrieving/generating/done/error/cancelled`;
- refs never create a terminal state;
- slow response shows progress and cancel control;
- error/cancel are terminal and cannot transition to done;
- first-token and done latency are exposed in sanitized status events.

**Tests:** transition matrix, refs intermediate event, error-after-done rejection, timeout and cancel tests.  
**Evidence:** normal/slow/timeout/error event traces and recordings.  
**Rollback risk:** stuck loading or duplicate terminal events.

## TASK-005 — Accessible send control

**Issue:** `EXP-AOG-20260803-005`  
**Problem:** icon-only send button has no accessible name evidence.  
**Acceptance criteria:**

- stable `aria-label="发送问题"` and disabled-state description;
- Enter and Space submission paths remain available;
- focus remains usable after submit, cancel and retry;
- VoiceOver focused retest is specified.

**Tests:** source/DOM contract and keyboard runtime replay.  
**Evidence:** accessibility tree and VoiceOver recording.  
**Rollback risk:** icon refactor removes the label.