# GOAL-AOG-KNOWLEDGE-R5 — Knowledge Review Engine and Local-First Acceptance

## Identity

- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Successor base: R4 strict-safety candidate `8f99777322e2a13bf5d42de31954e195d40ca967`
- Development branch: `chatgpt/aog-knowledge-review-engine-r5`
- Parent product review: Issue #12
- Public governance Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- External architecture reference: `nashsu/llm_wiki@ad215b51252ffc1c6721d5b057f0449a2fb51530`

## User outcome

An authenticated AOG knowledge owner can open the local product, browse pending-review knowledge, inspect provenance and candidate content, and understand exactly what still needs review. Pending content remains read-only and cannot be used as VERIFIED operational guidance or AI grounding until an explicit audited verification action occurs.

## Product policy

AOG separates two independent concepts:

1. **Review visibility** — whether an authenticated reviewer may inspect candidate knowledge.
2. **Operational eligibility** — whether knowledge may be used for AOG execution or AI generation.

Rules:

- pending content may be visible in the authenticated review surface when source content exists;
- normal operational city API/UI stays fail-closed for non-VERIFIED content;
- AI generation stays VERIFIED-only through the R4 strict router;
- review mode is read-only in R5; status mutation remains Owner-controlled;
- non-public contacts remain redacted and candidate contacts are not actionable links.

## llm_wiki reuse boundary

R5 reuses upstream architecture/protocol ideas (ingest queue, asynchronous review, stable review identity, provenance-first browsing, local API) but does **not** copy GPLv3 implementation source into AOG. Direct source reuse/forking requires a separate licensing decision.

## Included

- authenticated read-only review API;
- pending knowledge queue and review detail;
- provenance/status/confidence visibility;
- candidate knowledge content visible for review;
- CTA from non-VERIFIED city page to review surface;
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
- authenticated pending knowledge is browsable and candidate content is visible;
- non-public contacts remain redacted;
- review content is marked read-only/non-operational;
- normal non-VERIFIED operational endpoint still hides candidate content;
- strict AI remains VERIFIED-only;
- navigation and review queue/detail work locally;
- CI green on exact candidate;
- MiniMax exact-SHA local deployment PASS;
- Codex same-SHA product focused retest PASS;
- Owner local customer-value gate PASS before public cloud deployment.

## Terminal status

GitHub source/CI success is `PARTIAL PASS`; full `PASS` requires local runtime, Codex and Owner gates.