# GOAL-GOV-AOG-001 — Adopt Public ChatGPT Parent PM Core

## Identity

- Repository: `zhouzengrui369-commits/aog-knowledge-base`
- Input branch: `main`
- Input SHA: `1727a56aaa67ec2a29ab04076f0d8f84952b3e43`
- Development branch: `chatgpt/adopt-public-parent-pm-r1`
- Public Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- Goal ID: `GOAL-GOV-AOG-001`
- Product weight: `0%`

## Outcome

Install a thin, exact-SHA-pinned public Parent PM adapter so any authorized Agent can recover AOG project truth and use the standard remote-development/local-deployment/local-test role model without replacing AOG-specific governance or changing product behavior.

## Scope

### Included

- Agent entry point;
- thin project adapter;
- AOG Project Profile;
- exact public Core Governance Lock;
- non-destructive current status entry;
- standard-library validator;
- focused governance CI;
- compatibility, result, and evidence records.

### Excluded

- product source, frontend, backend, pipeline, tests, data, fixtures, reports, scripts, package/lockfiles, dependencies;
- `PROJECT_STATE.yaml` rewrite;
- runtime, local deployment, real data, CloudBase, credentials, signing, release;
- merge to `main` without separate Owner approval;
- any change to KnowMe, Copilot, Lingxi Presentation, or the public framework repository.

### Allowed paths

- `AGENTS.md`
- `PROJECT_STATUS.md`
- `.github/skills/chatgpt-parent-pm/**`
- `.github/workflows/parent-pm-governance.yml`
- `validators/**`
- `work/tasks/2026-08-05-adopt-public-parent-pm-r1/**`

### Forbidden paths

- `aog-web/**`
- `AOG知识库/**`
- `PROJECT_STATE.yaml`
- `reports/**`
- existing workflows
- existing historical task directories
- any credential, environment, database, or deployment artifact

## Acceptance criteria

- [x] public Core is pinned by exact merged SHA;
- [x] thin adapter preserves AOG-specific rules;
- [x] existing engineering state is referenced, not overwritten;
- [x] direct-main, auto-merge, and auto-release remain false;
- [x] Owner-only AOG actions are explicit;
- [x] governance adoption remains 0% product weight;
- [ ] governance workflow PASS on exact PR Head;
- [ ] existing AOG CI remains green on exact PR Head;
- [ ] branch Head equals PR Head;
- [ ] exact-SHA reverse fetch verifies all governance files;
- [ ] Parent PM review PASS;
- [ ] Owner merge decision.

## Required evidence

- GitHub branch and PR identity;
- public Core SHA and local lock contents;
- changed-file allowlist;
- validator/CI results;
- reverse-fetched governance files;
- explicit list of untouched product/data/evidence paths.

## Terminal status rules

- `PASS`: every acceptance criterion closes.
- `PARTIAL PASS`: implementation is committed but CI/review/Owner gates remain.
- `BLOCKED`: identity, permissions, existing-state overlap, or CI failure prevents safe progress.
- `FAIL`: the adapter weakens an invariant or changes product/data/runtime state.