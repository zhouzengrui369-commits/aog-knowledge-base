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
import cityCodes from "../codes.json";

interface PageProps {
  params: Promise<{ code: string }>;
}

/** 静态生成 — 直接用原始 city code (next.js 会自己处理 URL 编码) */
export async function generateStaticParams() {
  // V13: 不 encode — 让 next.js 内部处理, postbuild.sh 会把 URL 编码 file rename 回真实中文
  //   原因: next.js output:export 默认把 B-北京大兴.html encode 成 B-%E5%8C%97%E4%BA%AC%E5%A4%A7%E5%85%B4.html
  //   CloudBase 静态托管对 URL-encoded file 名支持不全, 公网访问 /city/C-重庆江北 返 404
  //   postbuild.sh rename 解决: B-%E5%8C%97%E4%BA%AC%E5%A4%A7%E5%85%B4.html → B-北京大兴.html
  return cityCodes.map((code) => ({ code }));
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
