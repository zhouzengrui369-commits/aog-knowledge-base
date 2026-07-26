# AOG 待办事项 (TODO)

> **目的**: 清晰标注待办事项，区分高/中/低优先级，新 AI 接手可立刻知道做什么。
> **维护**: 每日 / 阶段结束时更新。
> **最后更新**: 2026-07-26 by Mavis (PM)

---

## 🔴 高优先级 (High Priority) - NJX 拍板后立刻做

### 1. 公网 SCF 重新部署（含 V13-V28b endpoint）

- **背景**: 公网 SCF `76cca2c` (Jul 17) 仍跑老版本，缺以下 endpoint：
  - `/api/airlines`（V17 航司 layer）
  - `/api/auth/login`（Sprint A 密码登录）
  - `/api/cities` 含 V19 全 218 城市 lat/lon（老版本 lat=0, lon=0）
  - V15.3 isalnum 数字开头 IATA 修复
- **步骤**:
  1. 拉最新 `aog-web/functions/aog-api/aog_web/` 到 `functions/` 目录
  2. `tcb fn deploy aog-api` 重新部署 SCF
  3. 等 30s 冷启动，curl 验证 `/api/health` 200
  4. 验证 `/api/cities` 返回 223 城市含 lat/lon
  5. 验证 `/api/airlines` 返回 25 航司
  6. 验证 `/api/auth/login` POST 返回 JWT
- **风险**: CloudBase CDN 缓存可能滞后 10 分钟
- **预计时间**: 30 分钟
- **NJX 拍板**: 战略决策（外部承诺），需 NJX 确认部署窗口

### 2. 合并 integration/sprint-abc → main + 部署前端

- **背景**: V25-V28b 16 个新 commit 在 integration/sprint-abc 分支，公网前端仍是 Jul 17 老版本
- **步骤**:
  1. `git checkout main`
  2. `git merge integration/sprint-abc --no-ff`
  3. `git push origin main`
  4. 前端 build: `cd aog-web/frontend && pnpm build`
  5. 静态托管 deploy: `tcb hosting deploy aog-web/frontend/out -e njx-copilot-d6gs7642f8fa17122`
  6. 等 10 分钟 CDN 缓存
- **风险**: GitHub merge 冲突可能（V13-V28b 主要改 frontend/，无 backend/ 冲突）
- **预计时间**: 15 分钟
- **NJX 拍板**: 战略决策（对外可见），需 NJX 确认

---

## 🟡 中优先级 (Medium Priority) - 下一阶段做

### 3. Vite error overlay 治本

- **背景**: Next.js 15 + React 19 strict mode + leaflet 内部 removeChild 已知问题，仅 dev
- **当前 workaround**: dev 死掉时 `nohup pnpm dev --port 3004 > /tmp/aog_v28b_dev.log 2>&1 &` 重启 15s 恢复
- **治本方案**: 升级 react-leaflet v5（内部用 React 18 createRoot 解决 strict mode）
- **风险**: 工作量大，可能引入新 bug；需先在 worktree 验证
- **预计时间**: 1-2 天
- **NJX 拍板**: 否（PM 自主）

### 4. AOG 微信小程序备案

- **背景**: 域名 aog.knowledge.com 待 ICP 备案，微信小程序类目选择
- **步骤**:
  1. 登录微信公众平台 → 小程序管理
  2. 主体选择（个人 vs 企业，NJX 是个人 OPC）
  3. 类目选择（工具 → AOG 紧急救援类？）
  4. ICP 备案：登录 aog.knowledge.com 注册商 → 微信扫码 + 填 3 字段
  5. 备案号填回微信公众平台
- **风险**: 个人主体类目受限，可能需要企业主体
- **预计时间**: 1-2 周
- **NJX 拍板**: 战略决策（外部承诺）

### 5. V29 UI polish

- **背景**: V28b 治本后还有优化空间
- **可优化项**:
  - supercluster bubble 颜色（紫色 vs 蓝色统一）
  - hub vs 普通城市视觉差异（r=6 vs r=4 微差，可加大）
  - 选中态 label 样式
  - hover letter 同步高亮动画
- **风险**: 改 CSS 可能影响既有视觉
- **预计时间**: 半天
- **NJX 拍板**: 否（PM 自主）

---

## 🟢 低优先级 (Low Priority) - V30+ 阶段

### 6. V30+ 性能优化

- 视口外 city dot 不渲染（leaflet 内置优化）
- label collision detection（自动隐藏重叠 label）
- 218 城市 GeoJSON 索引（替代 JSON 数组）
- 6,072 全球机场按需加载（按视口 bbox）

### 7. OpenClaw 知识库整理自动化（项目外）

- 跟 AOG 项目无关，跨项目
- 之前有 knowledge-vault-curator cron 整理 Obsidian vault
- 已 disabled 几个（详见 memory）
- 后续: 用 AOG 项目的 FTS5 + RAG 知识库给 OpenClaw 提供长期记忆

### 8. SCF FTS5 索引优化

- 当前 27MB SQLite FTS5 索引
- 5,000+ 知识片段
- 优化: trigram + BM25 混合查询
- 跟 AI chat 性能相关

---

## ✅ 已完成（V28b 之前）

详细见 [STATUS.md](./STATUS.md) 的"已完成"表 + [CHANGELOG.md](./CHANGELOG.md)。

最近 8 个版本（V21-V28b）全部关于地图治本（V18-V25 一直在调灰色深度是治标方向错，V26 纠正为"重要彩色 + 次要灰"）。

---

## 📝 待 NJX 拍板（PM 暂时不行动）

| # | 决策点 | 详情 |
|---|---|---|
| 1 | 公网 SCF 重新部署窗口 | NJX 决定何时部署（外部承诺） |
| 2 | 微信小程序主体 | 个人 vs 企业（外部承诺 + 资源） |
| 3 | 域名 aog.knowledge.com 备案 | 战略决策（外部承诺） |
| 4 | V29 优化方向 | 颜色统一 / 视觉差异 / 选中态 等 |

---

**新 AI 接手步骤**：
1. 读 STATUS.md (当前阶段)
2. 看本文件高优先级（红色）→ 跟 NJX 确认是否执行
3. 看中优先级（黄色）→ 跟 NJX 确认下一阶段是否做
4. 看低优先级（绿色）→ PM 自主决定时机
5. 任何决策写入 DECISIONS.md

---

**最后更新**: 2026-07-26 by Mavis
