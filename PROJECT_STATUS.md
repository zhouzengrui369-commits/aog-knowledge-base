# AOG Knowledge Base — Current Project Status

## Development ownership

- Governance Core: `zhouzengrui369-commits/chatgpt-parent-pm@99e88020789603f17de715775b455e91e4e20b17`
- ChatGPT role: Remote Parent PM + Coding Agent
- MiniMax Code role: exact-SHA local deployment runner
- Codex role: real-operation test + product-experience auditor
- Owner role: product/data/CloudBase/release/final acceptance decisions

## R4 status

- Goal: `GOAL-AOG-ISSUE12-R4`
- Previous candidate: `8f99777322e2a13bf5d42de31954e195d40ca967`
- Status: `SUPERSEDED_BY_OWNER_SCOPE_UPDATE`
- MiniMax authorization: `REVOKED`

The R4 safety fixes remain valid input to the successor, but the candidate must not be deployed independently because Owner updated product requirements before local handoff.

## Successor requirements

The next Goal must additionally:

1. evaluate `nashsu/llm_wiki` source-level reuse for the AOG knowledge-management engine;
2. make pending-review knowledge browsable in an authenticated, read-only review surface;
3. preserve the strict boundary that only VERIFIED content may drive operational AI/execution;
4. provide a practical review queue rather than hiding most of the knowledge base;
5. treat local acceptance as the immediate deployment gate before Tencent Cloud public deployment;
6. keep cloud writes, credentials, billing, real-data mutation, and verification decisions under explicit Owner authority.

## Claim ceiling

R4 is not a valid local/runtime/release candidate anymore. No prior R4 CI or source PASS may be reused as a deployment authorization for the successor.