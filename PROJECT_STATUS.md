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
- Successor base: `8f99777322e2a13bf5d42de31954e195d40ca967`
- Development branch: `chatgpt/aog-knowledge-review-engine-r5`
- Parent issue: `#12`
- Status: `REMOTE_DEVELOPMENT_ACTIVE · LOCAL_AGENTS_HOLD_UNTIL_R5_SOURCE_GATE`

## Owner requirement update

R4 local deployment authorization was revoked before MiniMax execution. R5 adds:

- AOG-specific `nashsu/llm_wiki` reuse assessment;
- authenticated read-only knowledge review plane;
- pending-review queue and candidate-content browsing;
- separation of review visibility from operational/AI eligibility;
- local-first product acceptance before Tencent Cloud public deployment.

## Product policy

```text
pending content may be REVIEW_VISIBLE
while
operational_eligible = false
and
ai_eligible = false
```

The existing operational city API remains fail closed for non-VERIFIED records. The R4 strict AI router remains VERIFIED-only. R5 does not create an approval/status-mutation API.

## llm_wiki decision

`ARCHITECTURE_AND_PROTOCOL_REUSE_NOW`.

No GPL implementation source is copied into AOG in R5. Direct source integration/forking remains an explicit license decision.

## Deployment order

Tencent Cloud public deployment is on HOLD until local product acceptance closes.

```text
ChatGPT R5 source + CI
→ freeze exact R5 SHA
→ MiniMax local exact-SHA deployment
→ Codex same-SHA knowledge-review + Issue #12 retest
→ ChatGPT remediation if needed
→ Owner local customer-value acceptance
→ separate Tencent Cloud deployment Goal
```

## Claim ceiling

Not yet established:

- R5 GitHub Source Gate PASS;
- local knowledge-review usability PASS;
- MiniMax exact-SHA local deployment PASS;
- Codex focused product-experience PASS;
- Tencent Cloud deployment;
- release readiness;
- Human Owner final gate.