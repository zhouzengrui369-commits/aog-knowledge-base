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
- Parent issue: `#12`
- Product weight: `0%` — safety/runtime closure, no feature completion credit
- Status: `SOURCE_FIX_IN_PROGRESS · LOCAL_AGENTS_HOLD`

## Takeover audit

The Issue #12 remediation merged earlier, but takeover source review found two P0 regressions still present on the current production path:

1. the verification policy quarantines UNVERIFIED hits, but historical `chat_safe.py` later reintroduces `raw_hits` into LLM context;
2. provider-private `<think>` content is emitted as a public SSE event and can be rendered by the frontend.

R4 therefore restores the accepted safety boundary before any new local acceptance claim.

## Current claim ceiling

The following are **not** currently established by this status file or by prior CI:

- local exact-SHA candidate PASS;
- Issue #12 focused runtime retest PASS;
- VoiceOver PASS;
- real MiniMax 20-case `0/20` PASS on the R4 candidate;
- CloudBase deployment;
- production-data readiness;
- release readiness;
- Human Owner Gate.

## Existing truth preserved

`PROJECT_STATE.yaml` remains legacy engineering-version history and is not silently rewritten. Existing product-review reports, release manifests, data-governance records, PII gates and deployment scripts remain authoritative for their own evidence scopes.

## Next sequence

```text
ChatGPT source fix + focused tests
→ GitHub CI
→ freeze exact candidate SHA
→ MiniMax exact-SHA local deploy/technical receipt
→ Codex same-SHA focused product retest
→ ChatGPT forward fix if needed
→ focused redeploy/retest
→ Owner final gate
```

MiniMax and Codex remain HOLD until ChatGPT publishes a CI-green exact candidate SHA and the corresponding contracts.
