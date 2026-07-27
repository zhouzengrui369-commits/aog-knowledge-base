# AOG 项目状态 (Project Status)

> **目的**: 让任何新 AI 只看 README + STATUS + TODO + docs 目录就能 10 分钟内理解项目并继续开发。
> **维护**: 每完成一个功能 / 阶段必更新本文件。
> **最后更新**: 2026-07-26 by Mavis (PM)

---

## 🎯 当前阶段

**Phase 1 · 地图治本冲刺 (Wave UI v25→v28b 完成)**

- **里程碑**: 218 AOG 城市可视性 + 颜色分层 + 标签 + 数字聚合 全部治本完成
- **下一里程碑**: 公网 SCF 重新部署（含 /api/airlines + /api/auth/login）+ 微信小程序备案

---

## 📍 当前目标

让 NJX（OPC 独立创业）能够：

1. **本地浏览器硬刷 http://localhost:3004/** → 看到 V28b 治本后的地图（218 蓝点 + 数字 bubble + 6,072 灰点）
2. **点击紫色数字 bubble** → 自动 flyTo + zoom in 展开
3. **公网部署更新** → 含 V13-V28b 全部新功能（密码登录 + 航司 tab + 地图治本）

---

## ✅ 已完成 (Recent Shipped)

| 版本 | 日期 | 内容 |
|---|---|---|
| **V28b** | 2026-07-24 | supercluster radius 50→80 (治本 "5.0 还是有点挤") |
| **V28** | 2026-07-24 | supercluster 数字聚合 218 AOG (zoom 5-7 治本标签重叠) |
| **V27b** | 2026-07-24 | city-label 灰→蓝 (218 label 全部蓝色) |
| **V27** | 2026-07-24 | 详细视图 zoom≥5 全部 218 城市常驻 label |
| **V26** | 2026-07-24 | 治本 218 城市看不见 (默认 zoom 5 + 改 hub 蓝 #2563eb + r 加大) |
| V25 | 2026-07-23 | 航站 tab 隐藏航司 + 全球 panel 折叠 + 218 城市全可见 |
| V24 | 2026-07-23 | 航司 tab 地图切换 (NJX 拍 🅱️) |
| V23 | 2026-07-23 | N=1 显示实际内容 (推翻 V22 数字 "1") |
| V22 | 2026-07-23 | 数字徽章 + flyTo + 右侧 panel (NJX 拍 🅱️) |
| V21 | 2026-07-23 | UI 简化 (字母 sidebar + tooltip 限 5 + panel top 6) |
| V20 | 2026-07-22 | OpenFlights 6,072 全球机场 + 颜色区分 |
| V19 | 2026-07-22 | 完整 218 城市 MOCK (国内 144 + 国际 74) |
| V18 | 2026-07-22 | 本地验证全流程 (25 航司 MOCK + DISABLE_AUTH) |
| V17 | 2026-07-21 | 地图加航司 layer (紫环) |
| V16 | 2026-07-21 | react-leaflet 嵌入主图 (替换 react-simple-maps) |
| V15.3 | 2026-07-20 | backend 接受数字开头 IATA (3U/8L/9C/9D) |
| V15.2 | 2026-07-20 | dev backend 返空数组时 fallback MOCK |
| V15.1 | 2026-07-20 | 字母导航改为 tab 切换 (推翻 V15 2 个并列) |
| V15 | 2026-07-20 | 字母导航左右并排 3 列 (已废) |
| V14 | 2026-07-17 | 地图 click 直跳 uppercase URL + client render 防御性 |
| V13 | 2026-07-17 | postbuild rename URL-encoded city files to Chinese names |
| Sprint A | 2026-07-15 | 密码 + JWT 24h + AuthGate |
| Sprint B | 2026-07-15 | react-leaflet 调研 + prototype |
| Sprint C | 2026-07-15 | 25 航司数据 + /api/airlines + UI tab |
| V11 | 2026-07-14 | hub label density + 中文 city code 兼容 |
| V8-V12 | 2026-07-13~14 | 城市详情 / 智能 404 / UI polish |

---

## 🔄 正在进行 (In Progress)

无。当前 V28b 治本完成，等 NJX 拍板下一步。

---

## ⏭️ 下一步 (Next Steps)

### 🔴 高优先级（NJX 拍板后可立刻做）

1. **公网 SCF 重新部署**（含 V13-V28b 全部新功能）
   - 公网 SCF `76cca2c` (Jul 17) 仍跑老版本，缺 `/api/airlines` + `/api/auth/login`
   - 需拉最新 backend code + 重新部署 SCF 函数
   - 风险: CloudBase 静态托管 CDN 缓存可能滞后（之前用 tcb CLI 3.6.2 无 invalidate/purge/refresh）

2. **合并 integration/sprint-abc → main + 部署前端**
   - V25-V28b 16 个新 commit 在 integration/sprint-abc 分支
   - 公网前端仍是 Jul 17 老版本
   - 风险: GitHub push SSL 偶发超时（已确认 8333999 / 7d7dd6e / c79dab1 push 成功）

### 🟡 中优先级（NJX 拍板后做）

3. **Vite error overlay 治本**（升级 react-leaflet v5）
   - 当前 workaround: dev 死掉时 `nohup pnpm dev --port 3004 > /tmp/aog_v28b_dev.log 2>&1 &` 重启
   - 治本: 升级 react-leaflet v5（内部用 React 18 createRoot 解决 strict mode）
   - 风险: 工作量大，可能引入新 bug

4. **AOG 微信小程序备案**
   - 域名 aog.knowledge.com 待 ICP 备案
   - 微信小程序类目选择 + 主体选择（个人 vs 企业）
   - 风险: NJX 0 CloudBase / 备案经验，PM 全权负责

### 🟢 低优先级（V29+ 阶段）

5. **OpenClaw 知识库整理自动化**（项目外）
6. **V29 UI polish**: supercluster bubble 颜色 / hub vs 普通视觉差异
7. **V30+ 性能优化**: 视口外 city dot 不渲染（leaflet 内置优化）

---

## ⚠️ 当前风险 (Active Risks)

| 风险 | 等级 | 详情 | 缓解 |
|---|---|---|---|
| **🔴 P0 事故 (D-029)** | **高** | **PM 7/26 16:45 误写 stub docx 到 read-only AOG知识库/，build_index 吃进假数据** | **7/27 08:19 mavis-trash stub + UI PENDING_CITY_CODES 标"待补" + DECISIONS D-029 + rebuild index 225→223 城市** |
| 公网 SCF InsufficientBalance | 🔴 高 | NJX 续费日 2026-07-24 23:59:59 已过，公网后端 + 前端全挂 | NJX 续费 → PM 重 deploy；本地 dev 优先走通 P0/P1 |
| 公网 SCF 老版本 | 🟡 中 | `76cca2c` (Jul 17) 缺 V15-V28b endpoint | 拉最新 backend code + 重新部署 |
| GitHub push SSL 偶发超时 | 🟡 中 | 之前 8333999 / 7d7dd6e / c79dab1 push 失败 1-3 次才成功 | sleep 30-90s 重试 |
| Vite error overlay (dev) | 🟡 中 | Next.js 15 + React 19 + leaflet 已知问题，dev only | 重启 dev 15s 恢复；production OK |
| CloudBase 静态托管 CDN 缓存 | 🟡 中 | tcb CLI 3.6.2 无 invalidate/purge/refresh | 等 10 分钟自然过期或文件名加 hash |
| macOS TCC EPERM (LaunchAgent) | 🟢 低 | 当前不用 LaunchAgent，无影响 | 1 天 MVP 别碰 LaunchAgent + 写盘 |
| worker lost 概率 | 🟢 低 | bg_xxx status=lost，需要 PM 手动接管收口 | 任务拆小，重要 commit 自己来 |

---

## 📦 最近一次重要修改

### 最近代码 (V28b)
- **Commit**: `f86ab42`
- **分支**: `integration/sprint-abc` (待 merge → main)
- **标题**: V28b fix(map): supercluster radius 50→80 (治本 "5.0 还是有点挤")
- **内容**: 1 行改 (`world-map-leaflet.tsx` supercluster radius 50→80)
- **效果**: zoom 5 单点 label 156→90 (-42%)，数字 bubble 28→53 (+89%)，拥挤治本

### 最近代码 (P0 修复 D-029, 进行中)
- **Commit**: (pending, rebuild index 跑中)
- **分支**: `integration/sprint-abc`
- **标题**: fix(P0): 删 stub docx + UI S-上海浦东/虹桥 标"待补" (D-029 事故)
- **内容**: mavis-trash S-上海浦东/虹桥.docx + city-detail-client.tsx PENDING_CITY_CODES set + DECISIONS.md D-029
- **效果**: 225→223 城市, S-上海浦东/虹桥 入口"预案待补"红字提示, 等 NJX 补真 docx

### 最近文档 (本批基线 5 文档)
- **Commit**: `da8562c` (HEAD)
- **标题**: docs: 建项目基线 5 文档 (STATUS / TODO / ARCHITECTURE / CHANGELOG / DECISIONS)
- **内容**: 5 个新 md 文件, 1236 行, 含 V13-V28b 全部状态快照 + 28 条决策 + 架构说明
- **意义**: 任何新 AI 接手 10 分钟内能继续开发

### Push 状态
- ✓ GitHub `zhouzengrui369-commits/aog-knowledge-base` integration/sprint-abc
- 全部 5 文档已 push 成功 (commit `da8562c`)

---

## 🔗 关键链接 (Important Links)

- **GitHub**: https://github.com/zhouzengrui369-commits/aog-knowledge-base
- **公网前端 (老)**: https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com
- **公网 API (老)**: https://njx-copilot-d6gs7642f8fa17122.service.tcloudbase.com/api
- **本地前端**: http://localhost:3004/ (dev 跑, V28b 治本)
- **本地后端**: http://localhost:8000/ (uvicorn, DISABLE_AUTH=1)
- **本地 swagger**: http://localhost:8000/docs

---

## 📂 文档索引 (Documentation Index)

| 文档 | 用途 | 维护频率 |
|---|---|---|
| [README.md](./README.md) | 项目入口 + 部署链接 | 大版本变更 |
| [STATUS.md](./STATUS.md) | **本文件** - 当前状态快照 | 每功能/阶段必更新 |
| [TODO.md](./TODO.md) | 待办事项（高/中/低） | 每日 |
| [CHANGELOG.md](./CHANGELOG.md) | 每次重要修改 | 每功能 |
| [DECISIONS.md](./DECISIONS.md) | 重大决策背景 + 选项 + 原因 | 战略决策时 |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | 系统架构 + 关键设计 | 架构变更时 |
| [DEPLOY_CLOUDBASE.md](./DEPLOY_CLOUDBASE.md) | CloudBase 部署 SOP | 部署变更时 |

---

**新 AI 接手步骤**：
1. 读 README.md (项目入口)
2. 读 STATUS.md (本文件, 当前状态)
3. 读 TODO.md (待办事项 + 优先级)
4. 读 docs/ARCHITECTURE.md (架构 + 关键设计)
5. 读 CHANGELOG.md (最近修改历史)
6. 读 DECISIONS.md (重大决策，避免重复讨论)
7. 跑 `pnpm dev --port 3004` + 打开 http://localhost:3004/
8. 读代码: `frontend/components/world-map-leaflet.tsx` (核心 UI)
