"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { FeaturedCities } from "@/components/featured-cities";
import { AlphabetNav } from "@/components/alphabet-nav";
import dynamic from "next/dynamic";
import { getCities, getAirlines, getAirports } from "@/lib/api";
import { enrichCities, topByViewCount } from "@/lib/city-stats";
import { FileText, BookOpen, ArrowUpRight, MapPin, Plane } from "lucide-react";
import type { City, Airline, Airport } from "@/lib/types";

// V18: 解决 SSR window 报错 — leaflet 内部用 window, 客户端动态 import
const WorldMapLeaflet = dynamic(
  () => import("@/components/world-map-leaflet").then(m => m.WorldMapLeaflet),
  { ssr: false, loading: () => <div className="grid h-full place-items-center text-sm text-ink-500">地图加载中…</div> }
);

const QUICK_LINKS = [
  {
    href: "/experiences",
    icon: FileText,
    title: "保障经验库",
    desc: "18 份实战经验 · 流程 / 规范 / 案例 / 培训 / 技术 / 管理",
  },
  {
    href: "/experiences?category=案例",
    icon: MapPin,
    title: "AOG 案例复盘",
    desc: "真实事件处置记录，含根因 + 教训 + 改进项",
  },
  {
    href: "/experiences?category=规范",
    icon: BookOpen,
    title: "航材保障规范",
    desc: "标准操作流程、合规要求、应急手册",
  },
  {
    href: "/airlines",
    icon: Plane,
    title: "航司互援资源",
    desc: "25 家中国主要航司 · 基地 / 机队 / 联盟 / AOG 联系方式",
  },
];

/**
 * Home — 客户端数据组件
 * V2: 统一视图 — 字母侧栏 (固定) + 地图 (主区域)，无 toggle
 *   - hover 字母 → 地图同步 pulse 该字母城市
 *   - 点城市 → 自动 pan/zoom + 显示周边
 */
export function HomeData() {
  const [cities, setCities] = useState<City[]>([]);
  const [airlines, setAirlines] = useState<Airline[]>([]);
  const [airports, setAirports] = useState<Airport[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredLetter, setHoveredLetter] = useState<string | null>(null);
  const [selectedCity, setSelectedCity] = useState<City | null>(null);
  // V24: 航司 tab 选中状态 — 列表点航司行 → 地图高亮 base + 顶部 chip
  const [selectedAirline, setSelectedAirline] = useState<Airline | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [citiesData, airlinesData, airportsData] = await Promise.all([
        getCities(),
        getAirlines(),
        getAirports(),
      ]);
      if (cancelled) return;
      setCities(enrichCities(citiesData ?? []));
      setAirlines(airlinesData ?? []);
      setAirports(airportsData ?? []);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const recommended = topByViewCount(cities, 4);

  return (
    <>
      {/* SECTION 1 — 浏览城市 (V2 统一视图: 字母 sidebar + 地图) */}
      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-500">
              城市预案
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-ink-900 sm:text-3xl">
              浏览城市
            </h2>
            <p className="mt-1 text-sm text-ink-500">
              {cities.length} 个航站 ·{" "}
              {cities.filter((c) => c.lat != null).length} 个已上图 ·{" "}
              <span className="text-ink-400">hover 字母同步地图高亮 · 点城市查看周边</span>
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-ink-100 bg-white p-4 sm:p-5">
          {loading ? (
            <div className="grid h-[480px] place-items-center text-sm text-ink-500">
              加载中…
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px,1fr] lg:gap-5">
              {/* 字母侧栏 — V15.1 单 sidebar 切换航站/航司 */}
              <div className="rounded-lg border border-ink-100 bg-ink-50/30 p-3 lg:h-[520px]">
                <AlphabetNav
                  cities={cities}
                  airlines={airlines}
                  mode="sidebar"
                  hoveredLetter={hoveredLetter}
                  onLetterHover={setHoveredLetter}
                  selectedAirline={selectedAirline}
                  onSelectAirline={setSelectedAirline}
                />
              </div>

              {/* 地图主区域 - V18: dynamic import 解决 SSR window 报错 */}
              <div className="lg:h-[520px]">
                <WorldMapLeaflet
                  cities={cities}
                  airlines={airlines}
                  airports={airports}
                  hoveredLetter={hoveredLetter}
                  selectedCity={selectedCity}
                  onSelectCity={setSelectedCity}
                  selectedAirline={selectedAirline}
                  onSelectAirline={setSelectedAirline}
                />
              </div>
            </div>
          )}
        </div>
      </section>

      {/* SECTION 2 — 推荐城市 (1 大 + 3 小) */}
      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 sm:pb-16 lg:px-8">
        <div className="mb-6 flex items-end justify-between">
          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-500">
              高频访问
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-ink-900 sm:text-3xl">
              推荐城市
            </h2>
            <p className="mt-1 text-sm text-ink-500">
              按访问次数排序 · 现行有效保障
            </p>
          </div>
          <Link
            href="/experiences"
            className="hidden text-sm text-ink-500 transition hover:text-primary sm:inline"
          >
            查看全部经验 →
          </Link>
        </div>
        {loading ? (
          <div className="py-8 text-center text-sm text-ink-500">加载中…</div>
        ) : (
          <FeaturedCities cities={recommended} />
        )}
      </section>

      {/* SECTION 3 — 快速入口 (横向 list, 非 grid) */}
      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="mb-6">
          <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-500">
            快速入口
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-ink-900 sm:text-3xl">
            从最常用的场景进入
          </h2>
        </div>
        <div className="overflow-hidden rounded-xl border border-ink-100 bg-white">
          {QUICK_LINKS.map((item, i) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={
                  "group flex items-center gap-4 px-6 py-5 transition hover:bg-ink-50/60" +
                  (i < QUICK_LINKS.length - 1
                    ? " border-b border-ink-100"
                    : "")
                }
              >
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-ink-100 text-ink-700 transition group-hover:border-primary group-hover:text-primary">
                  <Icon className="h-5 w-5" strokeWidth={1.5} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-ink-900 transition group-hover:text-primary">
                    {item.title}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-ink-500">
                    {item.desc}
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-ink-300 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary" />
              </Link>
            );
          })}
        </div>
      </section>
    </>
  );
}
