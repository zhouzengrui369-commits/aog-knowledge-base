"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { CityCard } from "@/components/city-card";
import { AlphabetNav } from "@/components/alphabet-nav";
import { getCities } from "@/lib/api";
import { MapPin, FileText, BookOpen } from "lucide-react";
import type { City } from "@/lib/types";

export function HomeData() {
  const [cities, setCities] = useState<City[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await getCities();
      if (cancelled) return;
      setCities(data ?? []);
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const recommendedCodes = ["B-北京大兴", "S-上海浦东", "G-广州白云", "H-香港"];
  const recommended = recommendedCodes
    .map((code) => cities.find((c) => c.code === code))
    .filter((c): c is City => Boolean(c));

  return (
    <>
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-ink-100 bg-white p-4 shadow-soft">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium text-ink-700">按首字母浏览</h2>
            <span className="text-xs text-ink-500">
              共 {cities.length} 个城市预案 · 已索引 {cities.length}
            </span>
          </div>
          {loading ? (
            <div className="text-ink-500 text-sm py-2">加载中…</div>
          ) : (
            <AlphabetNav cities={cities} />
          )}
        </div>
      </div>

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
