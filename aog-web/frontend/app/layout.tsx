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
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="bg-white font-sans text-ink-900 antialiased">
        <AuthGate>
          {children}
          <ChatWidget />
        </AuthGate>
      </body>
    </html>
  );
}
