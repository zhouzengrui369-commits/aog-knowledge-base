# AOG Knowledge Base - 重大决策 (D-XXX)

> 决策号格式: D-XXX, 顺序累加
> 每条决策: 背景 + 选项 + 最终选择 + 影响
> 详细代码改动: git log --grep

---

## D-029 删 stub docx + PENDING check (2026-07-27)

**背景**: 7/27 PM 误读用户"项目文件夹有"为"目标文件在", 直接写 PVG/SHA stub docx 到 `AOG知识库/02_外战预案/` (read-only 数据源), 17:01 build_index 跑完把假数据吃进 aog.db + chroma + fts5 = 假数据流通到生产。

**选项**:
- 🅰️ 写 stub 到源目录占位 (PM 走捷径)
- 🅱️ stub 写到 staging 让 NJX 物理 mv (7/27 教训正解)
- 🅲️ 不写 stub, UI 标"待补" + 显式 MISSING 状态

**最终选择**: 🅲️ UI 标"待补" + 显式 MISSING 状态 (P0-5 进一步: 9 字段 + 6 状态枚举)

**影响**:
- ✅ 7/27 P0 修复关闭
- ✅ 写 memory: "read-only 数据源约束铁律" (跨项目通用)
- ✅ 写 memory: "Stub 数据污染预防 4 步"
- 📋 残余: AOG知识库/02_外战预案/S-上海浦东(待补).md 等 PENDING 状态 docx 需 NJX 物理 cp 真数据 (P1-3, P3-6)

---

## D-030 治本 city detail contacts 进 RAG (2026-07-27)

**背景**: 7/26 评发现 "Q1 召回 AOG 航材保障手册没召 city detail contacts" — RAG 只召手册不召 city。

**选项**:
- 🅰️ 5 段式 (wiki + city + city_contacts + experience + core_plan) 混合召回
- 🅱️ 单一 chunks 召回, metadata 过滤
- 🅲️ 双轨: fts5 主 + chroma fallback

**最终选择**: 🅰️ 5 段式 (P1-1)

**影响**:
- ✅ 7/26 P0 关闭
- 📋 D-043 进一步优化召数 (wiki 3 / city 8 / city_contacts 5 / exp 2 / core 1) + specificity 排序

---

## D-031 contacts 权限区分 (2026-07-27)

**背景**: 联系人 tab 直接展示 SPE@satair.com + 石培 +86 186 0086 6651 个人手机号, 无"内部/受控"标识。

**选项**:
- 🅰️ 全公开, 加免责 "本数据仅供参考"
- 🅱️ role 字段加 "公开" / "受控" / "私密" 三级, UI 显式标签
- 🅲️ 完全隐藏 contact tab, 必须登录

**最终选择**: 🅱️ (P0-6 完整实现)

**影响**:
- 7/27 评 OPEN → 本 PR P0-6 修
- 📋 Personal mobile 兜底 REDACTED 字段

---

## D-032 S-上海虹桥 抽取 bug 调查 (2026-07-27)

**背景**: NJX curl URL 字符错位导致 S-上海虹桥 提取失败。

**根因**: URL 字符错误, 不是 docx 缺

**修复**: `9e305cb` PENDING check 需 decode URL-encoded code

**影响**: ✅ 7/27 P0 关闭

---

## D-038 V29c trigram 治本 CJK 召回 (2026-07-27)

**背景**: NJX 7/27 19:55 反馈"未找到赫尔辛基预案" — db 里有 2 篇 wiki 段 + 1 篇 docx 段, 但 chat 召回 top 5 全是 斗湖/赣州/敦煌/营口/温州 (完全不相关城市)。

**根因 (3 层叠加)**:
1. FTS5 `unicode61 remove_diacritics 2 tokenchars '-_.#/'` tokenizer **对 CJK 完全不切分** — 整 db 643 个 term 全 ASCII 字母/数字/标点
2. 应用层 `_split_cjk` 拆 2-3-gram phrase 在 unicode61 索引里 **0 命中**
3. 结果: FTS5 MATCH 0 命中 → bm25 全 0 → ORDER BY 0 = unranked scan → 随机返前 5 行

**选项**:
- 🅰️ trigram (sqlite 内置, 3-char substring 匹配, 50-100MB 索引)
- 🅱️ jieba + 自建 tokenize (依赖 jieba dict, SCF /tmp 加载慢)
- 🅲️ 混合: trigram + 短 CJK LIKE fallback

**最终选择**: 🅲️ (commit 80aed9e)

**实测 7 query 回归 ✅**:
- 赫尔辛基保障预案: top 1 赫尔辛基 (bm25=-17.7)
- 北京大兴: top 1 北京大兴
- 西安/三亚/米兰/杭州 (2 char): top-3 含真实目标
- 前轮件号 3-1531: top-5 含真实目标

**影响**:
- ✅ V29c 7 query 回归全通过
- ✅ db 58.3MB (vs 30MB unicode61 1.9x), SCF 100MB 限制内
- ✅ build 时间 6.9s (vs 67s unicode61 10x 快)
- 📋 P0-3 进一步: 显式 manifest (tokenizer / build_commit / build_time / source_manifest)

---

## D-043 召回错城市治本 (2026-07-28, 待 commit)

**背景**: NJX 7/28 11:44 + 20:45 反馈"雅典/南宁 召错城市" — LIKE 召出 100+ city (N-南宁 排 38 / Y-雅典 排 212), LIMIT 16 截不到真实目标。

