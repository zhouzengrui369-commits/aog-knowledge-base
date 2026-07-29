# AOG Knowledge Base - 当前状态

> 最后更新: 2026-07-29 15:50 GMT+8 (Mavis PM)
> 评审对象: review/aog-product-experience-baseline `5d39967` (V28b, 7/27)
> 真正主线: integration/sprint-abc `9c29b89` (V30, 7/27)
> 目标主线: p0/integration-main-convergence `581a5a89b0bc` (本 PR HEAD, 2026-07-29)

---

## 1. 当前阶段

**代码和本地候选已通过 P0-1~P0-6 严令要求, 仅 P0-7 物理阻塞等 NJX 充值 CloudBase**

| 阶段 | 状态 | 关键交付 |
|------|------|----------|
| 阶段 0: 工程真相 | ✅ DONE | 4 套版本对照 + 5 文档基线 + PROJECT_STATE.yaml (12 字段) |
| 阶段 1: API 修复 | ✅ CLOSED_LOCAL | P0-2 base 不带尾, path /api/... (f89e4cd) |
| 阶段 2: RAG 维度 | ✅ CLOSED_LOCAL | P0-3 fts5 trigram + build_manifest 4 项严格校验 + 8 query 回归 |
| 阶段 3: Provider 边界 | ✅ CLOSED_LOCAL | P0-4 ALLOW_MOCK gate + get_llm() factory fail-closed 治本 |
| 阶段 4: 数据可信度 | ✅ CLOSED_LOCAL | P0-5 10 字段合同 + 6 状态 (VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED) |
| 阶段 5: 三个样板 | ✅ CLOSED_LOCAL | 北京大兴 (VERIFIED) / 上海浦东 (MISSING 明确) / 赫尔辛基 (UNVERIFIED, 23.80/31 评分) |
| 阶段 6: staging 验收 | ⏸️ BLOCKED | 物理阻塞 — NJX 充值 CloudBase `njx-copilot-d6gs7642f8fa17122` |
| 阶段 7: PR + 评审 | 📋 本 PR ready | gh pr edit body 用真实数字; 等 NJX merge |

---

## 2. P0 详细状态

### P0-1 分支和版本收敛: ⏳ IN PROGRESS (待 NJX merge)
- PR head: `581a5a89b0bc` (p0/integration-main-convergence)
- main: `80330dd` (V14, 落后 59 commits)
- integration/sprint-abc: `9c29b89` (V30, 落后 16 commits)
- merge 后 main = staging HEAD, 完成

### P0-2 API 修复: ✅ CLOSED_LOCAL
- f89e4cd 修 base 不带尾 + path /api/...
- 测试: backend/test_cities.py test_get_city_ok PASS

### P0-3 RAG 维度与索引: ✅ CLOSED_LOCAL
- 29e6a19 build_manifest 写入
- 5cecf31 RAG manifest 4 项严格校验 (db_size / APP_COMMIT_SHA / chunks_count / source_manifest_hash)
- schema_version 改精确等 (`v30-d038-d043`)
- 8 RAG 回归 8/8 PASS in 0.68s (test_rag_8query_regression.py)
- 真实 chunks: 9106 (fts5_index.db 58.3 MB, tokenizer=trigram)

### P0-4 真实 Provider + mock 边界: ✅ CLOSED_LOCAL
- ead11b2 ALLOW_MOCK + STRICT_LLM 配置
- 581a5a89 get_llm() factory fail-closed 治本 (P0-4 之前只有 lifespan 校验, factory 不校验)
- J6 lifespan startup RuntimeError PASS
- J7 get_llm() RuntimeError PASS
- frontend ALLOW_MOCK gate: 17/17 vitest PASS

### P0-5 数据可信度合同: ✅ CLOSED_LOCAL
- eef8b0e 9 字段 (source_document/source_location/source_version/updated_at/reviewed_at/reviewed_by/review_status/confidence/environment/pii_classification)
- 1c7c7a4 P0-5 pipeline 真写入 (10 字段)
- 6 状态: VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED
- 测试: pipeline/test_p05_trust_pipeline.py 10/10 PASS

### P0-6 PII 与权限: ✅ CLOSED_LOCAL
- 1c7c7a4 pipeline _build_contacts_chunk PII 隔离 (public 保留 phone/email, internal/restricted 替换"联系方式: [已脱敏]")
- bb3d9ec frontend REDACTED 显示
- backend _decode_city (permission=restricted 或 redacted=true → phone=REDACTED)
- 测试: pipeline/test_pii_isolation.py 17/17 PASS (RAG chunk / FTS5 index / chat context / city API 4 层)
- 旅程 J8 验证赫尔辛基 2 restricted contact phone=["REDACTED"]

