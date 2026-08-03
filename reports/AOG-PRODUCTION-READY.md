# AOG Knowledge Base — Production Readiness Ledger

## Verdict

```text
CODE_SCOPE: COMPLETE_PENDING_CI
LOCAL_RUNTIME_ACCEPTANCE: PENDING_MINIMAX_CODE
CLOUDBASE_STAGING: BLOCKED_OWNER_ENVIRONMENT
PRODUCTION_RELEASE: NOT_YET_AUTHORIZED
```

本报告不把代码完成等同于真实 AOG 上线。只有 GitHub CI、MiniMax Code 本地真机、20 题真实模型压测、CloudBase staging 和 NJX 走查全部通过后，才能由 Owner 签署“可以上线”。

## P0 关闭矩阵

| P0 | 代码处置 | 状态 |
|---|---|---|
| 01 经验空壳与 dev 占位 | `has_content` 持久门、API 过滤、详情 404、正文解析 | CODE PASS |
| 02 404 硬编码 | 城市与经验数量从 API 动态读取 | CODE PASS |
| 03 数字不一致 | 新增 `/api/stats`，首页/404/经验页使用单一 SQLite 真值 | CODE PASS |
| 04 CoT 暴露 | 生产前端丢弃 `<think>`，仅显式 debug 环境可保留调试信息 | CODE PASS |
| 05 Markdown 与截断 | 结构化 section 渲染、GFM 表格 fallback、私有标记清理、截断告警与重试 | CODE PASS |
| 06 联系人重复 | 后端与前端双层稳定去重，未知权限 fail-closed | CODE PASS |
| 07 HU/JD 术语 | IATA 身份覆盖，海南航空与首都航空分离 | CODE PASS |
| 08 航司电话冲突 | 跨 IATA 重复电话/邮箱自动标记 `CONFLICT` 并移除 | CODE PASS |
| 09 联盟过期 | HO 统一为“星空联盟优连伙伴”；季度复核合同落库 | CODE PASS |
| 10 路由掉登录 | httpOnly Cookie、credentialed verify、网络失败不销毁登录态 | CODE PASS |
| 11 UNVERIFIED 数据 | API 在非 VERIFIED 状态隐藏 contacts/fleet/parts/warehouse/logistics/content | CODE PASS |
| 12 SLA 无主语 | 明确内部处置责任方、目标性质与非对外 SLA 免责声明 | CODE PASS |
| 13 访问次数 | `city_usage` 原子累加、列表回读、首次访问文案 | CODE PASS |
| 14 课件 v2 占位 | 从主导航删除 | CODE PASS |
| 15 经验分类错位 | 导出/同步/治理记录强制 `has_content=0`，不进入公共案例 | CODE PASS |
| 16 AI 入口散落 | 保留一个全局浮窗与一个首页内联入口 | CODE PASS |

## P1 完成矩阵

已完成 9/12：

- P1-18 全球机场底图数据源说明；
- P1-19 访问次数数据库累计与排序；
- P1-20 城市名与机场名分离；
- P1-21 备件位置分为本站库存 / 协议求援 / 待确认；
- P1-22 “用 AI 总结”并入统一 AI 助手；
- P1-23 B787 / 787 / 梦想客机等机型别名；
- P1-24 相关航站算法及“不代表互援协议”标签；
- P1-25 省份/地区字段展示；
- P1-28 重复提示和重复入口清理。

待后续体验迭代：P1-17 字母空态、P1-26 全站视觉 token 深度统一、P1-27 PEK/PKX 跨页专项关系展示。

## 生产硬化

### RAG

- 20 个对抗问题及严格 `<5%` 评分器已入库；
- CI 验证用例数量、边界规则与评分逻辑；
- 真实 MiniMax 运行必须本地或 staging 取得 `0/20` 失败。

### PII

沿用并保留 D-052 至 D-056 的真实数据安全链：联系人自由文本、电话规范化、跨城市权限冲突、provenance-aware Gate、wiki release snapshot 和失败日志指纹化。

### 航司数据治理

运行时会隔离跨 IATA 冲突联系方式；季度复核流程见 `reports/DATA-GOVERNANCE-REGISTRY.md`。模型不得猜测 AOG desk。

## CI

本次新增 `production-readiness` workflow，包含：

- 后端生产策略测试；
- 前端 typecheck、lint、Vitest 和 production build；
- 20 题 RAG 合同；
- 用户可见占位符、密钥和交付文档检查。

最终 CI run ID 和 merge SHA 在总 PR 全绿、合并后回填。

## 外部 Gate

下列事项无法在 GitHub 远程代码环境中伪造：

1. NJX 本机真实数据和浏览器截图；
2. 真实 MiniMax Key 下的 20 题压测；
3. CloudBase 独立 staging 环境、COS、域名与灰度；
4. 一名真实 AOG 工程师完整流程走查；
5. NJX 最终签字。

执行合同见 `reports/MINIMAX-LOCAL-DEPLOYMENT.md`。

## Owner Sign-off

```text
NJX_PRODUCTION_SIGNOFF=PENDING
SIGNED_AT=
STAGING_URL=
FINAL_MAIN_SHA=
```
