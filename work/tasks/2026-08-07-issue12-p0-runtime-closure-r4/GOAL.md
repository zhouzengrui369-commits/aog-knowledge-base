# GOAL-AOG-ISSUE12-R4 — Restore Verified-Only AI Boundary and Private Reasoning Safety

## Identity

- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Input branch: `main`
- Input SHA: `62d53b42e7994131a762f93db0e0410e4a917ce3`
- Development branch: `chatgpt/issue12-p0-runtime-closure-r4`
- Parent issue: `#12`
- Public governance Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- Product weight: `0%` — safety/runtime closure, no new feature credit

## User outcome

An AOG user must never receive operational content from an UNVERIFIED city through AI, and must never see provider-private chain-of-thought. VERIFIED sources remain usable and traceable. The exact GitHub candidate is then deployed by MiniMax Code and independently exercised by Codex on the Owner Mac.

## Source-audit trigger

Takeover review found two P0 regressions on current `main`:

1. `verification_policy.py` correctly quarantines non-VERIFIED sources, but `chat_safe.py` later passes `raw_hits` — including UNVERIFIED city material — back into the model context.
2. `chat_safe.py` emits provider `<think>` content as SSE `think`; the frontend parser forwards it into a visible `thinkingSteps` panel.

Both contradict Issue #12's accepted fail-closed contract and the existing production rule that model-private reasoning must not be rendered.

## Scope

### Included

- add a strict production chat router;
- route production FastAPI chat endpoints through the strict router;
- only `policy.hits` with `verification_status=VERIFIED` may enter LLM messages;
- targeted non-VERIFIED cities return deterministic code-generated boundary responses without model invocation;
- no-verified-match returns a deterministic safe response without model invocation;
- provider-private `<think>`, `<thinking>`, `<reasoning>` and structured sentinel blocks are filtered server-side and never emitted as public SSE events;
- frontend ignores any legacy `think` event defensively;
- focused backend/frontend regression tests;
- exact-SHA MiniMax deployment contract and Codex focused-retest contract;
- current project status/handoff update.

### Explicitly preserved

- reference routing from Issue #12 remediation;
- sessionStorage session continuity and identity cleanup;
- queued/retrieving/generating/done/error/cancelled state machine;
- timeout/cancel/retry controls;
- accessible `发送问题` control;
- existing PII/data-governance gates;
- existing build-data-release and local deployment assets.

### Excluded / Owner locked

- real Owner knowledge-source edits;
- verification-status changes;
- real-data imports;
- CloudBase writes/deployment;
- credentials or billing;
- signing/notarization;
- production release;
- automatic merge.

## Code acceptance

- [ ] Targeted UNVERIFIED city never invokes the LLM.
- [ ] UNVERIFIED protected fixture content never appears in LLM messages, answer text, sections, or references.
- [ ] Mixed retrieval sends only VERIFIED eligible hits into LLM messages.
- [ ] No verified source returns a deterministic no-match boundary without model invocation.
- [ ] Provider `<think>` / `<thinking>` / `<reasoning>` content never appears in SSE output.
- [ ] Backend never emits `event: think` from the strict production router.
- [ ] Frontend ignores legacy `think` events and never forwards them to a rendering callback.
- [ ] Reference/session/state/accessibility focused regressions remain green.
- [ ] `aog-ci`, `production-readiness`, `staging-validation`, and governance checks are green on the exact PR Head.

## Local deployment acceptance — MiniMax Code

On the frozen candidate SHA, MiniMax must:

- prove clean exact-SHA checkout;
- reuse existing local environments when safe;
- rebuild the data release for that SHA;
- prove 8-query RAG PASS and PII-7a v2 forbidden hits = 0;
- start real backend/frontend with mock disabled;
- run the real 20-case RAG pressure suite at `0/20` failures;
- return release/artifact/hash identities and sanitized logs;
- make no source change, commit, push, merge, CloudBase write, or real-data mutation.

## Independent acceptance — Codex

Codex tests the same exact deployed SHA and must prove:

1. UNVERIFIED city question is blocked with no operational protected content;
2. VERIFIED control city can produce grounded, traceable content;
3. no raw provider reasoning is visible in UI, DOM, network transcript, or accessibility tree;
4. all clickable references resolve semantically; unsupported sources are non-clickable;
5. close/reopen, reference round-trip, refresh, in-flight refresh, logout, expiry, and session rotation behave per contract;
6. normal, slow, error, timeout and cancel terminal states are correct;
7. keyboard Enter/Space/focus/live-region behavior passes;
8. VoiceOver announces `发送问题` and disabled-state help;
9. candidate SHA / release identity matches MiniMax receipt.

## Terminal states

- `PASS`: code/CI + MiniMax deployment + Codex focused retest + Owner final gate all close.
- `PARTIAL PASS`: GitHub candidate is ready but local/Owner gates remain.
- `BLOCKED`: an external environment, credential, identity or Owner-locked condition prevents progress.
- `FAIL`: candidate violates accepted safety/runtime behavior.
