"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowUpRight, BookOpen, FileText, MapPin, Plane } from "lucide-react";
import { AlphabetNav } from "@/components/alphabet-nav";
import { FeaturedCities } from "@/components/featured-cities";
import { getAirlines, getAirports, getCities, getMockFallbackPaths } from "@/lib/api";
import { enrichCities, topByViewCount } from "@/lib/city-stats";
import { getProductionStats, type ProductionStats } from "@/lib/production-api";
import type { Airline, Airport, City } from "@/lib/types";

const WorldMapLeaflet = dynamic(
  () => import("@/components/world-map-leaflet").then((module) => module.WorldMapLeaflet),
  { ssr: false, loading: () => <div className="grid h-full place-items-center text-sm text-ink-500">地图加载中…</div> }
);

export function HomeData() {
  const [cities, setCities] = useState<City[]>([]);
  const [airlines, setAirlines] = useState<Airline[]>([]);
  const [airports, setAirports] = useState<Airport[]>([]);
  const [stats, setStats] = useState<ProductionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredLetter, setHoveredLetter] = useState<string | null>(null);
  const [selectedCity, setSelectedCity] = useState<City | null>(null);
  const [selectedAirline, setSelectedAirline] = useState<Airline | null>(null);
  const [activeTab, setActiveTab] = useState<"city" | "airline">("city");
  const [mockFallbackPaths, setMockFallbackPaths] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCities(), getAirlines(), getAirports(), getProductionStats()]).then(
      ([cityRows, airlineRows, airportRows, liveStats]) => {
        if (cancelled) return;
        setCities(enrichCities(cityRows ?? []));
        setAirlines(airlineRows ?? []);
        setAirports(airportRows ?? []);
        setStats(liveStats);
        setMockFallbackPaths(getMockFallbackPaths());
        setLoading(false);
      }
    );
    return () => { cancelled = true; };
  }, []);

  const recommended = useMemo(() => topByViewCount(cities, 4), [cities]);
  const quickLinks = [
    { href: "/experiences", icon: FileText, title: "保障经验库", desc: stats ? `${stats.experiences} 条可发布经验` : "读取中" },
    { href: "/experiences?category=案例", icon: MapPin, title: "AOG 案例复盘", desc: "根因、处置与复盘记录" },
    { href: "/experiences?category=规范", icon: BookOpen, title: "航材保障规范", desc: "流程、合规要求与应急手册" },
    { href: "/airlines", icon: Plane, title: "航司互援资源", desc: stats ? `${stats.airlines} 家航司，冲突联系方式自动隔离` : "读取中" },
  ];

  return (
    <>
      {mockFallbackPaths.length > 0 && (
        <div role="alert" className="border-b-2 border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          <div className="mx-auto max-w-7xl">
            <strong>演示数据警告：</strong>以下接口发生 dev-only mock fallback：{mockFallbackPaths.join(", ")}。生产发布前必须为零。
          </div>
        </div>
      )}

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-500">城市预案</div>
            <h2 className="text-2xl font-semibold text-ink-900 sm:text-3xl">浏览城市与航司</h2>
            <p className="mt-1 text-sm text-ink-500">
              {stats ? `${stats.cities} 个城市 · ${stats.verified_cities} 个已核验 · ${stats.mapped_cities} 个有三字代码` : "正在读取生产统计"}
            </p>
          </div>
        </div>
        <div className="rounded-xl border border-ink-100 bg-white p-4 sm:p-5">
          {loading ? (
            <div className="grid h-[480px] place-items-center text-sm text-ink-500">加载中…</div>
          ) : cities.length === 0 ? (
            <div className="grid h-[320px] place-items-center rounded-lg border border-dashed border-ink-200 text-center text-sm text-ink-500">
              当前没有可发布城市数据。请检查 API 与数据发布状态，不会自动使用 mock。
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px,1fr] lg:gap-5">
              <div className="rounded-lg border border-ink-100 bg-ink-50/30 p-3 lg:h-[520px]">
                <AlphabetNav
                  cities={cities}
                  airlines={airlines}
                  mode="sidebar"
                  hoveredLetter={hoveredLetter}
                  onLetterHover={setHoveredLetter}
                  selectedAirline={selectedAirline}
                  onSelectAirline={setSelectedAirline}
                  activeTab={activeTab}
                  onTabChange={setActiveTab}
                />
              </div>
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
                  activeTab={activeTab}
                />
                <p className="mt-2 text-[11px] text-ink-400">全球机场底图来源：OpenFlights 数据快照；城市保障状态与联系人以本系统审核状态为准。</p>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 sm:pb-16 lg:px-8">
        <div className="mb-6">
          <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-500">高频访问</div>
          <h2 className="text-2xl font-semibold text-ink-900 sm:text-3xl">推荐城市</h2>
          <p className="mt-1 text-sm text-ink-500">按数据库累计访问次数排序；首次访问会显示“首次访问”，不伪造热度。</p>
        </div>
        {loading ? <div className="py-8 text-center text-sm text-ink-500">加载中…</div> : <FeaturedCities cities={recommended} />}
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="mb-6"><h2 className="text-2xl font-semibold text-ink-900 sm:text-3xl">从常用场景进入</h2></div>
        <div className="overflow-hidden rounded-xl border border-ink-100 bg-white">
          {quickLinks.map((item, index) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className={`group flex items-center gap-4 px-6 py-5 hover:bg-ink-50/60 ${index < quickLinks.length - 1 ? "border-b border-ink-100" : ""}`}>
                <span className="grid h-10 w-10 place-items-center rounded-lg border border-ink-100 text-ink-700 group-hover:border-primary group-hover:text-primary"><Icon className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1"><div className="text-sm font-semibold text-ink-900 group-hover:text-primary">{item.title}</div><div className="mt-0.5 text-xs text-ink-500">{item.desc}</div></div>
                <ArrowUpRight className="h-4 w-4 text-ink-300 group-hover:text-primary" />
              </Link>
            );
          })}
        </div>
      </section>
    </>
  );
}
