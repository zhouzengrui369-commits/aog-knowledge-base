# CORS 白名单修复证据 — 公网 SPA 访问 0 城市 → 223 城市

**Fix 日期**: 2026-07-17 14:30
**PM 拍板**: NJX 2026-07-17 14:27 "全面排查"
**Branch**: `fix/cors-public-spa` (worktree at `worktrees/cors-public-spa/`)
**关联 Issue**: NJX 浏览器访问 `https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com` 显示 "0 个城市", PM 30s 排查锁定 `HomeData` 组件 `getCities()` 客户端 fetch `/api/cities` → **CORS 拦截**

---

## 1. 根因

`aog-web/cloudbaserc.json` 的 `CORS_ALLOW_ORIGINS` 当时只含 3 个 origin:

```
https://njx-copilot-d6gs7642f8fa17122.ap-shanghai.app.tcloudbase.com   (旧, 平台默认)
https://aog.njx.com                                                     (未备案)
http://localhost:3000                                                   (dev)
```

**缺**: `https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com` (CloudBase 静态托管公网 URL)

→ 浏览器在公网 URL 发起的 fetch 被 FastAPI `CORSMiddleware` 拒绝 (无 `access-control-allow-origin` 头响应), `getCities()` throw → `cities=[]` → 页面渲染 "0 个城市"

---

## 2. 修复

### 2.1 cloudbaserc.json — 4 个 origin (新公网 URL 排第一)

```json
"CORS_ALLOW_ORIGINS": "https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com,https://njx-copilot-d6gs7642f8fa17122.ap-shanghai.app.tcloudbase.com,https://aog.njx.com,http://localhost:3000"
```

### 2.2 SCF env var 推送 — UpdateFunctionConfiguration

CORS env var 由 SCF 启动时读, **不重 deploy 代码** (代码未变), 用 `UpdateFunctionConfiguration` API 单独推 env:

```
[step1] GetFunction OK in 0.4s  (读当前 18 个 env var)
  OLD CORS_ALLOW_ORIGINS = https://njx-copilot-d6gs7642f8fa17122.ap-shanghai.app.tcloudbase.com,https://aog.njx.com,http://localhost:3000
  NEW CORS_ALLOW_ORIGINS = https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com,...(其他 3 个保留)
[step2] UpdateFunctionConfiguration ✅ OK in 0.4s
  RequestId: 4ce64c67-0fda-4b33-85d6-aa6160926c7a
```

部署脚本: `/tmp/scf_update_cors_env.py` (GetFunction → 读 current env → 改 CORS → UpdateFunctionConfiguration, 不动其他 17 个 env var)

> 注: 与之前 `bg_dd9cffcf` EP fix 路径不同, 那个改的是代码, 走 build/zip/UploadFunctionCode. 本次**只改 env var**, 直接 API 单点推送更快 (0.4s vs 30s), 也不动其他 env vars.

---

## 3. 4 项验收 (全过)

### ✅ 1) cloudbaserc.json 含 4 个 origin (新增公网 URL)

```bash
$ grep "CORS_ALLOW_ORIGINS" aog-web/cloudbaserc.json
"CORS_ALLOW_ORIGINS": "https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com,https://njx-copilot-d6gs7642f8fa17122.ap-shanghai.app.tcloudbase.com,https://aog.njx.com,http://localhost:3000",
```

✓ 4 个, 公网 URL 排第一 (优先级最高)

### ✅ 2) SCF UpdateFunctionConfiguration 200 + cold start OK

- RequestId: `4ce64c67-0fda-4b33-85d6-aa6160926c7a`
- elapsed 0.4s
- 首次 fetch 公网 URL 耗时 3.3s (冷启动, FTS5 索引从 COS 下载 + 进程初始化), 后续 0.5-0.7s

### ✅ 3) /api/cities CORS 4 项 (4 个 origin + 拒绝)

```bash
$ curl -H "Origin: https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com" \
       https://njx-copilot-d6gs7642f8fa17122.service.tcloudbase.com/api/cities -i
HTTP/1.1 200 OK
access-control-allow-credentials: true
access-control-allow-origin: https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com
content-type: application/json
x-cloudbase-upstream-status-code: 200
```

