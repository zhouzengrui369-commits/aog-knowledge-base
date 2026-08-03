# AOG 航司数据治理登记册

## 结论

航司名称、联盟、IATA/ICAO、基地和 AOG 联系方式不再由前端 mock 或页面文案自行解释。生产 API 统一经过 `AirlinesClient` 治理：

1. `HU` 固定为“海南航空”，`JD` 固定为“首都航空”，禁止“海航（首都航）”一类混称；
2. `HO` 使用“星空联盟优连伙伴”术语，不再标成完整联盟成员或寰宇一家；
3. 相同电话或邮箱同时归属两个 IATA 运营人时，双方联系方式都从公共响应移除并标记 `verification_status=CONFLICT`；
4. 缺少 `verified_at` 的记录标记 `UNVERIFIED`，不得作为已核验生产联系方式；
5. 前端只展示 API 返回的治理结果，不直接读取静态联系方式。

## 生产状态枚举

| 状态 | 含义 | 公共联系方式 |
|---|---|---|
| `VERIFIED` | 有来源和核验日期，且未检测到跨航司冲突 | 可展示 |
| `UNVERIFIED` | 缺少核验日期或来源不足 | 不应作为生产依据 |
| `CONFLICT` | 电话或邮箱与其他 IATA 运营人冲突 | 自动移除，等待数据治理 |

## 联盟术语

- 吉祥航空 `HO`：Star Alliance Connecting Partner，产品中文统一为“星空联盟优连伙伴”。
- 其他联盟字段必须在季度复核时与联盟官网成员名录及航司官网交叉核验。
- 不用集团归属替代运营人身份；同一集团的 `HU` 与 `JD` 仍是两个独立 IATA 运营人。

权威参考：

- Star Alliance Connecting Partners — https://www.staralliance.com/en/connecting-partners
- Star Alliance Juneyao Airlines partner announcement — https://www.staralliance.com/en/news-article?newsArticleId=4234430

## 季度核验流程

每季度首个工作周执行：

1. 导出 `airlines.json` 的 25 个 IATA 运营人；
2. 核对 IATA/ICAO、法定中文名、官网、基地和联盟；
3. 联系方式必须有两个独立来源，至少一个为航司官方渠道；
4. 将来源、核验人、`verified_at` 写回数据登记册；
5. 运行重复电话/邮箱检测；
6. 冲突项不猜测、不复制集团热线，直接标记 `CONFLICT` 并从公共 API 移除；
7. 由业务 Owner 对新增或变化的公开 AOG desk 进行签字确认。

## 当前自动化覆盖

- IATA 身份覆盖：运行时 100% 归一；
- `HU` / `JD` 术语分离：自动测试覆盖；
- HO 联盟术语：自动测试覆盖；
- 跨航司电话冲突：自动检测并 fail-closed；
- `verified_at` 缺失：自动降级；
- 生产前双源人工核验：需要在本地部署验收阶段完成，不得由模型猜测具体 AOG 联系方式。

## 禁止项

- 禁止用客服热线冒充 AOG desk；
- 禁止因为集团相同就复用联系方式；
- 禁止用联盟历史关系推断当前联盟；
- 禁止将未经双源核验的电话、邮箱标记为 `VERIFIED`；
- 禁止为了通过测试而硬编码虚假“权威来源”。
