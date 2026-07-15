import type { Config } from "tailwindcss";

// 颜色 token 完全继承 mockup 5 个 HTML 共享的 tailwind.config（CONTRACT §4.4）
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#1e40af",
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          900: "#1e3a8a",
        },
        secondary: {
          DEFAULT: "#0891b2",
          50: "#ecfeff",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
        },
        ink: {
          900: "#111827",
          700: "#374151",
          500: "#6b7280",
          300: "#d1d5db",
          100: "#f3f4f6",
          50: "#f9fafb",
        },
        success: {
          DEFAULT: "#16a34a",
          50: "#f0fdf4",
          600: "#16a34a",
          700: "#15803d",
        },
        warning: {
          DEFAULT: "#d97706",
          50: "#fffbeb",
          600: "#d97706",
          700: "#b45309",
        },
        danger: {
          DEFAULT: "#dc2626",
          50: "#fef2f2",
          600: "#dc2626",
          700: "#b91c1c",
        },
      },
      boxShadow: {
        soft: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)",
        pop: "0 10px 25px -5px rgb(0 0 0 / 0.10), 0 8px 10px -6px rgb(0 0 0 / 0.06)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
