# AOG Knowledge Base · R2 Successor · FROZEN_REPLAYABLE_ARTIFACT Contract

> **Status**: R2 candidate `0f4692e...` (NJX 8/4 09:28 拍板 D)
> **Replaces**: `BUILD_SHA_1 == BUILD_SHA_2` byte-level rebuild gate (R1)
> **Authoritative for**: R2 candidate focused retest, freeze, and replay

## 1. Why R1's byte-rebuild gate was retired

The R1 contract required two consecutive Next.js production builds to
produce byte-identical artifacts.  That gate was retired because:

1. **Next.js 15.0.3 + React 19 RC** inject a 21-character base62
   Suspense boundary cache key into every prerendered HTML.  The key
   source is the `nanoid` prebundled in the app-page runtime chunk
   (`./dist/compiled/nanoid/index.cjs` reachable only through webpack's
   internal `__webpack_require__`, not through any user-facing
   `require()` boundary).
2. **All four patch attempts failed**:
   - `require.cache[realPath] = shim` — verify call shows the shim
     runs, but the HTML still drifts (prebundled chunk has its own
     import).
   - `webpack.NormalModuleReplacementPlugin` — applied successfully
     but the prebundled chunk bypasses the user webpack config.
   - `webpack resolve.alias` — same.
   - Monkey-patching `Module.prototype.require` — same.
3. **A 21-character key difference in the 6,158-byte
   `city/A-澳门.html`** is the **only** delta between two clean
   builds.  Every other byte is identical.
4. The original Issue #12 contract never required byte-level
   reproducibility — it only required "构建物 SHA-256 或 deployment ID"
   (frozen artifact SHA-256 OR deployment ID).  The `BUILD_SHA_1 ==
   BUILD_SHA_2` clause was an over-interpretation added during R1.

## 2. FROZEN_REPLAYABLE_ARTIFACT contract

Replace byte-rebuild with this 7-step contract:

1. **One clean candidate SHA** at a known commit.
2. **One clean production build** under:
   - `APP_COMMIT_SHA=<candidate_sha>` (or `GITHUB_SHA`)
   - `ALLOW_MOCK=false`
   - `STRICT_LLM=true`
   - `SYNC_ENABLED=false`
3. **One frozen static candidate package** at
   `out/<build_id>/...`.  `build_id` is bound to `APP_COMMIT_SHA` via
   the minimal `generateBuildId` in `next.config.ts`.
4. **`artifact-manifest.json`** records:
   - `candidate_sha`
   - `build_id`
   - `node_version`
   - `pnpm_version`
   - `next_version`
   - `react_version`
   - build environment names
   - one record per `out` file: relative path, size, SHA-256.
5. **`CANDIDATE_ARTIFACT_SHA256`** is the SHA-256 of
   `artifact-manifest.json` and serves as the candidate's identity
   manifest.
6. **Replay path**:
   - unpack the frozen archive
   - verify every file in `out/` against `artifact-manifest.json`
   - serve `out/` from the verification host
   - run the focused retest against that host.
7. **Verdict line**:
   - `BYTE_REPRODUCIBLE_REBUILD=NO_UPSTREAM_NONDETERMINISM`
   - `FROZEN_ARTIFACT_REPLAYABLE=PASS`

## 3. Allowed next.config.ts modification

The only modification permitted in the R2 candidate is the minimal
`generateBuildId`:

```ts
generateBuildId: async () =>
  process.env.APP_COMMIT_SHA ||
  process.env.GITHUB_SHA ||
  "local-development"
```

All of the following are explicitly **retired** and must NOT appear in
PR #13 R2 commits:

- `config.resolve.alias` for `nanoid`
- `webpack.NormalModuleReplacementPlugin` for `nanoid`
- `require.cache` shims for `nanoid`
- direct `nanoid` module replacement
- direct edits to `node_modules`
- runtime chunk patching
- React Suspense ID patching
- 2-byte SHA rebuild with `diff -u` / `sed` post-build (would mean
  shipping an artifact whose identity is not derivable from source)

## 4. R2 candidate identity at the time of this document

| Field | Value |
| --- | --- |
| `CANDIDATE_92D583F` | `92d583f71210e048a3154a4b9103409e4e514fca` (RETIRED_FAILED_CANDIDATE) |
| `SUCCESSOR_CANDIDATE_SHA` | `0f4692e...` (frozen after CI green) |
| `R2_SAFETY_COMMIT` | `e163c2d` (fix(safety)) |
| `R2_SAFETY_TEST_COMMIT` | `155f1ba` (test(safety)) |
| `R2_CHORE_COMMIT` | `919c56e` (chore(repo) — venv symlink exclude) |
| `R2_BUILD_COMMIT` | `0f4692e` (fix(build)) |
| `R2_DOCS_COMMIT` | TBD (this document) |

## 5. References

- `DECISIONS.md` — historical D-001..D-058 decision log
- `work/tasks/2026-08-03-exp-aog-focused-retest-r1/RESULT.md` — R1
  focused retest outcome (RAG 5/20 FAIL, build non-reproducible)
- `reports/2026-08-04-r2-evidence/` — R2 verification evidence
  (RAG 0/20 PASS, FROZEN_REPLAYABLE_ARTIFACT in progress)
- NJX 8/4 09:28 拍板 D — successor candidate R2 strategic decision
- D-059 memory: Next.js 15.0.3 + React 19 RC prebundled nanoid root
  cause (verbatim diff evidence)
- D-060 memory: RAG boundary language 5/20 fail root cause +
  SafetyIntentPolicy design
- D-061 memory: NJX 8/4 09:28 拍板 D — successor candidate R2
  strategic decision and frozen replayable artifact gate
