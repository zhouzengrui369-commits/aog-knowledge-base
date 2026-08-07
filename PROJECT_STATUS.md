# AOG Knowledge Base — Current Project Status

## Development ownership

- Governance Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- ChatGPT: Remote Parent PM + Coding Agent
- MiniMax Code: exact-SHA local deployment runner
- Codex: real-operation test + product-experience auditor
- Owner: product/data/cloud/release/final acceptance decisions

## Active Goal

- Goal: `GOAL-AOG-KNOWLEDGE-R5`
- Contract: `work/tasks/2026-08-07-aog-knowledge-review-engine-r5/GOAL.md`
- Development branch: `chatgpt/aog-knowledge-review-engine-r5`
- Draft PR: `#16`
- Parent issue: `#12`
- Status: `OWNER_POLICY_UPDATE_IN_IMPLEMENTATION · LOCAL_AGENT_AUTHORIZATION_REVOKED_UNTIL_NEW_SOURCE_FREEZE`

## Owner product decision — 2026-08-07

The prior rule `UNVERIFIED = hidden from normal browsing and AI` is superseded.

Current policy:

```text
KNOWLEDGE EXISTS
  ↓
authenticated browsing = visible after PII sanitization
  ↓
authenticated AI retrieval = allowed with verification_status preserved
  ↓
operational authority = VERIFIED only
```

Therefore:

- UNVERIFIED/STALE knowledge is not treated as nonexistent;
- an authenticated user may read candidate knowledge from normal knowledge browsing and the review plane;
- authenticated AI may answer what candidate knowledge records, clearly labelled as pending/unverified;
- only VERIFIED knowledge may be represented as confirmed execution guidance, guaranteed inventory, approved contact/action or SLA;
- private/controlled contact data and free-text phone/email values remain redacted;
- public/unauthenticated surfaces remain stricter and do not expose pending candidate knowledge;
- provider-private reasoning stays non-public.

## PII finding clarification

The Codex P0 finding meant that a private/controlled 11-digit mobile number was embedded inside warehouse free text and bypassed the structured contact permission model. The fix redacts that contact-shaped value while preserving the warehouse, logistics, parts, fleet and plan knowledge around it. PII safety must never be implemented by hiding the entire knowledge record.

## R5 product scope

R5 now includes:

- `nashsu/llm_wiki` architecture/protocol reuse assessment;
- authenticated read-only review plane;
- pending-review queue and candidate-content browsing;
- ordinary city browsing that loads the sanitized candidate copy for logged-in users;
- status-aware AI retrieval across verification states;
- strict distinction between AI retrievability and VERIFIED operational authority;
- free-text PII sanitization;
- local-first product acceptance before Tencent Cloud public deployment.

R5 still does **not** include Approve/Reject/comment/durable review decision ledger; that explicit follow-up remains Issue #17.

## Deployment order

All previously frozen R5 local candidates are superseded by this Owner policy update. Do not deploy an older SHA.

```text
ChatGPT policy/source update + CI
→ freeze one new exact R5 SHA
→ MiniMax focused local redeploy
→ Codex focused test: normal browsing + UNVERIFIED AI retrieval + PII boundary
→ Owner local customer-value acceptance
→ separate Tencent Cloud deployment Goal
```

## Claim ceiling

Not yet established for the new policy candidate:

- new GitHub Source Gate PASS;
- local normal-browsing knowledge visibility PASS;
- authenticated UNVERIFIED AI retrieval PASS;
- same-SHA MiniMax/Codex focused acceptance;
- Tencent Cloud deployment;
- release readiness;
- Human Owner final gate.
