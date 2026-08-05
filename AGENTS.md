# Agent Entry Point

This repository adopts the public ChatGPT Parent PM framework through a thin project adapter.

Read in this order before planning, coding, deploying, or testing:

1. `.github/skills/chatgpt-parent-pm/SKILL.md`
2. `.github/skills/chatgpt-parent-pm/PROJECT_PROFILE.yaml`
3. `.github/skills/chatgpt-parent-pm/GOVERNANCE_LOCK.json`
4. `PROJECT_STATUS.md`
5. `PROJECT_STATE.yaml` — legacy engineering version truth; do not silently rewrite it
6. the active Goal contract named by `PROJECT_STATUS.md`
7. relevant architecture, operations, security, data-governance, and deployment documents
8. the exact branch, pull request, and candidate SHA being acted on

## Durable truth

GitHub is the durable source of project truth. Chat history and local worktrees are execution context only.

## Default roles

- ChatGPT: remote Parent PM and Coding Agent; owns source changes, tests, commits, PRs, CI triage, and fixes.
- MiniMax Code: exact-SHA local deployment runner unless a Goal names another executor.
- Codex: real-operation test and product-experience auditor unless a Goal names another executor.
- Owner: product decisions, sensitive permissions, real data, CloudBase actions, merge/release, and final customer-value acceptance.

## Safety boundary

Do not infer that CI success proves runtime, product-experience, data-readiness, CloudBase deployment, or release readiness. Do not modify product data, credentials, verification status, production infrastructure, or release state without explicit Owner authority.