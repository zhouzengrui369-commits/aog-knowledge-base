import Link from "next/link";
import { NavBar } from "@/components/nav-bar";
import { Hero } from "@/components/hero";
import { CityCard } from "@/components/city-card";
import { AlphabetNav } from "@/components/alphabet-nav";
import { getCities } from "@/lib/api";
import { MapPin, FileText, BookOpen, Github } from "lucide-react";

export const dynamic = "force-dynamic"; // 每次请求重新拉数据（mock fallback 保证可显示）

export default async function HomePage() {
  const cities = await getCities();
  // 首页推荐 4 张（与 mockup 一致：B-北京大兴/S-上海浦东/G-广州白云/H-香港）
  const recommendedCodes = ["B-北京大兴", "S-上海浦东", "G-广州白云", "H-香港"];
  const recommended = recommendedCodes
    .map((code) => cities.find((c) => c.code === code))
    .filter((c): c is NonNullable<typeof c> => Boolean(c));

  return (
    <>
      <NavBar active="home" />
      <Hero />
      {/* Alphabet nav */}
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-ink-100 bg-white p-4 shadow-soft">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium text-ink-700">按首字母浏览</h2>
            <span className="text-xs text-ink-500">
              共 {cities.length} 个城市预案 · 已索引 {cities.length}
            </span>
          </div>
          <AlphabetNav cities={cities} />
        </div>
      </div>

      {/* Recommended cities */}
      <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-xl font-semibold text-ink-900">推荐城市</h2>
            <p className="mt-1 text-sm text-ink-500">现行有效 · 高频查询航站</p>
          </div>
          <Link
            href="/experiences"
            className="hidden text-sm text-primary hover:underline sm:inline"
          >
            查看全部经验 →
          </Link>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {recommended.map((c) => (
            <CityCard key={c.code} city={c} />
          ))}
        </div>
      </section>

      {/* Entry cards */}
      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-ink-900">快速入口</h2>
          <p className="mt-1 text-sm text-ink-500">从最常用的场景进入</p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Link
            href="#alpha"
            className="group rounded-xl border border-ink-100 bg-white p-6 shadow-soft transition hover:border-primary hover:shadow-pop"
          >
            <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg bg-primary-50 text-primary">
              <MapPin className="h-5 w-5" />
            </div>
            <div className="text-base font-semibold text-ink-900 group-hover:text-primary">
              航站查询
            </div>
            <p className="mt-1 text-sm text-ink-500">
              {cities.length} 个城市的应急保障预案，支持按首字母 / 地区过滤
            </p>
          </Link>
          <Link
            href="/experiences"
            className="group rounded-xl border border-ink-100 bg-white p-6 shadow-soft transition hover:border-primary hover:shadow-pop"
          >
            <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg bg-secondary/10 text-secondary">
              <FileText className="h-5 w-5" />
            </div>
            <div className="text-base font-semibold text-ink-900 group-hover:text-primary">
              保障经验
            </div>
            <p className="mt-1 text-sm text-ink-500">
              18 个实战经验库 · 流程/规范/案例/培训/技术/管理
            </p>
          </Link>
          <div className="relative cursor-not-allowed rounded-xl border border-dashed border-ink-100 bg-ink-50/50 p-6 opacity-60">
            <div className="absolute right-3 top-3 rounded bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500">
              v2 灰显
            </div>
            <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg bg-ink-100 text-ink-500">
              <BookOpen className="h-5 w-5" />
            </div>
            <div className="text-base font-semibold text-ink-700">课件</div>
            <p className="mt-1 text-sm text-ink-500">v1 不上线 · 已在库但暂不开放</p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-ink-100 bg-ink-50">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div>© 2026 AOG 知识库 · v0.1.0-frontend</div>
          <div>数据更新时间：2026-04-15 · 共 252 份文档</div>
          <div className="flex items-center gap-3">
            <Link href="/experiences" className="hover:text-ink-900">
              保障经验
            </Link>
            <a
              href="https://github.com/"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 hover:text-ink-900"
            >
              <Github className="h-3 w-3" /> GitHub
            </a>
          </div>
        </div>
      </footer>
    </>
  );
}
