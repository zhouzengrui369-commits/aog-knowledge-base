# AOG Web Frontend - 静态资源构建（CloudBase 静态托管）
#
# 用途: 在本地 / CI build 出 Next.js 静态产物, 然后用 tcb CLI 或控制台上传到
#       CloudBase 静态托管。
# 注: 实际部署推荐在本地 `pnpm build` + 手动 `tcb hosting deploy .next` ,
#     不用 Docker 构建 (节省 1GB+ 镜像).
# 这个 Dockerfile 是为"如果未来想 CI 全自动化"准备的备用方案.

# ---- Stage 1: deps ----
FROM node:20-alpine AS deps
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile --prefer-offline

# ---- Stage 2: build ----
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

RUN corepack enable && corepack prepare pnpm@9 --activate
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./

# 公网 API 地址由 build-time 注入 (替换为 CloudBase Run 域名)
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}

RUN pnpm build

# ---- Stage 3: standalone output (Next.js 15 自带) ----
# 如果 next.config.ts 输出 standalone 模式, 可以再小一点
# 这里只导出 .next + public, 上传到 CloudBase 静态托管

FROM node:20-alpine AS runner
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN corepack enable && corepack prepare pnpm@9 --activate
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules

# 暴露端口 (如果用 `pnpm start` 验证 build 结果)
EXPOSE 3000
CMD ["pnpm", "start"]

# 标签
LABEL org.opencontainers.image.title="aog-web-frontend" \
      org.opencontainers.image.description="AOG AI 知识库 · Next.js 15 前端 (可选, 推荐本地 build + 静态托管)" \
      org.opencontainers.image.licenses="Proprietary"
