// Vitest 配置: 跑 P0-4 production mock 隔离测试
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    environment: "node",
    testTimeout: 10000,
  },
});
