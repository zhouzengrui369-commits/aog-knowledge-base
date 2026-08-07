# AOG Public Core Compatibility Assessment

## Decision

`COMPATIBLE_WITH_THIN_ADAPTER`

## Existing assets preserved

- `PROJECT_STATE.yaml` remains the legacy engineering-version truth and is not modified.
- Existing AOG CI, staging, production-readiness, product-review, data-governance, PII, RAG, verification-status, and deployment evidence remain authoritative for their scopes.
- Existing task directories and historical receipts remain untouched.
- Product and data paths remain outside this Goal.

## Missing reusable entry surfaces

At the input SHA, the repository had no root `AGENTS.md`, no root `PROJECT_STATUS.md`, and no public-Core governance lock. This Goal adds those surfaces without claiming they replace historical project truth.

## Role mapping

| Framework role | AOG executor | Authority |
|---|---|---|
| Remote Parent PM + Coding Agent | ChatGPT | Goal contracts, source/tests, GitHub commits, PRs, CI remediation |
| Local Deployment Agent | MiniMax Code | exact-SHA install/build/start/deploy receipts; no silent source edits |
| Local Test / Product Auditor | Codex | real browser/computer-use/accessibility/product-experience evidence |
| Owner | NJX | data truth, verification decisions, credentials, CloudBase, release and final value gate |

## AOG-specific restrictions

The public Core is narrowed by these existing AOG constraints:

- real data and verification status are Owner-controlled;
- synthetic VERIFIED evidence demonstrates a code path only;
- PII/data-governance controls remain fail closed;
- CloudBase and production deployment require explicit Owner authority;
- CI or documentation success cannot substitute for runtime/accessibility/product acceptance;
- local deployment and Codex testing must bind to one exact candidate SHA.

## No-overwrite proof

The adoption changes only new governance paths. It does not modify:

- `aog-web/**`
- `AOG知识库/**`
- `PROJECT_STATE.yaml`
- `reports/**`
- `scripts/**`
- `extractors/**`
- `tests/**`
- existing workflows
- package manifests or lockfiles

## First real-loop requirement

Governance installation alone does not validate `v1.0.0`. After this adoption is accepted, one bounded AOG product Goal must complete:

`ChatGPT source fix → exact-SHA MiniMax deployment → Codex real-operation test → ChatGPT remediation if needed → focused redeploy/retest → Owner acceptance`.