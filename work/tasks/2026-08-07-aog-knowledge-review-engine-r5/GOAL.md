# GOAL-AOG-KNOWLEDGE-R5 — Knowledge Review Engine and Local-First Acceptance

## Identity

- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Successor base: R4 strict-safety candidate `8f99777322e2a13bf5d42de31954e195d40ca967`
- Successor branch: `chatgpt/aog-knowledge-review-engine-r5`
- Parent product review: Issue #12
- Public governance Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- External architecture reference: `nashsu/llm_wiki@ad215b51252ffc1c6721d5b057f0449a2fb51530`

## User outcome

An authenticated AOG knowledge owner can open the local product, browse pending-review knowledge, inspect provenance and candidate content, and understand exactly what still needs review. Pending content remains read-only and cannot be used as VERIFIED operational guidance or AI grounding until an explicit audited verification action occurs.

## Product policy

AOG now separates two independent concepts:

1. **Review visibility** — whether an authenticated reviewer may inspect candidate knowledge.
2. **Operational eligibility** — whether knowledge may be used for AOG execution or AI generation.

Rules:

- `UNVERIFIED`, `STALE`, `MISSING`, `FIXTURE`, `REDACTED` are never silently promoted to VERIFIED.
- Pending-review content may be displayed in the authenticated review surface when source content exists.
- The normal operational city API/UI stays fail-closed for non-VERIFIED content.
- AI generation remains VERIFIED-only through the R4 strict router.
- Review-mode content is read-only in R5; changing `review_status` remains an Owner-controlled future workflow.
- Non-public contact values stay redacted. Review UI must not turn candidate contacts into clickable operational actions.

## llm_wiki reuse decision

R5 may reuse `nashsu/llm_wiki` architecture and protocol ideas, especially:

- immutable/raw source separation;
- incremental ingest queue semantics;
- asynchronous human review queue;
- stable review identity/dedup ideas;
- provenance-first knowledge browsing;
- local authenticated API/sidecar concepts.

R5 must not copy GPLv3 source into AOG without an explicit licensing decision. The near-term implementation is a clean AOG-stack implementation based on independently expressed requirements and observed architecture.

## Included scope

- authenticated, read-only review API for city knowledge;
- review queue/list for non-VERIFIED records;
- review detail surface showing sanitized candidate content plus provenance/status;
- clear visual distinction between "可审核阅读" and "可用于实际处置";
- CTA from normal non-VERIFIED city page into review view;
- tests proving review visibility does not weaken operational/AI gates;
- AOG-specific `llm_wiki` reuse assessment;
- local-first MiniMax deployment contract and Codex acceptance contract;
- Tencent Cloud deployment kept on HOLD until local product acceptance closes.

## Excluded / Owner locked

- direct status mutation or bulk auto-approval;
- editing Owner source files;
- importing new real data;
- CloudBase/COS writes;
- Tencent Cloud credentials, billing, environment creation;
- release;
- automatic merge.

## Acceptance criteria

- [ ] unauthenticated review API is rejected;
- [ ] authenticated reviewer can list pending records and open a pending city with candidate content;
- [ ] review detail shows source, status, timestamps/confidence when present;
- [ ] non-public contacts remain redacted;
- [ ] review content is visibly read-only and marked non-operational;
- [ ] normal non-VERIFIED city API still hides operational content;
- [ ] strict AI still never receives non-VERIFIED content;
- [ ] VERIFIED operational city behavior remains unchanged;
- [ ] frontend includes a usable review queue and detail flow;
- [ ] all GitHub CI gates pass;
- [ ] MiniMax exact-SHA local deploy PASS;
- [ ] Codex local knowledge-browse + Issue #12 focused retest PASS;
- [ ] Owner accepts local customer value before any public-cloud deployment.

## Terminal status

`PASS` requires source, local runtime, Codex product experience and Owner gates. GitHub CI alone is `PARTIAL PASS`.