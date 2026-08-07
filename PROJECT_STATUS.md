# AOG Knowledge Base — Current Project Status

## Development ownership

- Governance Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- ChatGPT role: Remote Parent PM + Coding Agent
- MiniMax Code role: exact-SHA local deployment runner
- Codex role: real-operation test + product-experience auditor
- Owner role: product/data/CloudBase/release/final acceptance decisions

## Active Goal

- Goal: `GOAL-AOG-ISSUE12-R4`
- Contract: `work/tasks/2026-08-07-issue12-p0-runtime-closure-r4/GOAL.md`
- Input `main`: `62d53b42e7994131a762f93db0e0410e4a917ce3`
- Development branch: `chatgpt/issue12-p0-runtime-closure-r4`
- Draft PR: `#15`
- Parent issue: `#12`
- Product weight: `0%` — safety/runtime closure, no feature completion credit
- Status: `GITHUB_SOURCE_GATE_PASS · MINIMAX_EXACT_SHA_AUTHORIZED · CODEX_HOLD_PENDING_MINIMAX`

## Takeover audit and source repair

Takeover source review found two P0 regressions on the former production path:

1. the verification policy quarantined UNVERIFIED hits, but historical `chat_safe.py` later reintroduced `raw_hits` into LLM context;
2. provider-private `<think>` content was emitted as a public SSE event and could be rendered by the frontend.

R4 adds a strict production router and switches `main.py` to it. The historical router remains in Git history for audit, but is no longer mounted as the production chat API. The frontend also discards legacy `think` events defensively.

## Source Gate

The R4 code candidate reached all-green GitHub source gates before this status transition:

- parent-pm-governance: PASS;
- production-readiness: PASS;
- aog-ci: PASS;
- staging-validation: PASS.

Because this status update changes the branch Head, the exact deployable SHA is **not written inside this self-referential file**. Parent PM must record the final CI-green PR Head in a non-mutating PR receipt after the final workflow run. MiniMax may execute only that receipt-bound SHA.

## Local execution state

### MiniMax Code

Authorized **after** Parent PM posts the final candidate-freeze receipt on PR #15.

Read:

`work/tasks/2026-08-07-issue12-p0-runtime-closure-r4/MINIMAX_DEPLOYMENT.md`

MiniMax must not edit or commit source. Its PASS is deployment/technical evidence only.

### Codex

`HOLD_PENDING_MINIMAX_RECEIPT`

Codex starts only after MiniMax returns a coherent receipt for the exact same frozen candidate.

Read:

`work/tasks/2026-08-07-issue12-p0-runtime-closure-r4/CODEX_FOCUSED_RETEST.md`

## Current claim ceiling

Still **not established**:

- local exact-SHA deployment PASS;
- Issue #12 focused runtime retest PASS;
- VoiceOver PASS;
- real MiniMax 20-case `0/20` PASS on the final R4 candidate;
- CloudBase deployment;
- production-data readiness;
- release readiness;
- Human Owner Gate.

## Existing truth preserved

`PROJECT_STATE.yaml` remains legacy engineering-version history and is not silently rewritten. Existing product-review reports, release manifests, data-governance records, PII gates and deployment scripts remain authoritative for their own evidence scopes.

## Next sequence

```text
final GitHub CI on PR #15 Head
→ Parent PM non-mutating candidate-freeze receipt
→ MiniMax exact-SHA local deploy/technical receipt
→ Codex same-SHA focused product retest
→ ChatGPT forward fix if needed
→ focused redeploy/retest
→ Owner final gate
```