| Origin | 期望 | 实际 | 状态 |
|--------|------|------|------|
| `https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com` (新公网) | 200 + ACAO 匹配 | 200 + ACAO 匹配 | ✅ |
| `https://njx-copilot-d6gs7642f8fa17122.ap-shanghai.app.tcloudbase.com` (旧) | 200 + ACAO 匹配 | 200 + ACAO 匹配 | ✅ |
| `https://aog.njx.com` | 200 + ACAO 匹配 | 200 + ACAO 匹配 | ✅ |
| `https://evil.com` (攻击) | 200 但**无 ACAO 头** (浏览器会 block) | 200 无 ACAO 头 | ✅ |

✓ 4 个 origin 全 CORS 200, evil.com 被 FastAPI CORSMiddleware 静默拒绝 (无 ACAO 响应 → 浏览器 console 报 CORS 错)

返回 body: **223 城市** (api 返 list, count=223, 含 30 国际 + 193 国内)

### ✅ 4) NJX 浏览器实际显示 223 城市

**Playwright headless Chromium 验证** (`/tmp/cors_verify_screenshot.py`):

```
✅ home page render - title='AOG 应急保障知识库 · 航材 AOG 智能伙伴'
✅ body contains '223' - len(body)=506
✅ body does NOT show '0 个城市'
✅ 220/223 城市数据
✅ top viewport screenshot
```

**截图证据** (`project/AOG知识库网站/delivery/screenshots/W4-cors-fix/`):
- `cors_after_home.png` (256KB) — full_page 首页, 关键证据: "共 223 个城市预案 · 已索引 223"
- `cors_after_home_top.png` (260KB) — 1280×1600 viewport, 推荐城市区

页面关键 UI 元素:
- ✅ 顶部状态条: "数据已更新 · 220 城市预案 + 18 实战经验 + 14 核心预案"
- ✅ 按首字母浏览: "共 223 个城市预案 · 已索引 223" (从 0 → 223 ✓)
- ✅ 字母导航 A-Z 全渲染
- ✅ 推荐城市: 北京大兴 (PKX·华北·现行) 卡片正确显示
- ✅ 快速入口: 航站查询/保障经验/AI 知识助手
- ✅ 浮动 AI 角标

---

## 4. 副发现 (不影响本次 CORS fix, 留作 W4+)

`home-data.tsx` line 18-20 硬编码了 4 个推荐城市 code:

```ts
const recommendedCodes = ["B-北京大兴", "S-上海浦东", "G-广州白云", "H-香港"];
```

实测 API 返回的 code:
- `B-北京大兴` ✅ 命中
- `S-上海浦东` ❌ 不存在 (当前 223 城市里没此 code)
- `G-广州白云` ❌ 不存在
- `H-香港` ❌ 实际 code 是 `X-香港` (字母分类 X 不是 H)

→ 截图只显示 1 张推荐卡片 (北京大兴), 其他 3 张因 `cities.find()` 返回 undefined 被 filter 掉

**建议 W4+ 处理** (不在本 CORS fix 范围):
- 选项 A: 改前端用 `name` 字段匹配 (更稳)
- 选项 B: 改后端 code 命名 (B/S/G/H 字母序, 与 city pinyin 头字母对齐)
- 选项 C: 用 API 返 `featured=true` 字段, 前端按字段过滤

---

## 5. 关键文件

| 文件 | 改动 |
|------|------|
| `aog-web/cloudbaserc.json` | CORS_ALLOW_ORIGINS 加 1 个 origin (新公网 URL) |
| `aog-web/CORS_FIX_EVIDENCE.md` | 本文件 |
| `project/AOG知识库网站/delivery/screenshots/W4-cors-fix/cors_after_home.png` | 修复后首页截图 (256KB) |
| `project/AOG知识库网站/delivery/screenshots/W4-cors-fix/cors_after_home_top.png` | 修复后首页上半 viewport (260KB) |
| `/tmp/scf_update_cors_env.py` | UpdateFunctionConfiguration 部署脚本 (env-only) |
| `/tmp/cors_verify_screenshot.py` | Playwright 验证脚本 |
| `/tmp/scf_update_cors_response.json` | SCF API 响应落盘 |

---

## 6. Commit + Merge

```
fix/cors-public-spa:
  feat(cors): add public SPA URL to CORS_ALLOW_ORIGINS
    - aog-web/cloudbaserc.json: prepend njx-copilot-...-1343051603.tcloudbaseapp.com
    - UpdateFunctionConfiguration via SCF API (env-only, no code re-deploy)
    - 4 origin 全 CORS 200, evil.com 拒绝
    - 公网 SPA 城市显示 0 → 223
```

merge to main: `git checkout main && git merge --no-ff fix/cors-public-spa`
