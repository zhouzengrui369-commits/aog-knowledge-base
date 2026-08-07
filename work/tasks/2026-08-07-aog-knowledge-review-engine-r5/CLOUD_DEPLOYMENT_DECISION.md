# R5 Cloud Deployment Decision

## Immediate decision

`TENCENT_CLOUD_PUBLIC_DEPLOYMENT = HOLD_UNTIL_LOCAL_ACCEPTANCE`

The repository already contains CloudBase v2 staging packaging and deploy scripts, but actual deployment requires an authenticated `tcb` CLI session, staging environment identity, secrets/bucket/provider configuration and explicit cloud-write authorization.

The current Parent PM GitHub connector can modify source, tests, workflows and PRs, but does not provide a Tencent Cloud shell/session or repository-secret management surface. It therefore cannot truthfully claim to execute the real CloudBase write from this environment.

## Why local first

The current local product fails a core experience: non-VERIFIED knowledge is hidden, so the Owner cannot inspect the content that needs review. Public deployment before fixing and accepting that workflow would publish an unusable product state.

## R5 gate order

```text
ChatGPT source implementation
→ GitHub CI
→ exact successor SHA
→ MiniMax local exact-SHA deployment
→ Codex local product review
→ ChatGPT remediation if needed
→ Owner local customer-value acceptance
→ separate Tencent Cloud deployment Goal
```

Cloud scripts are preserved and will be reused after local acceptance; R5 does not rebuild them from scratch.