// ESLint 10 flat config (Owner 7/29 CI Green Closure: next lint 已被 Next 16 移除)
// 仅对 frontend lib/components/app 做基础 lint, 不做 stylistic 规则
import js from "@eslint/js";
import tsParser from "@typescript-eslint/parser";

export default [
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      ".next.died/**",
      "out/**",
      "tests/**",          // vitest 测试文件不参与前端 lint
      "lib/mock/cities.ts", // 2213 行 mockup 数据, 不参与 lint
      "vitest.config.ts",
      "next-env.d.ts",
    ],
  },
  js.configs.recommended,
  {
    files: ["**/*.{ts,tsx,js,jsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
      globals: {
        window: "readonly",
        document: "readonly",
        process: "readonly",
        console: "readonly",
        fetch: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        HTMLElement: "readonly",
        HTMLDivElement: "readonly",
        HTMLInputElement: "readonly",
        HTMLFormElement: "readonly",
        HTMLButtonElement: "readonly",
        HTMLAnchorElement: "readonly",
        HTMLImageElement: "readonly",
        HTMLLabelElement: "readonly",
        Element: "readonly",
        NodeJS: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        Buffer: "readonly",
        global: "readonly",
      },
    },
    rules: {
      "no-unused-vars": "off",  // 用 TypeScript noUnusedLocals
      "no-undef": "off",        // TS 已经有
      "no-empty": ["warn", { "allowEmptyCatch": true }],
      "no-prototype-builtins": "off",       // Next.js runtime 内部用, 不可改
      "no-redeclare": "off",                // Next.js runtime 内部用
      "no-fallthrough": "off",              // switch case fallthrough 在 Next.js runtime
      "no-control-regex": "off",            // 字符处理 regex (\x01 是合法控制字符)
      "no-useless-escape": "off",           // 字符转义在 regex context 是合法的
      "no-self-assign": "off",              // polyfill 内部用
      "no-cond-assign": "off",              // polyfill 用
      "no-sparse-arrays": "off",            // Next.js compile output 含空位
      "no-useless-assignment": "off",       // polyfill 用
      "no-unassigned-vars": "off",          // polyfill 用
    },
  },
];
