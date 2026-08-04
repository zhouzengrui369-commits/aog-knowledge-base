import type { NextConfig } from "next";

// V8: dev 模式不强制 output:export (避免 generateStaticParams 严格检查)
//   - dev 走 dynamic 渲染, [code] 路径无需预生成
//   - production 仍用 output:export, 静态托管需要纯静态 out/
const isDev = process.env.NODE_ENV !== 'production';

// FOCUSED-RETEST-2026-08-04 (R2 successor, NJX 8/4 09:28 拍板 D):
//   Bind Next.js build identity to the candidate commit.  This is the
//   ONLY allowed next.config.ts modification in the R2 candidate.
//   Production build refuses to proceed if neither APP_COMMIT_SHA nor
//   GITHUB_SHA is set; local development falls back to a stable tag.
const nextConfig: NextConfig = {
  // Bind buildId to candidate commit (FROZEN_REPLAYABLE_ARTIFACT contract).
  generateBuildId: async () =>
    process.env.APP_COMMIT_SHA ||
    process.env.GITHUB_SHA ||
    "local-development",
  reactStrictMode: true,
  // 静态导出 (CloudBase 静态托管需要纯静态 out/) — 只在 production
  ...(isDev ? {} : { output: 'export' as const }),
  // 允许 next/image 加载 http 图片（mockup 阶段暂无图，留作扩展）
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
  // 临时调大 build 静态生成 retry — production API cold start 4-10s, 4 个城市 + 4 个经验
  experimental: {
    staticGenerationRetryCount: 5, // 默认 3 → 5
  },
  // 同源 dev API 兼容 (T1 启动后再调整)
  async rewrites() {
    return [];
  },
  // V13: 关掉 redirects() — 避免 dev 模式 50 redirect 死循环
  //   lowercase URL 现在由 client 端 useEffect 智能 404 (V12.2 已实现) 处理
  //   CloudBase 静态托管本身不支持 redirect, postbuild.sh 仍生成 _redirects 文件备选
  async redirects() {
    return [];
  },
};

export default nextConfig;
