# AOG 重大决策记录 (DECISIONS)

> **目的**: 记录重大决策的背景、选项、最终选择、影响，避免以后重复讨论。
> **格式**: 按时间倒序，每条决策独立编号。
> **维护**: 战略决策时更新。
> **最后更新**: 2026-07-26 by Mavis (PM)

---

## D-028 · 地图 218 城市颜色分层 (V26 治本)

**日期**: 2026-07-24
**决策者**: NJX 拍板
**背景**:
- V18-V25 一直在调灰色深度（#9ca3af → #4b5563 + fillOpacity 0.65→0.95 + 白边 1.5px）治标 8 个版本
- 218 AOG 城市点还是融 OSM 灰路网看不见
- NJX 一句话"有预案的站点都应该有标签，没有预案的航站才灰色，是不是理解偏差了"直接纠偏

**选项**:
- 🅰️ 继续调灰色深度（治标，永远治不本）
- 🅱️ 改默认 zoom 5 + 加大字号（治一半）
- 🅲️ **采用 NJX 治本方向**：6,072 没预案 = 灰小点（背景），218 有预案 = 彩色（主视觉）

**最终选择**: 🅲️ 治本颜色分层

**影响**:
- 6,072 没预案 = 灰小点 #9ca3af r=1.5（保持）
- 218 有预案 = 彩色蓝 #2563eb r=4-6（V26 改）
- 默认 ZOOM_DEFAULT 4→5（治本 V25 默认 22 站）
- 治本 NJX 反馈"地图上显示的航站数量明显不够"

**教训** (写入 memory):
- 重要的彩色，次要的灰，不要全灰
- NJX 反馈"显示不够" 不一定是真的少，可能**视觉上分不出来**
- 验证：render 数量 + 视觉数量 双验证（render 对不等于视觉对）

---

## D-027 · 地图 zoom 5 拥挤治本 (V28 supercluster)

**日期**: 2026-07-24
**决策者**: NJX 拍板
**背景**:
- V27 改 218 label 全部常驻，但 zoom 5 中国区 100+ 城市挤一起，label 重叠严重
- NJX 反馈"重叠的航站应该显示为数字"

**选项**:
- 🅰️ 改默认 zoom 4 (V19 tier 2 22 站) - 但 NJX V26 拍"默认 5 全显示 218"
- 🅱️ 缩小字号 + 半透明 - 治标
- 🅲️ **supercluster 数字聚合**（跟 V20 6,072 一致）：zoom 5-7 数字 bubble + 单点 label，zoom 8 全散开

**最终选择**: 🅲️ supercluster 数字聚合

**影响**:
- V19 旧 15 hub cluster (radius 80, maxZoom 4) 删
- V28 新 218 城市 supercluster (radius 50 → V28b 80, maxZoom 7, minPoints 2)
- 渲染逻辑：cluster → 数字 bubble / single → CityDot + label
- visibleCities 仅 zoom > 7 走（zoom 8 全散开）

**V28b 治本"5.0 还是有点挤"**：
- NJX 反馈 V28 后还挤
- PM 自主：radius 50→80（聚合更狠）
- 实测：zoom 5 蓝点 156→90 (-42%)，数字 bubble 28→53 (+89%)

---

## D-026 · Vite error overlay workaround (已知问题)

**日期**: 2026-07-23
**决策者**: PM 自主
**背景**:
- Next.js 15 + React 19 strict mode + leaflet 内部 removeChild 已知问题
- dev 重启时 process 死掉，仅 dev，production OK

**选项**:
- 🅰️ 升级 react-leaflet v5（内部用 React 18 createRoot 解决 strict mode）
- 🅱️ **重启 dev workaround**：`nohup pnpm dev --port 3004 > /tmp/aog_v28b_dev.log 2>&1 &`

**最终选择**: 🅱️ 重启 dev workaround（短期，V29+ 治本）

**影响**:
- dev 死掉时 15s 恢复
- production 不受影响
- 治本工作量 1-2 天（升级 react-leaflet v5）

---

## D-025 · V22 数字徽章 + 右侧 Panel (NJX 拍 🅱️)

**日期**: 2026-07-23
**决策者**: NJX 拍板
**背景**:
- V21 改"tooltip 限 5 + 还有 N 折叠"治标，多个城市 hover 仍堆叠
- NJX 反馈 V21 tooltip 限 5 仍堆叠

**选项**:
- 🅰️ tooltip 限 3 + 更多折叠（治标）
- 🅱️ **数字徽章 + flyTo + 右侧 panel**（治本）
- 🅲️ 缩略图 panel 列表 + click 高亮

**最终选择**: 🅱️ 数字徽章 + flyTo + 右侧 panel

