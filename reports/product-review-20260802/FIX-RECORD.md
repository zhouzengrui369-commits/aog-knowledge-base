# 2026-08-02 产品体验评审修复记录

本文件是 `REPORT.md` 的修复索引。代码以总生产冲刺 PR 与最终 main SHA 为准。

| 问题 | 修复位置 | 自动化证据 |
|---|---|---|
| P0-01 经验空壳 | `experience_content.py`, experiences API, experience pages | backend + frontend tests |
| P0-02 404 错数据 | `app/not-found.tsx` | production-readiness Vitest |
| P0-03 18 vs 3 | `/api/stats`, hero/home/404/experience metadata | backend stats test + static contract |
| P0-04 CoT 暴露 | `chat-widget.tsx` | private protocol test |
| P0-05 Markdown/截断 | typed section renderer + table/list fallback + truncation warning | TypeScript/build + source contract |
| P0-06 联系人重复 | `production_policy.py`, `city-tabs.tsx` | trust/dedupe tests |
| P0-07 HU/JD 混称 | `airlines_client.py` | airline governance test |
| P0-08 重复 AOG 电话 | cross-IATA conflict quarantine | duplicate contact test |
| P0-09 联盟术语 | HO Connecting Partner override + registry | alliance regression |
| P0-10 路由掉登录 | httpOnly cookie AuthGate/API | auth tests |
| P0-11 UNVERIFIED 暴露 | API release policy + tabs fail-closed | unverified city test |
| P0-12 SLA 无主语 | city detail responsibility/disclaimer | frontend contract |
| P0-13 访问次数 | `city_usage` durable table | visit count test |
| P0-14 课件 v2 | nav removal | frontend contract |
| P0-15 导出记录分类 | governance-record publication filter | experience publication tests |
| P0-16 AI 入口 | one global + one home inline | frontend contract |

P1 完成 9 项：数据源、访问排序、城市/机场、备件位置、AI 总结入口、机型别名、相关算法、省份/地区、重复提示。

生产硬化证据：

- `reports/RAG-HALLUCINATION-PRESSURE-TEST.md`
- `reports/DATA-GOVERNANCE-REGISTRY.md`
- `reports/MINIMAX-LOCAL-DEPLOYMENT.md`
- `reports/AOG-PRODUCTION-READY.md`
