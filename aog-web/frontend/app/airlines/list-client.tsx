"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, Plane, Search, ShieldCheck } from "lucide-react";
import { getAirlines } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Airline } from "@/lib/types";

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
const ALLIANCES = ["全部", "星空联盟", "天合联盟", "寰宇一家", "无"];

export function AirlinesClient() {
  const [airlines, setAirlines] = useState<Airline[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [letter, setLetter] = useState<string | null>(null);
  const [alliance, setAlliance] = useState("全部");

  useEffect(() => {
    let cancelled = false;
    getAirlines().then((rows) => { if (!cancelled) { setAirlines(rows ?? []); setLoading(false); } });
    return () => { cancelled = true; };
  }, []);

  const list = useMemo(() => airlines.filter((item) => {
    const needle = query.trim().toLowerCase();
    if (needle && !`${item.iata} ${item.icao} ${item.name_cn} ${item.name_en} ${item.name_short || ""}`.toLowerCase().includes(needle)) return false;
    if (letter && !item.iata.startsWith(letter)) return false;
    if (alliance !== "全部") {
      const normalized = item.alliance.startsWith("无") ? "无" : item.alliance;
      if (alliance === "星空联盟" ? !normalized.startsWith("星空联盟") : normalized !== alliance) return false;
    }
    return true;
  }), [airlines, query, letter, alliance]);

  const lettersWithData = useMemo(() => new Set(airlines.map((item) => item.iata.charAt(0))), [airlines]);
  const verified = airlines.filter((item) => item.verification_status === "VERIFIED").length;
  const conflicts = airlines.filter((item) => item.verification_status === "CONFLICT").length;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header><div className="text-xs font-medium uppercase tracking-wider text-ink-500">互援资源</div><h1 className="mt-1 text-3xl font-semibold text-ink-900">中国主要航司</h1><p className="mt-2 text-sm text-ink-500">{loading ? "加载中…" : `${airlines.length} 家运营人 · ${verified} 家通过当前登记核验 · ${conflicts} 家联系方式冲突已隔离`}</p></header>
      <div className="mt-6 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-ink-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 IATA、中文名或英文名" className="w-full rounded-md border border-ink-100 py-2 pl-9 pr-3 text-sm focus:border-primary focus:outline-none" /></div>
        <div className="flex flex-wrap gap-1.5">{ALLIANCES.map((item) => <button key={item} type="button" onClick={() => setAlliance(item)} className={cn("rounded-full border px-3 py-1 text-xs", alliance === item ? "border-primary bg-primary text-white" : "border-ink-200 bg-white text-ink-700")}>{item}</button>)}</div>
      </div>
      <div className="mt-5 flex flex-wrap gap-1">{ALPHABET.map((item) => {
        const has = lettersWithData.has(item);
        return <button key={item} type="button" disabled={!has} onClick={() => setLetter((current) => current === item ? null : item)} title={has ? `${item} 有航司数据` : `${item} 暂无航司数据`} className={cn("grid h-8 w-8 place-items-center rounded text-xs font-semibold", !has ? "cursor-not-allowed bg-ink-50 text-ink-300" : letter === item ? "bg-primary text-white" : "bg-ink-50 text-ink-800 hover:bg-primary-50")}>{item}</button>;
      })}</div>

      {loading ? <div className="py-16 text-center text-sm text-ink-500">加载中…</div> : list.length === 0 ? <div className="mt-8 rounded-lg border border-dashed border-ink-200 p-12 text-center text-sm text-ink-500">当前筛选无数据；空字母已显式禁用。</div> : <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{list.map((item) => <AirlineCard key={item.iata} airline={item} />)}</div>}
    </main>
  );
}

function AirlineCard({ airline }: { airline: Airline }) {
  const hub = airline.hubs.find((item) => item.type === "hub") || airline.hubs[0];
  const conflict = airline.verification_status === "CONFLICT";
  return <article className="rounded-xl border border-ink-100 bg-white p-4 shadow-soft">
    <div className="flex items-start justify-between gap-3"><div className="flex items-center gap-3"><span className="grid h-12 w-12 place-items-center rounded-lg bg-primary-50 font-bold text-primary">{airline.iata}</span><div><h2 className="font-semibold text-ink-900">{airline.name_cn}</h2><p className="text-xs text-ink-500">{airline.name_en} · {airline.icao}</p></div></div><span className="rounded-full bg-ink-50 px-2 py-0.5 text-[10px] text-ink-600">{airline.alliance}</span></div>
    <div className="mt-4 space-y-2 text-xs text-ink-600"><p className="flex items-center gap-1"><Building2 className="h-3.5 w-3.5" />{hub ? `${hub.city?.name || hub.iata} · ${hub.note || hub.type}` : "基地待核"}</p><p className="flex items-center gap-1"><Plane className="h-3.5 w-3.5" />机队 {airline.fleet_size} 架</p></div>
    <div className={`mt-4 rounded-md p-3 text-xs ${conflict ? "bg-amber-50 text-amber-900" : airline.verification_status === "VERIFIED" ? "bg-green-50 text-green-800" : "bg-ink-50 text-ink-600"}`}>
      {conflict ? <><AlertTriangle className="mr-1 inline h-3.5 w-3.5" />联系方式冲突，已从公共 API 移除</> : airline.verification_status === "VERIFIED" ? <><ShieldCheck className="mr-1 inline h-3.5 w-3.5" />核验于 {airline.verified_at}</> : "联系方式尚未完成生产核验"}
      {!conflict && airline.aog_contact?.phone && <div className="mt-2 font-mono">{airline.aog_contact.phone}</div>}
    </div>
  </article>;
}
