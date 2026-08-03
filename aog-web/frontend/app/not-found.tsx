"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Home, Plane, Search } from "lucide-react";
import { NavBar } from "@/components/nav-bar";
import { getCities } from "@/lib/api";
import { getProductionStats } from "@/lib/production-api";
import type { City } from "@/lib/types";

export default function NotFound() {
  const router = useRouter();
  const [cities, setCities] = useState<City[]>([]);
  const [experienceCount, setExperienceCount] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [matchedCity, setMatchedCity] = useState<City | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCities(), getProductionStats()]).then(([cityRows, stats]) => {
      if (cancelled) return;
      setCities(cityRows ?? []);
      setExperienceCount(stats?.experiences ?? null);

      const match = window.location.pathname.match(/^\/city\/([^/]+)$/);
      if (!match) return;
      const raw = decodeURIComponent(match[1]);
      const name = raw.includes("-") ? raw.slice(raw.indexOf("-") + 1) : raw;
      const hit = (cityRows ?? []).find((city) =>
        city.code.toLowerCase() === raw.toLowerCase() ||
        city.name === name || city.name === raw ||
        city.iata?.toUpperCase() === raw.toUpperCase() ||
        city.pinyin?.toLowerCase() === raw.toLowerCase()
      );
      setMatchedCity(hit ?? null);
    });
    return () => { cancelled = true; };
  }, []);

  const recommended = useMemo(
    () => cities.filter((city) => city.trust?.review_status === "VERIFIED").slice(0, 2),
    [cities]
  );

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (value) router.push(`/experiences?q=${encodeURIComponent(value)}`);
  }

  return (
    <>
      <NavBar />
      <main className="mx-auto flex min-h-[70vh] max-w-3xl flex-col items-center justify-center px-4 py-12 text-center sm:px-6 lg:px-8">
        <div className="relative">
          <div className="text-[120px] font-extrabold leading-none text-primary-50 sm:text-[160px]">404</div>
          <div className="absolute inset-0 flex items-center justify-center"><Plane className="h-12 w-12 text-primary opacity-50" /></div>
        </div>
        <h1 className="-mt-6 text-2xl font-bold text-ink-900 sm:text-3xl">没有找到对应的保障页面</h1>
        <p className="mt-2 max-w-md text-sm text-ink-500">
          {matchedCity ? `找到匹配航站：${matchedCity.name}（${matchedCity.iata || "代码待核"}）` : "链接可能已迁移。可搜索经验，或从已核验航站继续。"}
        </p>

        <form onSubmit={submit} className="mt-6 flex w-full max-w-md flex-col gap-2 sm:flex-row">
          <label className="sr-only" htmlFor="not-found-search">搜索经验</label>
          <input id="not-found-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索城市、机型、件号或经验" className="flex-1 rounded-md border border-ink-100 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
          <button type="submit" className="inline-flex items-center justify-center gap-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"><Search className="h-4 w-4" />搜索</button>
        </form>

        {matchedCity && (
          <Link href={`/city/${encodeURIComponent(matchedCity.code)}`} className="mt-5 rounded-md border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary-50">
            打开 {matchedCity.name} →
          </Link>
        )}

        <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
          {recommended.map((city) => (
            <Link key={city.code} href={`/city/${encodeURIComponent(city.code)}`} className="rounded-xl border border-ink-100 bg-white p-4 text-left shadow-soft hover:border-primary">
              <div className="text-xs font-medium text-primary">已核验航站</div>
              <div className="mt-1 text-sm font-semibold text-ink-900">{city.name}</div>
              <div className="mt-0.5 text-xs text-ink-500">{city.iata || "—"} · {city.region} · {city.status}</div>
            </Link>
          ))}
          <Link href="/experiences" className="rounded-xl border border-ink-100 bg-white p-4 text-left shadow-soft hover:border-primary">
            <div className="text-xs font-medium text-primary">保障经验</div>
            <div className="mt-1 text-sm font-semibold text-ink-900">经验库</div>
            <div className="mt-0.5 text-xs text-ink-500">{experienceCount === null ? "正在读取真实数据" : `${experienceCount} 条可发布经验`}</div>
          </Link>
        </div>

        <Link href="/" className="mt-8 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-primary"><Home className="h-4 w-4" />返回首页</Link>
      </main>
    </>
  );
}
