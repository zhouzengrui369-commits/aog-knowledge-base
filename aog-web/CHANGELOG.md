# AOG 修改日志 (CHANGELOG)

> **目的**: 简要记录每次重要修改、日期、内容、原因、影响。
> **格式**: 按时间倒序（新→旧），按版本号组织。
> **维护**: 每完成一个功能 / 阶段必更新。
> **最后更新**: 2026-07-26 by Mavis (PM)

---

## [Unreleased]

### 🔄 V29 计划 (待 NJX 拍板)

- V29 UI polish（颜色统一 / hub vs 普通视觉差异 / 选中态 label 样式）
- 视口外 city dot 性能优化
- supercluster bubble 颜色统一

---

## [V28b] - 2026-07-24 · Map 治本收口

**Commit**: `f86ab42` (HEAD)
**分支**: `integration/sprint-abc`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - supercluster radius `50` → `80`

### 原因

V28 改完 NJX 反馈"5.0 还是有点挤"。zoom 5 视口内 156 蓝点 + 28 数字 bubble，单点 label 仍偏多。

### 影响

- zoom 5: 156 蓝 → **90 蓝** (-42%)，28 bubble → **53 bubble** (+89%)
- zoom 6: 188 → 169 蓝，14 → 23 bubble
- zoom 7: 193 → 189 蓝，12 → 14 bubble
- zoom 8: 218 + 0 全散开（一致）
- 总可视元素 -22%，NJX 验证"宽松"

---

## [V28] - 2026-07-24 · Supercluster 数字聚合 218 AOG

**Commit**: `8333999`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - 3 处重构（30 行改）

### 原因

V27 改 218 label 全部常驻，但 zoom 5 中国区 100+ 城市挤一起，label 重叠严重。NJX 反馈"重叠的航站应该显示为数字"。

### 影响

- V19 旧 15 hub cluster (radius 80, maxZoom 4) 删
- V28 新 218 城市 supercluster (radius 50 → V28b 80, maxZoom 7, minPoints 2)
- 渲染逻辑：cluster → 数字 bubble / single → CityDot + label
- visibleCities 仅 zoom > 7 走（zoom 8 全散开）
- 跟 V20 6,072 supercluster 风格一致

---

## [V27b] - 2026-07-24 · 218 Label 全部蓝色

**Commit**: `7d7dd6e`
**作者**: Mavis (PM)

### 改动

1. `frontend/app/globals.css` - `.city-label` 灰→蓝
   - `color: #6b7280` → `#1e40af`
   - `font-size: 12px` → `13px`
   - `font-weight: 500` → `600`

### 原因

V27 改 218 label 全部常驻，但 CSS 区分 hub-label（蓝）+ city-label（灰）。NJX 反馈"218 个航站都是蓝色标签"。

### 影响

- 203 city-label: rgb(30, 64, 175) = #1e40af 蓝
- 15 hub-label: 跟 city-label 视觉一致
- 总 218 label 全部统一蓝色

---

## [V27] - 2026-07-24 · 218 AOG 城市常驻 Label

**Commit**: `c79dab1`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - showLabel 计算去 isHub 限制
   - `showLabel = inLabelSet || (isHub && zoom >= 5) || ...` 
   - → `showLabel = inLabelSet || zoom >= 5 || ...`

### 原因

NJX 反馈"详细视图下，有的有标签，有的没有标签，有保障预案的应该都显示标签"。

### 影响

- zoom 5/6/7: 218 label (15 hub + 203 city) 全部常驻
- zoom 4: 2 label (tier 2 少而精保留)
- CSS 已支持 city-label (12px 灰) + hub-label (14px 蓝)

---

## [V26] - 2026-07-24 · 治本 218 城市看不见 (颜色分层)

**Commit**: `acb5239`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - 4 处改

| 项 | 改前 | 改后 |
|---|---|---|
| `ZOOM_DEFAULT` | `4` | `5` |
| CityDot `r` | `isHub ? 5 : 3` | `isHub ? 6 : 4` |
| CityDot `fill` (普通) | `#4b5563` | `#2563eb` |
| CityDot `fillOpacity` (普通) | `0.95` | `1` |
| CityDot `weight` (普通) | `1.5` | `2` |

### 原因

V18-V25 一直在调灰色深度（#9ca3af → #4b5563 + fillOpacity 0.65→0.95 + 白边 1.5px）都没用。NJX 一句话"有预案的站点都应有标签，没有预案的航站才灰色，是不是理解偏差了"直接纠偏：**重要的彩色，次要的灰**。

### 影响

- 6,072 没预案 = 灰小点 #9ca3af r=1.5（背景）
- 218 有预案 = 彩色蓝 #2563eb r=4-6（主视觉）
- 默认进入就 tier 3 全显示 218（治本 V25 默认 22 站）
- 实测：默认 zoom 5 → 218 蓝 + 5915 灰

---

## [V25] - 2026-07-23 · 航站 Tab 隐藏航司 + Panel 折叠