**根因**: 短 CJK LIKE 全表扫, "通用 AOG 词" (保障/预案/求援/故障/外站/手册) 和"city-specific 词" (南宁/雅典) 同等权重。

**修法**:
- 通用 AOG 词黑名单 (`_GENERIC_AOG_WORDS_LIKE`): 保障/预案/求援/故障/外站/手册/应急/处理/需求/求地/地点/控制/活门/防冰/大翼/机号 等
- 召数扩大: wiki 5→3, city 5→8, city_contacts 3→5
- city 主文档 boost: 1.5x → 2.0x
- 合并去重限制: 8 → 12
- specificity 排序: source_id 含 city-specific keyword > content 含 > 通用

**影响**:
- 🔄 待 commit (本 PR 一并)
- 📋 P0-3 进一步: 7 query 回归必须包含雅典/南宁/赫尔辛基

---

## D-044 7/29 P0-1 ~ P0-7 (本 PR 决策, 待 commit)

**D-044-A P0-2 API base 规范**

**选项**:
- 🅰️ base 不带尾 /api, path /api/...
- 🅱️ base 带 /api, path 不重复

**最终选择**: 🅰️ (frontend .env.local 改 `https://...tcloudbase.com`, path 保持 `/api/cities`)

**影响**: 消除公网 400 double-prefix, 7/27 评 P0-2 关闭

---

**D-044-B P0-3 RAG 维度 manifest**

**方案**: export_fts5.py 写 build_manifest 表 (tokenizer, build_commit, build_time, source_manifest_hash, chunk_count, db_size_bytes), fts5_client 启动时校验, 不一致 fail-closed

**影响**: 7/27 评 P0-2 (RAG 维度) 完整关闭, chroma 集合 dim=1024 误用问题彻底澄清 (V28b 后 chroma 已废用)

---

**D-044-C P0-4 mock 隔离**

**方案**: config 加 `ALLOW_MOCK: bool` 字段, dev 默认 true, SCF 默认 false; backend 启动时校验, ALLOW_MOCK=false + MINIMAX_API_KEY 空 → fail-closed 503; frontend `.env` 加 `NEXT_PUBLIC_ALLOW_MOCK` 同步, production false → 静默 mock 改显式 "Provider 未配置" banner

**影响**: 7/27 评 P0 残余关闭, mock 不再静默进 production

---

**D-044-D P0-5 数据可信度 9 字段合同**

**9 字段**:
1. `source_document` - 源文件路径 (e.g. "AOG知识库/02_外战预案/B-北京大兴.docx")
2. `source_location` - 源在仓库的位置 (e.g. "filesystem:02_外战预案")
3. `source_version` - 源版本 (e.g. "2026-07-15 v1.0")
4. `updated_at` - 最后更新时间 (ISO8601)
5. `reviewed_at` - 最后审核时间 (ISO8601)
6. `reviewed_by` - 审核人 (e.g. "NJX" / "Mavis PM")
7. `review_status` - 审核状态 (VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED)
8. `confidence` - 置信度 (0.0-1.0)
9. `environment` - 适用环境 (dev/staging/production/all)
10. `pii_classification` - PII 等级 (none/internal/confidential/restricted)

**6 状态枚举**:
- `VERIFIED` - 已人工或交叉验证
- `UNVERIFIED` - 来源存在但未审核
- `STALE` - 来源过期 (>30 天)
- `MISSING` - 来源缺失, 显示"暂无已核验数据"
- `FIXTURE` - 测试 fixture, UI 显著标识
- `REDACTED` - 已脱敏, 仅显示 role 不显示具体值

**影响**:
- City model + Experience model 加 9 字段
- DB migration 加 9 列
- pipeline 写入 (从 docx YAML frontmatter 读)
- UI city detail 显示: 来源/最后更新/审核人/置信度/PII
- 7/27 评 P1-1 (数据来源) 关闭
- 上海浦东/虹桥 MISSING 状态不再 404, 显式"待补"

---

**D-044-E P0-6 Contact role_class + REDACTED**

**方案**: Contact 加 `role_class: Literal["public", "controlled", "private"]` + `redacted: bool`, 缺真值时 `redacted=true`, 私有 `role_class=private` 默认 redacted

**3 级**:
- `public` - 公开 (单位电话/邮箱/库房地址)
- `controlled` - 受控 (商业联系人 Satair SPE)
- `private` - 私密 (个人手机号, 需登录)

**影响**:
- 7/27 评 P1-11 (个人手机号裸露) 关闭
- UI: public 直展示, controlled 加"受控"标签, private 默认不展示 (登录后可)
- frontend bundle grep `1[3-9]\d{9}` = 0 (验证)

---

**D-044-F P0-7 staging 真实验收**

**前提**:
- NJX 充值 CloudBase 账户 (`njx-copilot-d6gs7642f8fa17122`)
- 本 PR merge main
- NJX 物理 OAuth + `tcb fn deploy`
- NJX 上传 frontend/out 到 CloudBase 静态托管

**10 项旅程验收 (待 P0-7 后执行)**:
1. 首页理解产品用途
2. 搜索北京大兴
3. 查看上海浦东 (MISSING 状态显式)
4. 查看样板外站
5. 提出 AOG 问题 (依赖真资料)
6. 打开答案来源 (UI 显示 source_document)
7. 测试 Provider 不可用 (显式 "Provider 未配置" banner)
8. 测试无数据城市 (MISSING 状态)
9. 测试过期数据 (STALE 状态)
10. 测试未授权用户访问 controlled contact (REDACTED 兜底)

---
