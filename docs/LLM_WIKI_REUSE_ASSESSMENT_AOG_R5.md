# AOG R5 — `nashsu/llm_wiki` Reuse Assessment

## Upstream identity reviewed

```text
repository = nashsu/llm_wiki
upstream_commit = ad215b51252ffc1c6721d5b057f0449a2fb51530
license = GNU GPL v3.0
```

## Decision

`ARCHITECTURE_AND_PROTOCOL_REUSE_NOW`

`DIRECT_SOURCE_COPY = OWNER_LICENSE_DECISION_PENDING`

`OPTIONAL_LOCAL_SIDECAR_SPIKE = LATER`

`DROP_IN_RUNTIME_REPLACEMENT = NO`

## Why it fits AOG

The upstream project already implements several knowledge-management primitives AOG needs:

- persistent ingest queue with pending/processing/done/failed/cancelled states, pause, retry and restart persistence;
- asynchronous human review queue rather than blocking ingest;
- stable content-derived review identity and deduplication;
- project/source provenance and source-content browsing;
- a token-protected local HTTP API for files, content, reviews and review resolution;
- separation of source material from derived Wiki knowledge.

These concepts directly address AOG's current problem: many records are UNVERIFIED and the current product hides their contents, leaving no usable human review workflow.

## Why it is not a drop-in AOG engine

AOG currently runs FastAPI + Next.js + SQLite/FTS5 with CloudBase-oriented packaging. `llm_wiki` is a Tauri/Rust desktop application with its own local storage, UI and API server. Replacing AOG runtime with it would create a second application stack and complicate CloudBase deployment rather than reduce work.

The correct near-term reuse boundary is therefore workflow/contract reuse, not runtime replacement.

## Source reuse / license boundary

The upstream repository is GPLv3. AOG currently has no root license file. Copying or adapting upstream implementation code into the AOG repository would create a material licensing/distribution decision that should not be made implicitly by a coding agent.

R5 therefore performs a clean implementation in the existing AOG stack. Upstream source is used as an architectural reference only. If the Owner later wants a direct fork, embedded component, or copied implementation, licensing must be decided first.

## R5 concepts adopted

### 1. Review does not hide ingestion

Knowledge may exist before it is operationally trusted. A human reviewer must be able to inspect candidate content while status remains UNVERIFIED.

### 2. Review visibility != operational eligibility

A record may be `review_visible=true` while `operational_eligible=false` and `ai_eligible=false`.

### 3. Stable review identity

R5 derives a deterministic review key from record identity/status/source instead of creating ephemeral queue IDs.

### 4. Provenance-first review

Every review record exposes source document/location/version, updated/reviewed timestamps, reviewer, confidence and PII classification when available.

### 5. Local-first

The review flow must work on the Owner's local URL before public-cloud deployment is attempted.

## Future optional sidecar

A later isolated experiment may run `llm_wiki` as an unmodified local sidecar and consume its authenticated HTTP API for authoring/curation. That experiment must not become the production AOG dependency until data mapping, license, operational support and deployment architecture are accepted.

## Non-goals

- no GPL source copied into AOG in R5;
- no Tauri/Rust migration;
- no new vector database migration;
- no automatic approval;
- no weakening of VERIFIED-only operational AI.