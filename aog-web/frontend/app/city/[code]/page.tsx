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
  // 不 encode URI, Next.js 会自动处理 path segment encoding
  return [
    { code: "B-北京大兴" },
    { code: "S-上海浦东" },
    { code: "G-广州白云" },
    { code: "X-西安" },
  ];
}

/** 动态 SEO metadata */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  // metadata 失败用默认, 不阻塞 build
  return { title: "城市详情 · AOG 知识库" };
}

export default async function CityPage({ params }: PageProps) {
  const { code } = await params;
  const decoded = decodeURIComponent(code);

  // 用超时 1s 的 fetch 拉数据, 失败用 mock fallback (build 时不会卡 30s+ cold start)
  const city = await Promise.race([
    getCity(decoded),
    new Promise<null>((r) => setTimeout(() => r(null), 1000)),
  ]).catch(() => null);

  if (!city) {
    // fallback: 直接渲染 client 组件让浏览器去 fetch
    return <CityDetailClient code={decoded} />;
  }

  const st = STATUS_LABEL[normalizeCityStatus(city.status)] || { cls: "", text: city.status };
  const normalized = normalizeCityStatus(city.status);

  return (
    <>
      <NavBar />
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <nav className="text-xs text-ink-500">
          <Link href="/" className="hover:text-primary">首页</Link>
          <span className="mx-1">/</span>
          <Link href="/" className="hover:text-primary">航站查询</Link>
          <span className="mx-1">/</span>
          <span className="text-ink-700">{city.name}</span>
        </nav>
      </div>

      {normalized === "暂停" && (
        <div className="bg-amber-50 border-y border-amber-200 mt-3">
          <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8 flex items-center gap-2 text-amber-800 text-sm">
            <AlertTriangle className="h-4 w-4" />
            <span><strong>该站暂停保障</strong>，建议参考同地区可替代航站或联系总部协调。</span>
          </div>
        </div>
      )}

      <header className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-semibold text-ink-900">{city.name}</h1>
            {city.iata && (
              <span className="rounded bg-ink-100 px-2 py-0.5 text-xs text-ink-700 font-mono">{city.iata}</span>
            )}
            <span className={cn("rounded px-2 py-0.5 text-xs font-medium", st.cls)}>
              {st.text}
            </span>
            <span className="rounded bg-primary-50 px-2 py-0.5 text-xs text-primary-700">
              {city.region}
            </span>
          </div>
          {city.airport && <div className="text-sm text-ink-500">{city.airport}</div>}
          {city.tags && city.tags.length > 0 && (
            <div className="flex gap-1.5 flex-wrap mt-1">
              {city.tags.map((t) => (
                <span key={t} className="rounded-full bg-surface-2 px-2.5 py-0.5 text-xs text-ink-700">{t}</span>
              ))}
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <CityTabs city={city} />
          </div>
          <aside className="space-y-4">
            <div className="rounded-lg border border-surface-3 bg-white p-4 space-y-2">
              <h3 className="text-sm font-semibold text-ink-800">应急操作</h3>
              <button className="w-full flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm text-white hover:bg-primary-600">
                <Bot className="h-4 w-4" />
                AI 问询
              </button>
              <button className="w-full flex items-center justify-center gap-2 rounded-md border border-surface-3 bg-white px-3 py-2 text-sm text-ink-700 hover:bg-surface-2">
                <Download className="h-4 w-4" />
                下载预案 PDF
              </button>
            </div>
          </aside>
        </div>
        {city.updated_at && (
          <div className="mt-8 text-xs text-ink-500 text-center">
            最后更新：{fmtDate(city.updated_at)}
          </div>
        )}
        <div className="mt-4 text-center">
          <Link href="/" className="text-sm text-ink-500 hover:text-primary">
            <ChevronLeft className="mr-0.5 inline h-3 w-3" /> 返回首页
          </Link>
        </div>
      </main>
    </>
  );
}

// Fallback: 数据拉不到时 (build / 冷启动 / mock), 用 client 组件让浏览器 fetch
function CityFallback({ code }: { code: string }) {
  return <CityDetailClient code={code} />;
}
