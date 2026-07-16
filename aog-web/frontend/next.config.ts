import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // 静态导出 (CloudBase 静态托管需要纯静态 out/)
  output: 'export',
  // 允许 next/image 加载 http 图片（mockup 阶段暂无图，留作扩展）
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
  // 同源 dev API 兼容 (T1 启动后再调整)
  async rewrites() {
    return [];
  },
};

export default nextConfig;
