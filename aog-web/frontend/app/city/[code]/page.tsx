import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import { NavBar } from "@/components/nav-bar";
import { CityTabs } from "@/components/city-tabs";
import { getCity, getCities } from "@/lib/api";
import { normalizeCityStatus, STATUS_LABEL, cn, fmtDate } from "@/lib/utils";
import { Download, Bot, ChevronLeft, AlertTriangle } from "lucide-react";
import type { City } from "@/lib/types";
import { CityDetailClient } from "@/components/city-detail-client";

interface PageProps {
  params: Promise<{ code: string }>;
}

/** 静态生成 — 列出 featured 城市 (其余 client-side 加载, 避开 SCF cold start 30-60s) */
export async function generateStaticParams() {
  // Next.js 15 + output:export 期望 path segment 已 encode (lowercase, URL 形态)
  // dev mode 的 URL 也是 lowercase, 保持一致避免 "missing param" 错误
  const featured = [
    "B-北京大兴",
    "S-上海浦东",
    "G-广州白云",
    "X-西安",
  ];
  return featured.map((code) => ({ code: encodeURIComponent(code).toLowerCase() }));
}

/** 动态 SEO metadata */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  // metadata 失败用默认, 不阻塞 build
  return { title: "城市详情 · AOG 知识库" };
}

export default async function CityPage({ params }: PageProps) {
  const { code } = await params;
  // 总是渲染 client 组件 — 浏览器去 fetch /api/city/{code}
  // 这样 SSG HTML 是空骨架, 客户端 hydrate 后会显示真实数据
  // 避免 build 时 fetch SCF 失败 (HTTP 500) 锁死 "城市未找到" 状态
  return <CityDetailClient code={code} />;
}

// Fallback: 数据拉不到时 (build / 冷启动 / mock), 用 client 组件让浏览器 fetch
function CityFallback({ code }: { code: string }) {
  return <CityDetailClient code={code} />;
}