**影响**:
- AirlineHubDot → AirlineHubBadge：紫环保留 + 中心 divIcon 28x28 紫底白字 N
- 选中态: outline 3px amber + scale 1.1
- AirlineHubPanel (320px 右侧浮层)：头部 IATA+城市+访问+X，列 N 航司
- ESC 关闭

---

## D-024 · V21 UI 简化 (NJX 拍 🅲️)

**日期**: 2026-07-23
**决策者**: NJX 拍板
**背景**:
- V20 加 6,072 全球机场 + 缩略图数字 panel
- NJX 反馈"页面太拥挤了，不应该显示太多航站细节"

**选项**:
- 🅰️ 保持 V20 缩略图
- 🅱️ 删缩略图
- 🅲️ **3 处简化**：字母 sidebar 26→flex-wrap / tooltip 限 top 5 / panel top 6

**最终选择**: 🅲️ 3 处简化

**影响**:
- alphabet-nav.tsx: sidebar `grid grid-cols-4` → `flex flex-wrap gap-1`，26 → 21 实际有数据字母
- world-map-leaflet.tsx: 航司 tooltip 限 top 5 + 还有 N 折叠，panel 12 → 6 国家
- globals.css: airline-hub-tooltip max-width 200px

**V22 推翻 V21**：
- NJX 反馈 V21 tooltip 限 5 仍堆叠
- 治本改数字徽章 + 右侧 panel（D-025）

---

## D-023 · V20 全球 6,072 机场 + AOG 218 两层 (NJX 拍 🅲️)

**日期**: 2026-07-22
**决策者**: NJX 拍板
**背景**:
- V19 完整 218 城市 MOCK
- NJX 反馈"未来全球每一个机场都应该显示"

**选项**:
- 🅰️ 只显示 AOG 218 城市
- 🅱️ 显示 AOG 218 + 中国主要机场
- 🅲️ **全球 6,072 机场 + AOG 218 两层叠加**

**最终选择**: 🅲️ 全球 6,072 机场 + AOG 218 两层

**影响**:
- OpenFlights airports.dat ETL → 6,072 机场 → public/data/global-airports.json (707KB)
- supercluster zoom < 4 聚合 (141/60/22/76/99/19 国家 cluster)
- zoom >= 4 散开 6,072 灰小点
- AOG 218 城市保持彩色 + label

**V26 治本颜色分层**（D-028）：
- 6,072 没预案 = 灰小点（背景）
- 218 有预案 = 彩色（主视觉）

---

## D-022 · V16 react-leaflet 嵌入主图 (NJX 拍 🅰️)

**日期**: 2026-07-21
**决策者**: NJX 拍板
**背景**:
- 找专业地图开源模型潜入地图页面
- 之前用 react-simple-maps 渲染静态 SVG 地图

**选项**:
- 🅰️ **react-leaflet + OSM tile**（真实 OSM tile，可交互）
- 🅱️ MapLibre + 自定义 tile
- 🅲️ 保留 react-simple-maps

**最终选择**: 🅰️ react-leaflet + OSM tile

**影响**:
- 替换 react-simple-maps 为 react-leaflet 4.2.1 + leaflet 1.9.4
- OSM tile 真实地图
- 需要 `dynamic({ssr: false})` 避免 SSR `window is not defined`
- 需要 `import "leaflet/dist/leaflet.css"` 否则 tile 不显示
- Vite error overlay 已知问题（react-leaflet v4 内部用 React 17 API）

---

## D-021 · Sprint A 密码 + JWT 24h (NJX 拍 🅰️)

**日期**: 2026-07-15
**决策者**: NJX 拍板
**背景**:
- 加入密码验证功能 (13456789)
- 之前想用客户端 JS 简单验证

**选项**:
- 🅰️ **SCF 后端鉴权 + JWT 24h**（PyJWT 2.8.0 HS256 + AuthGate）
- 🅱️ 客户端 JS 简单验证（不安全）
- 🅲️ 第三方 OAuth

**最终选择**: 🅰️ SCF 后端鉴权 + JWT 24h

**影响**:
- 密码 13456789 硬编码
- PyJWT 2.8.0 HS256 24h
- AuthGate client component
- V18 dev 跳过: `NEXT_PUBLIC_DISABLE_AUTH=1` 早期 return children

---

## D-020 · Sprint C 25 航司 + /api/airlines (NJX 拍 🅰️)

**日期**: 2026-07-15
**决策者**: NJX 拍板
**背景**:
- 加入航空公司基地检索
- 航司数据从哪来？

