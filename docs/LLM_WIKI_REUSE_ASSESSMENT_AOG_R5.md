# AOG R5 — `nashsu/llm_wiki` Reuse Assessment

## Upstream identity reviewed

```text
repository = nashsu/llm_wiki
upstream_commit = ad215b51252ffc1c6721d5b057f0449a2fb51530
license = GNU GPL v3.0
```

## Decision

```text
ARCHITECTURE_AND_PROTOCOL_REUSE_NOW
DIRECT_SOURCE_COPY = OWNER_LICENSE_DECISION_PENDING
OPTIONAL_LOCAL_SIDECAR_SPIKE = LATER
DROP_IN_RUNTIME_REPLACEMENT = NO
```

## Reusable concepts

The upstream project already implements knowledge-management primitives AOG needs:

- persistent ingest queue with pending/processing/done/failed/cancelled states, pause, retry and restart persistence;
- asynchronous human review queue rather than blocking ingest;
- stable content-derived review identity and deduplication;
- project/source provenance and source-content browsing;
- token-protected local HTTP API for files, content and reviews;
- source material separated from derived Wiki knowledge.

These concepts address AOG's current problem: many records are not VERIFIED and the existing operational surface hides their candidate content, leaving no practical human review workflow.

## Not a drop-in production engine

AOG runs FastAPI + Next.js + SQLite/FTS5 with CloudBase-oriented packaging. `llm_wiki` is a Tauri/Rust desktop application with its own local storage, UI and HTTP API. Replacing AOG runtime with it would create a second application stack and complicate deployment.

R5 therefore reuses workflow/contract ideas in the existing AOG stack instead of replacing the runtime.

## License boundary

The upstream repository is GPLv3. AOG currently has no root license file. Copying or adapting implementation source into AOG would create a material licensing/distribution decision that must not be made implicitly by a coding agent.

R5 is a clean implementation from independently stated requirements. No upstream GPL implementation file is copied, translated line-for-line or embedded.

## R5 concepts adopted

1. **Review does not block knowledge existence.** Candidate knowledge can be ingested and visible before operational verification.
2. **Review visibility != operational eligibility.** `review_visible=true` may coexist with `operational_eligible=false` and `ai_eligible=false`.
3. **Stable review identity.** A deterministic review key is derived from record identity/status/source.
4. **Provenance-first review.** Source/version/time/reviewer/confidence/PII metadata are shown alongside candidate content.
5. **Local-first acceptance.** The Owner's local URL must support the review workflow before public-cloud deployment.

## Future optional sidecar

A later isolated experiment may run unmodified `llm_wiki` as a local authoring/curation sidecar and consume its authenticated HTTP API. That experiment requires explicit data mapping, license and operational-support acceptance before becoming an AOG dependency.

## R5 non-goals

- no GPL source copy;
- no Tauri/Rust migration;
- no vector-store migration;
- no automatic approval;
- no weakening of VERIFIED-only operational AI.