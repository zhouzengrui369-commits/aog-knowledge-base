"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Bot, ChevronLeft, ChevronRight, Clock, Eye, Package, Plane } from "lucide-react";
import { NavBar } from "@/components/nav-bar";
import { CityTabs } from "@/components/city-tabs";
import { getCities, getCity } from "@/lib/api";
import { fmtDate, normalizeCityStatus, STATUS_LABEL } from "@/lib/utils";
import type { City } from "@/lib/types";

function decodeCode(value: string): string {
  let output = value;
  for (let index = 0; index < 2; index += 1) {
    try {
      const decoded = decodeURIComponent(output);
      if (decoded === output) break;
      output = decoded;
    } catch { break; }
  }
  return output;
}

export function CityDetailClient({ code }: { code: string }) {
  const [city, setCity] = useState<City | null | undefined>(undefined);
  const [related, setRelated] = useState<City[]>([]);

  useEffect(() => {
    let cancelled = false;
    const normalized = decodeCode(code);
    (async () => {
      const candidates = [normalized, normalized.charAt(0).toUpperCase() + normalized.slice(1)];
      let found: City | null = null;
      for (const candidate of [...new Set(candidates)]) {
        found = await getCity(candidate);
        if (found) break;
      }
      const all = await getCities();
      if (!found) {
        const name = normalized.includes("-") ? normalized.slice(normalized.indexOf("-") + 1) : normalized;
        found = all.find((item) => item.code.toLowerCase() === normalized.toLowerCase() || item.name === name || item.iata?.toUpperCase() === normalized.toUpperCase()) || null;
      }
      if (cancelled) return;
      setCity(found);
      if (found) {
        const sameRegion = all.filter((item) => item.code !== found!.code && item.region === found!.region);
        const fallback = all.filter((item) => item.code !== found!.code && item.region !== found!.region);
        setRelated([...sameRegion, ...fallback].slice(0, 3));
      }
    })();
    return () => { cancelled = true; };
  }, [code]);

  if (city === undefined) return <><NavBar /><div className="mx-auto max-w-7xl px-4 py-12 text-sm text-ink-500">加载中…</div></>;
  if (city === null) return <><NavBar /><div className="mx-auto max-w-3xl px-4 py-12"><h1 className="text-xl font-semibold">城市未找到</h1><Link href="/" className="mt-3 inline-block text-primary hover:underline">返回首页</Link></div></>;

  const reviewStatus = city.trust?.review_status || "UNVERIFIED";
  const verified = city.data_available !== false && reviewStatus === "VERIFIED";
  const status = STATUS_LABEL[normalizeCityStatus(city.status)] || { cls: "", text: city.status };
  const viewCount = city.view_count || 0;

  function askCity() {
    window.dispatchEvent(new CustomEvent("aog:ask", { detail: { q: `请基于已核验资料说明 ${city!.name}（${city!.iata || "代码待核"}）的 AOG 保障要点。` } }));
  }

  return (
    <>
      <NavBar />
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <nav className="flex items-center gap-1.5 text-xs text-ink-500"><Link href="/" className="hover:text-primary">AOG 知识库</Link><ChevronRight className="h-3 w-3" /><span>{city.name}</span></nav>
      </div>

      {normalizeCityStatus(city.status) === "暂停" && <div className="mt-4 border-y border-warning-200 bg-warning-50"><div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-3 text-sm text-warning-700"><AlertTriangle className="h-4 w-4" /><strong>该站保障状态为暂停</strong><span>请使用替代航站或联系维修控制中心确认。</span></div></div>}

      <div className={`mt-4 border-y ${verified ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"}`}>
        <div className="mx-auto max-w-7xl px-4 py-3 text-sm sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center gap-2"><strong>{verified ? "已核验数据" : "数据未审核，禁止用于实际处置"}</strong><span className="rounded-full bg-white/70 px-2 py-0.5 text-xs">{reviewStatus}</span>{city.trust?.confidence != null && <span className="text-xs">置信度 {(city.trust.confidence * 100).toFixed(0)}%</span>}</div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-600">{city.trust?.source_document && <span>来源：{city.trust.source_document}</span>}{city.trust?.reviewed_by && <span>审核：{city.trust.reviewed_by}</span>}{city.trust?.updated_at && <span>更新：{fmtDate(city.trust.updated_at)}</span>}</div>
        </div>
      </div>

      <header className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-soft">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
            <div>
              <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.cls}`}>{status.text}</span><span className="rounded-full bg-ink-50 px-2.5 py-0.5 text-xs text-ink-600">城市：{city.name}</span><span className="rounded-full bg-ink-50 px-2.5 py-0.5 text-xs text-ink-600">机场：{city.airport || "待核"}</span></div>
              <h1 className="mt-3 text-3xl font-bold text-ink-900">{city.name} <span className="font-mono text-xl text-ink-400">{city.iata || "—"}</span></h1>
              <p className="mt-2 text-sm text-ink-500">{city.region} · 城市与机场名称分开管理，三字代码以审核数据为准。</p>
            </div>
            <button type="button" onClick={askCity} className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"><Bot className="h-4 w-4" />问 AI</button>
          </div>
          <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-ink-100 bg-ink-100 sm:grid-cols-4">
            <Stat icon={<Eye className="h-4 w-4" />} label="访问次数" value={viewCount > 1 ? String(viewCount) : "首次访问"} />
            <Stat icon={<Plane className="h-4 w-4" />} label="已核验机型" value={verified ? `${city.fleet?.length || 0} 种` : "需审核"} />
            <Stat icon={<Package className="h-4 w-4" />} label="已核验备件" value={verified ? `${city.parts?.length || 0} 项` : "需审核"} />
            <Stat icon={<Clock className="h-4 w-4" />} label="数据状态" value={reviewStatus} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr,300px]">
          <CityTabs city={city} />
          <aside className="space-y-4">
            <div className="rounded-lg border border-ink-100 bg-white p-5">
              <div className="text-xs font-semibold uppercase tracking-wider text-ink-500">处置目标与责任边界</div>
              <div className="mt-3 text-lg font-semibold text-ink-900">30 分钟内完成首次信息核对</div>
              <p className="mt-2 text-xs leading-5 text-ink-500">执行责任方：当班航材 AOG 工程师。该时间是内部处置目标，不代表航司、机场、供应商或本平台对外 SLA；实际承诺以书面协议为准。</p>
            </div>
            <div className="rounded-lg border border-ink-100 bg-white p-5 text-xs leading-5 text-ink-500">
              <strong className="text-ink-700">相关航站算法</strong><p className="mt-1">优先推荐同地区航站，不足时按现行列表补足。该标签不代表互援协议或库存可用。</p>
            </div>
          </aside>
        </div>

        {related.length > 0 && <section className="mt-10 border-t border-ink-100 pt-8"><h2 className="mb-4 text-sm font-medium text-ink-700">相关航站 <span className="ml-1 rounded bg-ink-100 px-2 py-0.5 text-[10px]">同地区优先</span></h2><div className="grid gap-3 sm:grid-cols-3">{related.map((item) => <Link key={item.code} href={`/city/${encodeURIComponent(item.code)}`} className="flex items-center justify-between rounded-lg border border-ink-100 bg-white p-4 hover:border-primary"><div><div className="text-sm font-medium">{item.name}</div><div className="mt-1 text-xs text-ink-500">{item.iata || "—"} · {item.region} · {item.trust?.review_status || "UNVERIFIED"}</div></div><ChevronRight className="h-4 w-4" /></Link>)}</div></section>}
        <Link href="/" className="mt-8 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-primary"><ChevronLeft className="h-3 w-3" />返回首页</Link>
      </main>
    </>
  );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <div className="bg-white p-4"><div className="flex items-center gap-2 text-lg font-semibold text-ink-900">{icon}{value}</div><div className="mt-1 text-xs text-ink-500">{label}</div></div>;
}
