import type { Metadata } from "next";
import { ChatWidget } from "@/components/chat-widget";
import AuthGate from "@/components/auth-gate";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "AOG 应急保障知识库 · 航材 AOG 智能伙伴",
    template: "%s · AOG 知识库",
  },
  description: "航材 AOG 智能伙伴 — 城市预案、保障经验、AI 对话一站式查询",
  metadataBase: new URL("http://localhost:3000"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="font-sans text-ink-900 bg-white antialiased">
        {/* Sprint A: 整个 SPA 套 AuthGate, 未登录显示密码页 */}
        <AuthGate>
          {children}
          {/* ChatWidget 全局挂载（悬浮右下角） */}
          <ChatWidget />
        </AuthGate>
      </body>
    </html>
  );
}
