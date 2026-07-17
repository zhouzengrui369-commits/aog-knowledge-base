"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { CityCard } from "@/components/city-card";
import { AlphabetNav } from "@/components/alphabet-nav";
import { WorldMapView } from "@/components/world-map";
import { getCities } from "@/lib/api";
import { enrichCities, topByViewCount } from "@/lib/city-stats";
import { MapPin, FileText, BookOpen } from "lucide-react";
import type { City } from "@/lib/types";

type View = "alpha" | "map";

export function HomeData() {
  const [cities, setCities] = useState<City[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>("alpha");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await getCities();
      if (cancelled) return;
      // 合并静态 view_count / lat / lon (SCF 暂未返回, 走 fallback)
      setCities(enrichCities(data ?? []));
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  // 推荐城市：按 view_count 降序取前 4
  const recommended = topByViewCount(cities, 4);

  return (
    <>
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-ink-100 bg-white p-4 shadow-soft">
          {/* 标题 + view 切换 tab */}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-medium text-ink-700">浏览城市</h2>
              <p className="mt-0.5 text-xs text-ink-500">
                共 {cities.length} 个城市预案 · {cities.filter((c) => c.lat != null).length} 个有坐标
              </p>
            </div>
            <div className="flex gap-1 rounded-md border border-ink-100 bg-ink-50 p-0.5">
              <button
                type="button"
                onClick={() => setView("alpha")}
                className={
                  "rounded px-3 py-1 text-xs font-medium transition " +
                  (view === "alpha"
                    ? "bg-white text-primary shadow-sm"
                    : "text-ink-500 hover:text-ink-900")
                }
              >
                按首字母
              </button>
              <button
                type="button"
                onClick={() => setView("map")}
                className={
                  "rounded px-3 py-1 text-xs font-medium transition " +
                  (view === "map"
                    ? "bg-white text-primary shadow-sm"
                    : "text-ink-500 hover:text-ink-900")
                }
              >
                世界地图
              </button>
            </div>
          </div>

          {loading ? (
            <div className="text-ink-500 text-sm py-2">加载中…</div>
          ) : view === "alpha" ? (
            <AlphabetNav cities={cities} />
          ) : (
            <WorldMapView cities={cities} />
          )}
        </div>
      </div>

      <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-xl font-semibold text-ink-900">推荐城市</h2>
            <p className="mt-1 text-sm text-ink-500">按 view_count 排序 · 现行有效 · 高频查询航站</p>
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
            <div className="text-base font-semibold text-ink-900 group-hover:text-primary">航站查询</div>
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
            <div className="text-base font-semibold text-ink-900 group-hover:text-primary">保障经验</div>
            <p className="mt-1 text-sm text-ink-500">
              18 个实战经验库 · 流程 / 规范 / 案例 / 培训 / 技术 / 管理
            </p>
          </Link>
          <Link
            href="#chat"
            className="group rounded-xl border border-ink-100 bg-white p-6 shadow-soft transition hover:border-primary hover:shadow-pop"
          >
            <div className="mb-3 grid h-10 w-10 place-items-center rounded-lg bg-accent-50 text-accent-600">
              <BookOpen className="h-5 w-5" />
            </div>
            <div className="text-base font-semibold text-ink-900 group-hover:text-primary">AI 知识助手</div>
            <p className="mt-1 text-sm text-ink-500">
              基于 8686 条知识片段的 RAG 问答 · 每条回答都附引用
            </p>
          </Link>
        </div>
      </section>
    </>
  );
}
