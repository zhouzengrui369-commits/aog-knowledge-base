# Wave 3 真 E2E 部署 · Notes

## 公网 URL
- 前端: https://njx-copilot-d6gs7642f8fa17122-1343051603.tcloudbaseapp.com
- 后端: https://njx-copilot-d6gs7642f8fa17122.service.tcloudbase.com/api

## 真 E2E 验证 (curl)
- GET /api/health → 200 `{"status":"ok","llm_mode":"live","rag_backend":"fts5"}`
- GET /api/cities?limit=2 → 200 (1MB+, 220 城市 content_md)
- GET /api/experiences?limit=2 → 400 (6MB SCF 上限, 后续优化 list 端点)
- POST /api/chat `{"q":"B787 风挡 AOG 处理"}` → 200
  - 5 真实文档引用 (NSM-2 满足):
    - `exp-e25c39e8` "B787 风挡AOG处理流程" (score 0.8, 真命中)
    - `exp-593dbe10` 知识库导出记录
    - `exp-3a73d6ac` AOG航材保障手册
    - `A-鞍山`, `S-韶关` (城市 fallback)

## 关键决策 (按 NJX 拍板顺序)
1. 🅲-2 SCF + SQLite FTS5 (替代 Chroma)
   - 个人版 CloudBase SCF 内存 512MB / timeout 60s / Python 3.11
   - FTS5 (trigram) 中文友好, 116MB Chroma → 27MB FTS5 index
   - cold start 30-60s (从 COS 下载 27MB fts5_index.db + 9.7MB aog.db + 2.2MB chunks_meta)
2. 个人版 0 成本运行 (NSM-2 后端)
3. 4 个真实文档引用 + 1 个 fallback (城市)

## 7 commits
- e2a3194: P1 FTS5 ETL (chroma → sqlite fts5, 8686 chunks, 27MB)
- 15f8ee4: P2 FTS5 client + RAG_BACKEND 切换
- 52d0825: P3 SCF web 函数 functions/aog-api
- c1f944c: P4 cloudbaserc + gitignore cleanup
- 0f41cb4: storage_cos.py 下载 fts5_index.db
- d32c55e: P5-P6 真 E2E + scf_cos inline + lazy imports
- d47c93c: P7-P8 前端静态化 + client component

## 7 张截图 (delivery/screenshots/W3-prod/)
- 01_home_desktop.png: 首页 Hero + 推荐城市 (北京大兴/上海浦东/广州白云/香港)
- 02_home_cities.png: 字母导航 A-Z + 城市列表
- 03_city_detail.png: 北京大兴详情 (PKX / 华北 / 3 机队 B787-A320-A321) — 真实数据
- 04_experiences_list.png: 保障经验列表 (B787 风挡 AOG 流程等)
- 05_experience_detail.png: B787 风挡 AOG 详情页
- 06_chat_open.png: AI 助手弹窗 (Sparkles 右下角)
- 07_health.png: /api/health JSON

## 关键工程决策
1. **Lazy imports** — chromadb / chroma_client 在 SCF 不可用, 改 try/except + lazy import
2. **inline COS signer** (scf_cos.py) — 不用 cos sdk (无 Linux wheel), 改 httpx + 手动 V4 sha1 签名
3. **vendor 策略** — 50MB Linux cp311 x86_64 wheel + cos sdk 复制 + six
4. **API Gateway /api 前缀** — scf_adapter 自动补回 (rawPath 被 strip)
5. **lifespan in main_handler** — 首次请求同步跑 startup (避免 daemon thread 不可靠)
6. **dynamic route → client component fallback** — Next.js 15 output: 'export' + 4 featured static + 其余 client-side load

## 已知问题
- /api/experiences?limit=2 response 超 6MB SCF 上限 → 改 list 端点 summary_only
- 测试域名有 "页面访问提示" 拦截 (首次需点"确定访问")
- 4 月 23 日 (NJX 个人版到期) 后需续费 / 迁企业版 / 迁 Railway

## 文件位置
- 后端: `aog-web/backend/aog_web/`
- SCF 函数: `aog-web/functions/aog-api/`
- cloudbaserc: `aog-web/cloudbaserc.json`
- 部署 SOP: `aog-web/DEPLOY_CLOUDBASE.md` (待更新)
- e2e 验证: `aog-web/tools/e2e_verify.sh`
- vendor 装包: `aog-web/functions/aog-api/build_vendor.sh`
- 部署脚本: `aog-web/tools/deploy_frontend_static.sh`
- 截图: `project/AOG知识库网站/delivery/screenshots/W3-prod/`
- 数据 COS 桶: `aog-prod-data-1343051603` (11 对象 155MB)
- envId: `njx-copilot-d6gs7642f8fa17122`
