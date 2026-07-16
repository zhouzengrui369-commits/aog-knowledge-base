"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { NavBar } from "@/components/nav-bar";
import { CityTabs } from "@/components/city-tabs";
import { getCity, getCities } from "@/lib/api";
import { normalizeCityStatus, STATUS_LABEL, cn, fmtDate } from "@/lib/utils";
import { Download, Bot, ChevronLeft, AlertTriangle } from "lucide-react";
import type { City } from "@/lib/types";

export function CityDetailClient({ code }: { code: string }) {
  const [city, setCity] = useState<City | null | undefined>(undefined);
  const [related, setRelated] = useState<City[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const c = await getCity(code);
      if (cancelled) return;
      setCity(c);
      if (c) {
        const all = await getCities();
        if (cancelled) return;
        const others = all.filter((x) => x.code !== c.code);
        const sameRegion = others.filter((x) => x.region === c.region).slice(0, 3);
        const fill = others.filter((x) => x.region !== c.region).slice(0, 3 - sameRegion.length);
        setRelated([...sameRegion, ...fill].slice(0, 3));
      }
    })();
    return () => { cancelled = true; };
  }, [code]);

  if (city === undefined) {
    return (
      <>
        <NavBar />
        <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
          <div className="text-ink-500 text-sm">加载中…</div>
        </div>
      </>
    );
  }
  if (city === null) {
    return (
      <>
        <NavBar />
        <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
          <div className="text-ink-700">城市未找到</div>
          <Link href="/" className="text-sm text-primary hover:underline mt-2 inline-block">
            返回首页
          </Link>
        </div>
      </>
    );
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
            {related.length > 0 && (
              <div className="rounded-lg border border-surface-3 bg-white p-4 space-y-3">
                <h3 className="text-sm font-semibold text-ink-800">相关航站</h3>
                <div className="space-y-2">
                  {related.map((c) => (
                    <Link key={c.code} href={`/city/${encodeURIComponent(c.code)}`} className="block rounded-md p-2 hover:bg-surface-2">
                      <div className="text-sm font-medium text-ink-800">{c.name}</div>
                      <div className="text-xs text-ink-500">{c.region} · {c.iata || "—"}</div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
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
