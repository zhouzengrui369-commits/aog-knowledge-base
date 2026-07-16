# AOG Web Backend - CloudBase Run 容器镜像
#
# 用途：腾讯云 CloudBase Run 容器部署
# 构建 (从 worktree 根目录):
#   docker build -f aog-web/aog-web-backend.Dockerfile -t aog-web-backend:latest .
# 端口: 8000 (CloudBase Run 通过 $PORT 环境变量注入)
# 数据: 容器冷启动时从 COS 下载 chroma/ + aog.db 到 /app/aog-web/backend/data
# 启动: python -m aog_web.scripts.migrate_and_start (内置 COS 预热 + uvicorn)
#
# Build context 约定: 从 worktree 根目录 (aog-web/ 所在层) build, Dockerfile 内的
# COPY 路径以 aog-web/backend/ 为准. 镜像内 WORKDIR 仍是 /app/aog-web/backend,
# 跟本地 dev (uv run) 的相对路径一致.

# ---- Base: 官方 Python slim ----
FROM python:3.11-slim AS base

# 系统依赖 (uv 加速, build-essential 备用)
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv (比 pip 快 10x)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# ---- Backend 依赖 ----
WORKDIR /app/aog-web/backend

# 单独 COPY pyproject + uv.lock 最大化层缓存
COPY aog-web/backend/pyproject.toml aog-web/backend/uv.lock ./

# 用 uv 装所有依赖 (含 dev 暂时用不到，但方便 debug)
RUN uv sync --frozen --no-install-project --no-dev || uv sync --frozen --no-install-project

# ---- 业务代码 ----
COPY aog-web/backend/aog_web ./aog_web

# 安装项目自身（让 `python -m aog_web.scripts.migrate_and_start` 可用）
RUN uv sync --frozen --no-dev

# ---- 启动脚本 (COS 预热 + uvicorn) ----
# CloudBase Run 必须用脚本入口（lifespan 里没法装 COS hook）
# 容器启动命令在 cloudbaserc.json 的 settings.container.image 配套,
# 或在 CloudBase 控制台 "启动命令" 字段填: .venv/bin/python -m aog_web.scripts.migrate_and_start
#
# ★ 必须用 .venv/bin/python 启动: deps 装在 WORKDIR/.venv 里, 系统 Python 没装
#   (uv sync 不会污染 base image 的 site-packages)
ENV PATH="/app/aog-web/backend/.venv/bin:${PATH}"
ENTRYPOINT [".venv/bin/python", "-m", "aog_web.scripts.migrate_and_start"]

# 健康检查 (CloudBase Run 通过 /api/health 探活)
# 注意: 容器内 curl 不一定有，用 Python http.client
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD .venv/bin/python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3); sys.exit(0 if r.status==200 else 1)" || exit 1

EXPOSE 8000

# 元数据
LABEL org.opencontainers.image.title="aog-web-backend" \
      org.opencontainers.image.description="AOG AI 知识库 · FastAPI 后端 (CloudBase Run 容器)" \
      org.opencontainers.image.source="https://example.local/aog-web" \
      org.opencontainers.image.licenses="Proprietary"
