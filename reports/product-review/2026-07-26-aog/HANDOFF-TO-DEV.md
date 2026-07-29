# AOG 评审 → Dev Session Handoff (2026-07-26)

> **给 dev session `mvs_a38cc4e1c46d4aadb1591d423acc43fe` (AOG 知识库网站开发)**
> **From**: Mavis (产品体验评审官, 独立评审 root session)
> **Date**: 2026-07-26 15:10 CST
> **状态**: 等待 dev session 接收 + 基于此报告迭代

---

## 1. 评审已完成 — 请查阅

✅ **报告已生成 + GitHub push 成功**:
- 报告: `reports/product-review/2026-07-26-aog-product-experience-review.md` (26KB, 379 行)
- 证据: `reports/product-review/2026-07-26-aog/evidence/` (30 张截图 + 5 tab)
- Commit: `40ce57d` (main HEAD)
- 评审版本: `7d9ac13` (V14, 2026-07-22, **main 分支** — 不是你工作的 integration/sprint-abc)

**结论**: `NOT_READY` (平均分 2.20/5, 行业产品线阈值 3.0)

---

## 2. 你需要做的事（按优先级）

### 优先级 P0: 验证 integration/sprint-abc 修复了哪些 P0/P1

**评审基于 main V14 (7/22)。你在 integration/sprint-abc HEAD `7a53723` (7/24) 推了 16 个 commit (V15-V28b)。**

请先回答 4 个问题:

1. **API base 拼接 bug** 修了吗？  
   检查 `lib/api.ts:16` 是不是 `BASE = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/api$/, "")`  
   或 build 时 `next.config.ts` 正确处理

2. **RAG 维度 mismatch** 修了吗？  
   检查 `pipeline/embedder.py` 和 `chroma_client.py`  
   1024 维 vs 384 维的 query 还能跑吗？

3. **MINIMAX_API_KEY 接入** 修了吗？  
   `.env.cloudbase.example` 是不是 hardcode 了真 key？  
   部署后 `llm_mode` 是不是 `minimax` 而不是 `mock`？

4. **公网 SCF 重新部署** 做了吗？  
   旧 SCF `76cca2c` (Jul 17) 缺 `/api/airlines` / `/api/auth/login`  
   重新 `tcb fn deploy` 了吗？

**这 4 个问题答完再决定下一步**。如果都修了 → 重做完整评审 (基于 V28b 集成版);还有 broken → 进入 P1 整改。

### 优先级 P1: 整改数据可信度问题 (评审报告 §5 P1 列表)

报告中 9 个 P1 严重问题，主要 3 个工作量最大:
- **数据抽取质量**: 同一备件模板套 200 城市 → 重写 `pipeline/extract_city.py` 真正按 docx 抽
- **mock fallback UI 标注**: 用户被蒙骗 → 加 "演示数据" 红框
- **公网死链**: hero 推荐 `/city/S-上海浦东` 但 SSG 漏 → 修 `generateStaticParams` + 加 fallback

### 优先级 P2: main merge + 公网部署

NJX 拍板后:
1. `git checkout main && git merge integration/sprint-abc --no-ff`
2. 前端 `pnpm build` + `tcb hosting deploy`
3. 后端 SCF `tcb fn deploy aog-api`
4. 等 10 分钟 CDN
5. 硬刷 `https://aog.njx.com` verify 5 张截图

---

## 3. 重新评审时的检查清单

- [ ] 公网 `https://aog.njx.com/api/cities` 返 200 (不是 400 double-prefix)
- [ ] `/api/cities?status=现行` 返 155+ 城市，stock > 0
- [ ] `/api/experiences?limit=10` 返 10+，content_len > 0
- [ ] `/api/chat` 返 200+ 字符真 LLM 回答（非 "Mock 模式"）
- [ ] AI 引用包含 `B787 风挡` 相关 content
- [ ] 上海浦东 / 上海虹桥 可正常访问
- [ ] 数据更新时间 ≤ 7 天 (不是 2026-07-17 一次 batch)
- [ ] 5 个 mock fallback 场景有 "演示数据" 红框
- [ ] 联系人 / 库房 phone 不是 "全国中介表" 重复
- [ ] 移动端 375×812 城市详情正常

---

## 4. 联系 / 上下文

- **本评审 root session**: `mvs_adf2f57e1be647659f3f4d9b6d04e91b` (已 finished)
- **本 dev session**: `mvs_a38cc4e1c46d4aadb1591d423acc43fe` (你的 session, 7/24 finished)
- **NJX 拍板**:
  - 战略 / 外部承诺 / 资源分配 = NJX 拍
  - 其他 (技术实现 / 整改细节 / 数据重抽 / 部署) = PM (你) 自主
- **OPC 上下文**: NJX 是 OPC 独立创业 + 航材主业 + 12 周飞轮 — AOG 是 openclaw 主线产品 (60% 权重)
- **memory 7/8 教训**: ground truth 优先级 = `state.json.verifier_results[].passed` (bool) > verdict_summary > status > verifier_report > git log > deliverable VERDICT
  - 也就是:**不要只信 DELIVERY.md 写 "VERDICT PASS"** — 必须自己 Playwright 实测 5/5 截图才能信
  - 你 7/21 V6/V7 DELIVERY 都写 "VERDICT: PASS" 但**没 commit + 没 deploy**, 这是过去教训

---

## 5. 不要做的事

- ❌ 不要只改 DELIVERY.md 写 "VERDICT: PASS" 而不真做 Playwright verify
- ❌ 不要把 mock fallback 当 "已就绪" — 必须有 UI 红框
- ❌ 不要 push 真实 secret (GitHub push protection 拦 GH013, 你 7/24 已被拦过)
- ❌ 不要跳过上海主基地 — 是吉祥核心,缺失会被一线员工骂
- ❌ 不要依赖 ollama (持续 timeout) — 换 sentence-transformers 本地计算

---

## 6. 期望完成时间

| 阶段 | 时间 | 阻塞 |
|------|------|------|
| 答完 4 个验证问题 | 1 小时 | 不阻塞 |
| 修 P0 (如果还有 broken) | 1 天 | 修完才能继续 |
| 修 P1 (3 个主要) | 1 周 | NJX 拍板 |
| merge main + 公网部署 | 30 分钟 | NJX 拍板 + NJX 物理 (如果 CloudBase CLI 需 OAuth) |
| 重新评审 (基于 V28b) | 2 小时 | 全部整改完 |

---

## 7. 报告路径 (重新阅读)

```
/Users/njx/Project/AOG知识库/reports/product-review/2026-07-26-aog-product-experience-review.md
```

GitHub: `https://github.com/zhouzengrui369-commits/aog-knowledge-base` commit `40ce57d` (main 分支)

证据 30 张图在 `evidence/` 子目录。

---

**收到请回复 NJX "已读,开始验证 4 个 P0 问题"**。如果有任何疑问,直接 scratchpad 留言,root session 会在 idle 1h 后扫到。

— Mavis (产品体验评审官)
2026-07-26 15:10 CST
