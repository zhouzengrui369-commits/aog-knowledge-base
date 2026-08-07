# GOAL-AOG-KNOWLEDGE-R5 — Knowledge Review Engine and Local-First Acceptance

## Identity

- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Successor base: R4 strict-safety candidate `8f99777322e2a13bf5d42de31954e195d40ca967`
- Development branch: `chatgpt/aog-knowledge-review-engine-r5`
- Parent product review: Issue #12
- Public governance Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- External architecture reference: `nashsu/llm_wiki@ad215b51252ffc1c6721d5b057f0449a2fb51530`

## User outcome

An authenticated AOG user can browse the knowledge base and ask AI questions against the knowledge that actually exists, including pending-review records. Verification status remains visible and authoritative: candidate knowledge may be read and quoted, but only VERIFIED knowledge may be presented as confirmed operational authority.

## Product policy — Owner decision 2026-08-07

AOG separates three independent concepts:

1. **Knowledge visibility** — whether an authenticated user may inspect sanitized source/candidate knowledge.
2. **AI retrievability** — whether authenticated AI may retrieve and summarize that knowledge while preserving its verification status.
3. **Operational authority** — whether the knowledge may be treated as confirmed execution guidance.

Rules:

- knowledge with actual source content remains browsable to authenticated users regardless of VERIFIED/UNVERIFIED/STALE status;
- authenticated AI may retrieve sanitized knowledge across verification states and answer what the knowledge base records;
- every AI reference preserves its `verification_status`; non-VERIFIED content must be phrased as pending/candidate knowledge, never silently promoted;
- only VERIFIED knowledge may be represented as confirmed operational authority, guaranteed inventory, SLA or approved execution instruction;
- private/controlled contact data remains redacted; knowledge visibility does not grant PII visibility;
- public/unauthenticated operational APIs may remain fail-closed for non-VERIFIED candidate content;
- review mode is read-only in R5; status mutation remains Owner-controlled and auditable;
- provider-private reasoning remains non-public.

## llm_wiki reuse boundary

R5 reuses upstream architecture/protocol ideas (ingest queue, asynchronous review, stable review identity, provenance-first browsing, local API) but does **not** copy GPLv3 implementation source into AOG. Direct source reuse/forking requires a separate licensing decision.

## Included

- authenticated read-only review API;
- pending knowledge queue and review detail;
- ordinary authenticated city browsing that automatically loads sanitized candidate knowledge when operational data is not VERIFIED;
- provenance/status/confidence visibility;
- status-aware authenticated AI retrieval across verification states;
- VERIFIED-only operational-authority semantics;
- PII sanitization for free-text candidate knowledge;
- backend/frontend regression tests;
- AOG-specific llm_wiki reuse assessment;
- local-first MiniMax/Codex acceptance contracts;
- Tencent Cloud public deployment HOLD until local acceptance.

## Excluded / Owner locked

- review-status mutation or bulk approval;
- editing Owner source files;
- real-data import;
- CloudBase/COS writes;
- Tencent credentials, billing, environment creation;
- release or automatic merge.

## Acceptance

- unauthenticated review API rejected;
- authenticated pending knowledge is browsable and candidate content is visible from both review and normal knowledge-browsing paths;
- private/controlled contact data and free-text phone/email values remain redacted;
- authenticated AI can retrieve UNVERIFIED knowledge and clearly carries `verification_status=UNVERIFIED` into context/references;
- non-VERIFIED AI answers describe candidate knowledge without upgrading it to confirmed operational authority;
- unauthenticated UNVERIFIED chat remains fail-closed;
- provider-private reasoning never leaves the backend;
- navigation and review queue/detail work locally;
- CI green on exact candidate;
- MiniMax exact-SHA local deployment PASS;
- Codex same-SHA product focused retest PASS;
- Owner local customer-value gate PASS before public cloud deployment.

## Terminal status

GitHub source/CI success is `PARTIAL PASS`; full `PASS` requires local runtime, Codex and Owner gates.
