import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import { NavBar } from "@/components/nav-bar";
import { CityTabs } from "@/components/city-tabs";
import { getCity, getCities } from "@/lib/api";
import { normalizeCityStatus, STATUS_LABEL, cn, fmtDate } from "@/lib/utils";
import { Download, Bot, ChevronLeft, AlertTriangle, X } from "lucide-react";

interface PageProps {
  params: Promise<{ code: string }>;
}

/** 静态生成 — 当前 mockup 数据中的 4 个 featured 城市 */
export async function generateStaticParams() {
  // 返回空数组 → 走 dynamic 渲染（fetch 走 mock fallback 总是有数据）
  return [];
}

/** 动态 SEO metadata */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { code } = await params;
  const decoded = decodeURIComponent(code);
  const city = await getCity(decoded);
  if (!city) {
    return { title: "城市未找到" };
  }
  return {
    title: `${city.name} · AOG 知识库`,
    description: city.summary || `${city.name} 应急保障预案`,
  };
}

export default async function CityPage({ params }: PageProps) {
  const { code } = await params;
  const decoded = decodeURIComponent(code);
  const city = await getCity(decoded);
  if (!city) {
    notFound();
  }

  const st = STATUS_LABEL[normalizeCityStatus(city.status)];
  const normalized = normalizeCityStatus(city.status);

  // 找 3 个相关城市（同地区优先）
  const allCities = await getCities();
  const others = allCities.filter((c) => c.code !== city.code);
  const sameRegion = others.filter((c) => c.region === city.region).slice(0, 3);
  const fill = others.filter((c) => c.region !== city.region).slice(0, 3 - sameRegion.length);
  const related = [...sameRegion, ...fill].slice(0, 3);

  return (
    <>
      <NavBar />
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <nav className="text-xs text-ink-500">
          <Link href="/" className="hover:text-primary">
            首页
          </Link>
          <span className="mx-1">/</span>
          <Link href="/" className="hover:text-primary">
            航站查询
          </Link>
          <span className="mx-1">/</span>
          <span className="text-ink-700">{city.name}</span>
        </nav>
      </div>

      {/* Status banner */}
      {normalized === "暂停" && (
        <div className="mx-auto max-w-7xl px-4 pt-3 sm:px-6 lg:px-8">
          <div className="rounded-lg border border-warning/30 bg-warning-50 px-4 py-2.5 text-sm text-warning-700">
            <span className="font-medium">
              <AlertTriangle className="mr-1 inline h-4 w-4" /> 该预案已暂停
            </span>
            · 仅供历史参考，请联系 AOG 中心确认最新流程。
          </div>
        </div>
      )}
      {normalized === "已废" && (
        <div className="mx-auto max-w-7xl px-4 pt-3 sm:px-6 lg:px-8">
          <div className="rounded-lg border border-danger-100 bg-danger-50 px-4 py-2.5 text-sm text-danger-700">
            <span className="font-medium">
              <X className="mr-1 inline h-4 w-4" /> 该预案已废止
            </span>
            · 不再使用，请参考其他现行预案。
          </div>
        </div>
      )}

      <section className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
        <div className="overflow-hidden rounded-2xl border border-ink-100 bg-white shadow-soft">
          {/* Header */}
          <div className="border-b border-ink-100 bg-gradient-to-r from-primary-50 via-white to-secondary-50 px-6 py-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold text-ink-900 sm:text-3xl">{city.name}</h1>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
                      st.cls
                    )}
                  >
                    <span className={cn("h-1.5 w-1.5 rounded-full", st.dot)} />
                    {st.text}
                  </span>
                </div>
                <div className="mt-1 text-sm text-ink-500">
                  {city.iata || "—"} · {city.region} · {city.code}
                </div>
                {city.summary && (
                  <p className="mt-2 max-w-3xl text-sm text-ink-700">{city.summary}</p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex cursor-not-allowed items-center gap-1 rounded-md border border-ink-100 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 opacity-60">
                  <Download className="h-3.5 w-3.5" /> 下载 docx
                </span>
                <span className="inline-flex cursor-not-allowed items-center gap-1 rounded-md border border-ink-100 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 opacity-60">
                  <Download className="h-3.5 w-3.5" /> 下载 pdf
                </span>
                <a
                  href="#chat"
                  className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white shadow-soft hover:bg-primary-700"
                >
                  <Bot className="h-3.5 w-3.5" /> 问 AI
                </a>
              </div>
            </div>
          </div>

          {/* Tabs + Sidebar */}
          <div className="grid grid-cols-1 gap-0 lg:grid-cols-[1fr_280px]">
            <CityTabs city={city} />
            <aside className="hidden border-l border-ink-100 bg-ink-50/50 p-6 lg:block">
              <div className="mb-4 rounded-lg border border-ink-100 bg-white p-3">
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink-700">
                  <Bot className="h-3.5 w-3.5" /> AI 助手
                </div>
                <p className="text-xs text-ink-500">
                  可问我此城市的备件、联系人、物流方案等问题。
                </p>
                <a
                  href="#chat"
                  className="mt-2 block w-full rounded-md bg-primary px-3 py-1.5 text-center text-xs font-medium text-white hover:bg-primary-700"
                >
                  打开 AI 助手
                </a>
              </div>

              <h3 className="mb-2 text-xs font-semibold text-ink-700">相关城市</h3>
              <div className="space-y-2">
                {related.map((c) => (
                  <Link
                    key={c.code}
                    href={`/city/${encodeURIComponent(c.code)}`}
                    className="block rounded-md border border-ink-100 bg-white px-3 py-2 text-sm hover:border-primary"
                  >
                    <div className="font-medium text-ink-900">{c.name}</div>
                    <div className="text-[11px] text-ink-500">
                      {c.region} · {c.iata || "—"}
                    </div>
                  </Link>
                ))}
              </div>

              <div className="mt-4 text-[11px] text-ink-500">
                数据更新：{fmtDate(city.updated_at)}
              </div>
            </aside>
          </div>
        </div>
      </section>

      <footer className="border-t border-ink-100 bg-ink-50">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div>© 2026 AOG 知识库 · v0.1.0-frontend</div>
          <div>
            <Link href="/" className="hover:text-ink-900">
              <ChevronLeft className="mr-0.5 inline h-3 w-3" /> 返回首页
            </Link>
          </div>
        </div>
      </footer>
    </>
  );
}
