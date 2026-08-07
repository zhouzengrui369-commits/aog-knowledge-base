# R5 Cloud Deployment Decision

## Decision

`TENCENT_CLOUD_PUBLIC_DEPLOYMENT = HOLD_UNTIL_LOCAL_ACCEPTANCE`

The repository already contains CloudBase v2 staging packaging/deploy assets. R5 does not rebuild them.

Actual CloudBase deployment requires an authenticated `tcb` CLI/cloud session, staging environment identity, provider/COS secrets, billing availability and explicit cloud-write authority. The ChatGPT GitHub execution surface can change source, tests, workflows and PRs, but it does not have a Tencent Cloud shell/session or repository-secret management surface. It therefore cannot truthfully perform the real public cloud write from this environment.

## Why local first

The current product has a failed user experience before cloud deployment: pending knowledge is hidden in the operational surface, so the Owner cannot inspect the records that need review. Public deployment before fixing and accepting this flow would publish a known-bad experience.

## Gate order

```text
ChatGPT R5 source + GitHub CI
→ exact R5 candidate
→ MiniMax local deployment only
→ Codex local knowledge-review + Issue #12 retest
→ ChatGPT fix/redeploy if needed
→ Owner local customer-value acceptance
→ separate Tencent Cloud deployment Goal
```

No CloudBase/COS write is authorized by R5.