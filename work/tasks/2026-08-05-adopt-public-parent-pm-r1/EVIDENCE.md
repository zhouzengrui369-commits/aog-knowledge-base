# GOAL-GOV-AOG-001 Evidence

## Input identity

```text
repository = zhouzengrui369-commits/aog-knowledge-base
base branch = main
base SHA = 1727a56aaa67ec2a29ab04076f0d8f84952b3e43
adoption branch = chatgpt/adopt-public-parent-pm-r1
```

## Public Core identity

```text
repository = zhouzengrui369-commits/chatgpt-parent-pm
version = 0.1.0-alpha
merged Core SHA = 99e88020789603f17de715775b455e91e4e20b17
bootstrap PR = #1
bootstrap PR Head CI = PASS
```

## Added governance paths

- `AGENTS.md`
- `PROJECT_STATUS.md`
- `.github/skills/chatgpt-parent-pm/SKILL.md`
- `.github/skills/chatgpt-parent-pm/PROJECT_PROFILE.yaml`
- `.github/skills/chatgpt-parent-pm/GOVERNANCE_LOCK.json`
- `.github/workflows/parent-pm-governance.yml`
- `validators/__init__.py`
- `validators/validate_install.py`
- `work/tasks/2026-08-05-adopt-public-parent-pm-r1/GOAL.md`
- `work/tasks/2026-08-05-adopt-public-parent-pm-r1/COMPATIBILITY.md`
- `work/tasks/2026-08-05-adopt-public-parent-pm-r1/RESULT.md`
- `work/tasks/2026-08-05-adopt-public-parent-pm-r1/EVIDENCE.md`

## Untouched boundaries

The adoption must show zero changes under:

- `aog-web/**`
- `AOG知识库/**`
- `PROJECT_STATE.yaml`
- `reports/**`
- `scripts/**`
- `extractors/**`
- `tests/**`
- existing workflow files
- package manifests and lockfiles

## Pending post-commit evidence

After the Draft PR is created, record externally in the PR conversation:

- exact final branch Head;
- exact PR Head;
- workflow runs and conclusions;
- reverse-fetched blob SHA for every added governance file;
- changed-file allowlist;
- Parent PM verdict;
- Owner verdict.

Do not insert the final commit SHA into the commit that creates itself.