**Commit**: `a600ab9`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map-leaflet.tsx` - 4 处
2. `frontend/components/alphabet-nav.tsx` - 航站/航司 tab 切换

### 原因

NJX 4 条反馈：(1) 航站 tab 隐藏航司 (2) 全球 panel 默认折叠 (3) 218 城市不全可见 (4) 重庆 "2" 含义不清。

### 关键 root cause 发现

V18-V25 一直以为 218 城市 "render 数量不够"，但实测 218 dot 都渲染了。真正问题是 fillOpacity 0.65 跟 OSM 灰路网融一体看不见。改 #4b5563 + 0.95 + 1.5px 白边治本。

---

## [V18-V24] - 2026-07-21~23 · 地图 UI 演进

| 版本 | 内容 |
|---|---|
| V24 | 航司 tab 地图切换（保留 hub 城市 + 顶部高亮当前航司）|
| V23 | N=1 显示实际内容（推翻 V22 数字 "1" 冗余）|
| V22 | 数字徽章 + flyTo + 右侧 panel（推翻 V21 tooltip 堆叠）|
| V21 | UI 简化（字母 sidebar + tooltip 限 5 + panel top 6）|
| V20 | OpenFlights 6,072 全球机场 + 颜色区分 + 缩略图数字 |
| V19 | 完整 218 城市 MOCK（国内 144 + 国际 74）|
| V18 | 本地验证全流程（25 航司 MOCK + DISABLE_AUTH + leaflet SSR fix）|
| V17 | 地图加航司 layer（紫环）|
| V16 | react-leaflet 嵌入主图（替换 react-simple-maps）|

---

## [V15.x] - 2026-07-20 · 字母导航 + IATA 修复

| 版本 | 内容 |
|---|---|
| V15.3 | backend `isalpha()` → `isalnum()`（接受数字开头 IATA）|
| V15.2 | dev backend 返空数组时 fallback MOCK |
| V15.1 | 字母导航改为 tab 切换（推翻 V15 2 个并列）|
| V15 | 字母导航左右并排 3 列（已废）|

---

## [V14] - 2026-07-17 · 地图 Click 直跳 + Client Render 防御

**Commit**: `7d9ac13`
**作者**: Mavis (PM)

### 改动

1. `frontend/components/world-map.tsx` - 4 处 `.toLowerCase()` 删除
2. `frontend/components/city-detail-client.tsx` - render const try/catch wrap
3. `frontend/components/city-tabs.tsx` - 5 pane `?.` optional chaining
4. `frontend/lib/utils.ts` - `fmtDate` try/catch wrap

### 原因

NJX 反馈"打开失败"——地图 click 走 lowercase URL → 404，法兰克福 client-side exception。

### Root cause

1. `world-map.tsx:813/822/1081/1219` 4 处强制 `code.toLowerCase()`
2. `city-detail-client.tsx` render const 没 try/catch wrap
3. SCF 真实 API `city.contacts[0].phone` 是 `string[]` 不是 `string`（mockup 是 string）

---

## [V13] - 2026-07-17 · 真实中文 City File 名

**Commit**: `3584a0a`
**作者**: Mavis (PM)

### 改动

1. `frontend/postbuild.sh` 新增 - rename URL 编码 file → 真实中文 file

### 原因

Next.js `output: export` 把中文 URL 编码（如 `A-%E9%98%BF%E6%A0%BC.html`），CloudBase 静态托管找不到 raw 中文 file（虽然文件存在但 URL 不匹配）。

---

## [Sprint A/B/C] - 2026-07-15 · 三大 Sprint

| Sprint | 内容 | Commit |
|---|---|---|
| A | 密码 + JWT 24h + AuthGate | `ac6d8f4` |
| B | react-leaflet 调研 + prototype | `2047944` (未 merge) |
| C | 25 航司数据 + /api/airlines + UI tab | `58637a3` |

---

## [V8-V12] - 2026-07-13~14 · 早期 UI 演进

| 版本 | 内容 |
|---|---|
| V12.2 | 智能 404 client 端 useEffect |
| V12.1 | 试图用 Netlify `_redirects`（被 CloudBase 静态托管不支持，改 client 智能 404）|
| V12 | 城市详情页 + 智能 404 + 部署 + 备案准备 |
| V11 | hub label density + 删 IATA + 中文名 + 中文 city code 兼容 |
| V10 | 城市详情 client fetch + SCF + CSS |
| V9 | 区域级 (T2) 缩略图 panel |
| V8 | dot 半径 constant 像素 |

---

## [V1-V7] - 2026-07-08~12 · MVP 初版

MVP 部署 → Wave 1-3 → UI v1-v7 全部完成（历史）。详见 git log `7d9ac13` 之前。

---

## 📊 统计

- **总 commit**: 49 (filter-repo 重写后) + 16 (V11-V28b) = 65
- **总文件**: 1290
- **总代码行**: ~50,000
- **MVP 截止**: 2026-07-23（已延期至 V28b 治本完成）
- **下一里程碑**: 公网 SCF 重新部署

---

**新 AI 接手步骤**：
1. 读 STATUS.md (当前状态)
2. 读本文件（最近修改历史）
3. 看 git log 找具体 commit
4. 跑 `pnpm dev --port 3004` 验证当前效果

---

**最后更新**: 2026-07-26 by Mavis
