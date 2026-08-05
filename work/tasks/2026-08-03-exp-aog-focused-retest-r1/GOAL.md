# GOAL — AOG Focused Experience Remediation R1

## Candidate identity

- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Baseline: `b390629d1684d62a8d0d8c7f4126b4b928633bd8`
- Review: Issue #12
- Product Experience Verdict: `NOT_READY`
- Release Evidence Verdict: `BLOCKED_NON_REPRODUCIBLE_CANDIDATE`
- Human Owner Gate: `NOT_ELIGIBLE`

## Goal

Produce a bounded, replayable code candidate for `EXP-AOG-20260803-001` through `005`:

1. enforce verification status before retrieval and generation;
2. make every reference route explicit and fail closed for unsupported types;
3. restore the same-tab chat session across reference navigation and refresh, while clearing it on logout, expiry or identity rotation;
4. implement a terminal-safe streaming state machine;
5. give the send control a stable accessible name and focused keyboard/VoiceOver retest contract.

## Non-goals

- No CloudBase or COS deployment.
- No real-data import.
- No model, credential or global configuration change.
- No unrelated navigation, positioning or visual redesign.
- No claim that code diff or CI replaces runtime focused retest.

## Completion boundary

Remote completion means code, automated tests, task evidence, a frozen candidate commit and a pull request. Runtime screenshots, VoiceOver recording, real MiniMax 20-case execution and reproducible artifact SHA remain MiniMax Code local gates.