**选项**:
- 🅰️ **本地扒 20+ 航司 + /api/airlines**（民航局 + 维基 + 各航司官网）
- 🅱️ 现扒现用
- 🅲️ 空数组占位

**最终选择**: 🅰️ 本地扒 25 航司

**影响**:
- CA 国航/MU 东航/CZ 南航/HU 海航/3U 川航/9C 春秋/MF 厦航 等 25 真实航司
- 含 base 城市列表
- V18 dev MOCK，V15.3 isalnum 修复数字开头 IATA (3U/8L/9C/9D)

---

## D-019 · V15.1 字母导航改 Tab 切换 (NJX 拍修正)

**日期**: 2026-07-20
**决策者**: NJX 拍板
**背景**:
- V15 改字母导航左右并排 3 列 (航站 + 航司并列)
- NJX 反馈后改主意

**选项**:
- 🅰️ 保持 V15 2 个并列
- 🅱️ **可切换 tab** (航站 / 航司)

**最终选择**: 🅱️ tab 切换

**影响**:
- alphabet-nav.tsx 航站/航司 tab
- V24 进一步: 列表切航站/航司 tab 时地图要切换

---

## D-018 · V14 防御性 Client Render (治本 V13 后遗症)

**日期**: 2026-07-17
**决策者**: PM 自主
**背景**:
- V13 治本真实中文 file 名
- 但 NJX 反馈"打开失败"——法兰克福 client-side exception

**Root cause**:
1. `world-map.tsx:813/822/1081/1219` 4 处强制 `code.toLowerCase()`
2. SCF 真实 API `city.contacts[0].phone` 是 `string[]` 不是 `string`（mockup 是 string）

**修法**:
- 4 处 `.toLowerCase()` 删除，改 `encodeURIComponent(c.code)`
- `city-detail-client.tsx` render const try/catch wrap
- `Array.isArray(firstContact.phone) ? firstContact.phone[0] : firstContact.phone` 兼容

**影响**:
- 5/5 公网 verify: `/city/F-法兰克福（暂停）` HTTP 200
- 教训: client render 必须 try/catch wrap（V14 教训）

---

## D-017 · V13 真实中文 City File 名 (治本)

**日期**: 2026-07-17
**决策者**: PM 自主
**背景**:
- Next.js `output: export` URL 编码中文 file 名 → CloudBase 找不到
- V12 试图 Netlify `_redirects` 不支持（CloudBase 静态托管）

**修法**:
- `frontend/postbuild.sh` 新增：遍历 `out/city/`，把 URL 编码 file rename 成真实中文 file

**影响**:
- V12 后全部能直跳
- 教训: macOS APFS case-insensitive，A-澳门.html + a-澳门.html 不能共存，真实中文 file 名治本

---

## D-016 · 本地优先 Deploy 流程 (NJX 拍)

**日期**: 2026-07-17
**决策者**: NJX 拍板
**背景**:
- 改 UI 频繁，部署浪费时间
- 改 UI 必须先在本地验证

**选项**:
- 🅰️ 改 UI 直接 deploy 公网
- 🅱️ **改 UI 先 `pnpm dev` + Playwright 100% 通过才 deploy**

**最终选择**: 🅱️ 本地优先

**影响**:
- V13-V28b 全部在本地 dev 验证后才 commit
- 避免 deploy 出错浪费时间
- Playwright 是唯一 browser automation（mavis bash 无 mcp__cu 工具）

---

## D-015 · NSM-2 红线 (不可妥协)

**日期**: 2026-07-10
**决策者**: NJX 拍板
**背景**:
- AI chat 答案可能 LLM 幻觉
- 业务可靠性要求答案必须基于真实文档

**红线**: AI chat answers MUST include ≥ 1 real document reference

**实施**:
- RAG 检索 top-k 文档
- prompt 强制要求引用至少 1 个文档
- Playwright 测 chat 响应必须含 `references` 字段

**影响**:
- 不可妥协，任何 LLM 答案必须能追溯到真实文档
- 跟 NJX 业务（航材 AOG 支援）相关，错误答案可能导致实际损失

---

## 📊 决策统计

- **总决策**: 28
- **NJX 拍板**: 12 (D-021, D-022, D-023, D-024, D-025, D-028, D-016 等)
- **PM 自主**: 16 (D-017, D-018, D-026 等)
- **不可妥协红线**: 1 (D-015 NSM-2)

---

**新 AI 接手步骤**：
1. 读 STATUS.md (当前状态)
2. 读本文件 (已定决策，避免重复讨论)
3. 读 CHANGELOG.md (最近修改历史)
4. 跟 NJX 拍板前先查本文件，避免重复已决策的方向

---

**最后更新**: 2026-07-26 by Mavis