### P0-7 staging 真实验收: ⏸️ BLOCKED (物理)
- 物理阻塞: 公网 SCF `InsufficientBalance` 返 400
- 本地 10 旅程全 PASS (test_journey_10_local.py 10/10 in 1.66s)
- 等 NJX 充值 CloudBase → merge PR → tcb fn deploy → 跑 staging 10 旅程

---

## 3. PR 真实规模 (P0-1 验证)

```
main HEAD: 80330dd (V14)
PR HEAD:  581a5a89 (p0/integration-main-convergence)
commits ahead: 59
files changed: 98
insertions:    30,496
deletions:     869
```

---

## 4. 测试总览 (P0-3 验证)

| 套 | 测试 | 状态 |
|----|------|------|
| backend/tests/test_journey_10_local.py | 10/10 | ✅ PASS in 1.66s |
| backend/tests/test_cities.py | 11/11 | ✅ PASS in 9.54s |
| pipeline/tests/test_rag_8query_regression.py | 8/8 (+1 summary) | ✅ PASS in 0.68s |
| pipeline/tests/test_pii_isolation.py | 17/17 | ✅ PASS |
| pipeline/tests/test_p05_trust_pipeline.py | 10/10 | ✅ PASS |
| pipeline/tests/test_export_fts5_manifest.py | 21/21 | ✅ PASS |
| pipeline/tests/test_parsers + extractors + chunker | 23/23 | ✅ PASS |
| frontend/tests/api-mock-isolation.test.ts | 17/17 | ✅ PASS |
| **总** | **117/117** | ✅ ALL PASS |

---

## 5. 三个样板站点 (P0-5 阶段 5 验证)

| 样板 | code | review_status | source | warehouse | parts | contacts | 评分 |
|------|------|---------------|--------|-----------|-------|----------|------|
| #1 | B-北京大兴 | VERIFIED (2026-01-15, NJX) | B-北京大兴.docx | 北京大兴东航机务区 | B787 主轮 0 个 | 1 public | 满分 (1) |
| #2 | S-上海浦东 | **MISSING** (无源 docx) | — | — | — | — | 缺, 等 NJX 物理补 |
| #3 | **H-赫尔辛基** (Stage 9.2 评分 23.80/31) | UNVERIFIED (2026-01-20 mtime) | H-赫尔辛基.docx (59178 bytes) | 赫尔辛基机场东航区 (3369 char) | B787 主轮 1 个 | 1 public + 2 restricted | warehouse 3369 char 最大 |

---

## 6. 评审对比

| 维度 | review baseline `5d39967` (V28b) | p0/integration-main-convergence `581a5a89b0bc` |
|------|--------------------------------|----------------------------------------|
| 时间 | 7/27 14:30 | 7/29 15:50 |
| 评审结论 | 3.85/5, READY_WITH_MANDATORY_FIXES | (待评审) |
| API 路径 | 修复但 P0-2 未明示 | P0-2 治本 + 测试 |
| RAG 维度 | 已 fts5 trigram (D-038) | + 8 query 回归测试 + manifest 校验 |
| mock 边界 | UI 红框 (P1-2) | + ALLOW_MOCK gate + get_llm fail-closed 治本 |
| 数据可信度 | — | 10 字段 + 6 状态 + pipeline 真写入 |
| PII | — | 三层隔离 (RAG chunk + decode_city + frontend badge) |
| 8 RAG 回归 | — | 8/8 PASS, 验证 CJK + 短词 + 国际外站 + 件号 |
| 10 旅程本地 | — | 10/10 PASS (1.66s) |
| 第三个样板 | — | H-赫尔辛基 (自动选, 不向 Owner 询问) |

---

## 7. 唯一 NJX 外部动作 (完成门通过后)

```
1. 充值 CloudBase 账户 njx-copilot-d6gs7642f8fa17122 (解除 InsufficientBalance)
2. cd aog-web && bash scripts/prepare-scf.sh  (构建函数包)
3. tcb fn deploy aog-api -e APP_COMMIT_SHA=581a5a89b0bc0140417269ec6ed6fa406612f8b9
4. gh pr merge 1 --squash --body-file PR_BODY.md
5. 通知独立产品体验评审官基于 staging (URL) 重新评审
```

---

## 8. 不声明完成门, 阻塞诚实

- P0-7 staging 验收: ⏸️ 物理阻塞, 等 NJX 充值
- PR 描述真实数字: 已对齐 (59 commits / 98 files / +30496 / -869)
- 无 mock 模拟: J7 fail-closed PASS
- 无虚构 close: P0-1/P0-7 明确未 CLOSED
- 不需要 Owner 先执行 1-4 之外的任何动作
