"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, Building2, Globe, Phone, Mail, Filter, Plane } from "lucide-react";
import { getAirlines, searchAirlines } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Airline } from "@/lib/types";

const ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

const ALLIANCES = [
  { key: "", label: "全部联盟" },
  { key: "星空联盟", label: "星空联盟" },
  { key: "天合联盟", label: "天合联盟" },
  { key: "寰宇一家", label: "寰宇一家" },
];

/**
 * 航司列表页 (Sprint C)
 *  - 顶部搜索框 (按 IATA / 中文名 / 英文名 / 简称)
 *  - 字母 sidebar A-Z 快速跳转
 *  - 联盟 filter chip
 *  - 卡片 grid (每航司一张: IATA + 中文名 + 基地 + 机队)
 */
export function AirlinesClient() {
  const [airlines, setAirlines] = useState<Airline[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [activeLetter, setActiveLetter] = useState<string | null>(null);
  const [activeAlliance, setActiveAlliance] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await getAirlines();
      if (cancelled) return;
      setAirlines(data ?? []);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // 按 query 即时搜索 (debounce 不需要 — 数据小, 25 条)
  const searched = useMemo<Airline[]>(() => {
    if (!query.trim()) return airlines;
    const k = query.trim().toLowerCase();
    return airlines.filter((a) => {
      const hay = `${a.iata} ${a.icao} ${a.name_cn} ${a.name_en} ${a.name_short || ""}`.toLowerCase();
      return hay.includes(k);
    });
  }, [airlines, query]);

  // 按字母过滤
  const letterFiltered = useMemo<Airline[]>(() => {
    if (!activeLetter) return searched;
    const l = activeLetter.toUpperCase();
    return searched.filter(
      (a) => a.iata.toUpperCase().startsWith(l) || a.name_cn.startsWith(activeLetter)
    );
  }, [searched, activeLetter]);

  // 按联盟过滤
  const finalList = useMemo<Airline[]>(() => {
    if (!activeAlliance) return letterFiltered;
    return letterFiltered.filter((a) => {
      // "无（低成本）" / "无（民营）" 等统一归为 "无"
      const allianceBase = a.alliance.startsWith("无") ? "无" : a.alliance;
      return allianceBase === activeAlliance;
    });
  }, [letterFiltered, activeAlliance]);

  // 按 IATA 字母索引
  const byAlpha = useMemo(() => {
    const m: Record<string, Airline[]> = {};
    for (const a of searched) {
      const k = a.iata.charAt(0).toUpperCase();
      (m[k] = m[k] || []).push(a);
    }
    for (const k of Object.keys(m)) {
      m[k].sort((a, b) => a.iata.localeCompare(b.iata));
    }
    return m;
  }, [searched]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <header className="mb-6">
        <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-500">
          互援资源
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900 sm:text-3xl">
          中国主要航司
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          {loading
            ? "加载中…"
            : `${airlines.length} 家航司 · 真实基地 + 机队 + 联盟 + AOG 联系方式 · 数据源: AOG 知识库 + 公开资料`}
        </p>
      </header>

      {/* 搜索框 + 联盟 filter */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="按 IATA / 中文名 / 英文名 / 简称搜索 (例: CA / 国航 / Air China / 春)"
            className="w-full rounded-md border border-ink-100 bg-white py-2 pl-10 pr-3 text-sm placeholder:text-ink-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <Filter className="h-3.5 w-3.5 text-ink-500" />
          {ALLIANCES.map((a) => (
            <button
              key={a.key}
              type="button"
              onClick={() => setActiveAlliance(a.key)}
              className={cn(
                "rounded-full px-2.5 py-1 transition",
                activeAlliance === a.key
                  ? "bg-primary text-white"
                  : "border border-ink-100 bg-white text-ink-700 hover:border-ink-300"
              )}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>

      {/* 字母 sidebar + 卡片 grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[80px,1fr]">
        {/* 字母索引 */}
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <div className="grid grid-cols-7 gap-1 lg:grid-cols-2">
            {ALPHA.map((l) => {
              const list = byAlpha[l] || [];
              const has = list.length > 0;
              const isActive = activeLetter === l;
              return (
                <button
                  key={l}
                  type="button"
                  disabled={!has}
                  onClick={() =>
                    setActiveLetter((prev) => (prev === l ? null : l))
                  }
                  className={cn(
                    "relative flex h-9 items-center justify-center rounded-md text-xs font-semibold tabular-nums transition",
                    has
                      ? isActive
                        ? "bg-primary text-white shadow-sm"
                        : "bg-ink-50 text-ink-900 hover:bg-primary-50 hover:text-primary"
                      : "cursor-not-allowed bg-ink-50/40 text-ink-300"
                  )}
                  title={has ? `${l} · ${list.length} 家` : `${l} 无航司`}
                >
                  {l}
                  {has && !isActive && (
                    <span className="absolute -right-0.5 -top-0.5 grid h-3.5 min-w-[14px] place-items-center rounded-full bg-ink-200 px-0.5 text-[9px] font-medium text-ink-600">
                      {list.length}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          {activeLetter && (
            <button
              type="button"
              onClick={() => setActiveLetter(null)}
              className="mt-2 w-full text-center text-[11px] text-primary hover:underline"
            >
              清除字母筛选
            </button>
          )}
        </aside>

        {/* 卡片 grid */}
        <div>
          {loading ? (
            <div className="grid h-40 place-items-center text-sm text-ink-500">
              加载中…
            </div>
          ) : finalList.length === 0 ? (
            <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-8 text-center text-sm text-ink-500">
              没有匹配的航司 — 试试清除搜索或联盟筛选
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {finalList.map((a) => (
                <AirlineCard key={a.iata} airline={a} />
              ))}
            </div>
          )}

          {!loading && (
            <div className="mt-4 text-center text-xs text-ink-500">
              显示 {finalList.length} / {airlines.length} 家
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

function AirlineCard({ airline }: { airline: Airline }) {
  const allianceShort = airline.alliance.startsWith("无")
    ? "无联盟"
    : airline.alliance;
  const mainHub = airline.hubs.find((h) => h.type === "hub") || airline.hubs[0];

  return (
    <Link
      href={`/airlines/${encodeURIComponent(airline.iata)}`}
      className="group flex flex-col rounded-xl border border-ink-100 bg-white p-4 transition hover:border-ink-300 hover:shadow-sm"
    >
      {/* Top: IATA placeholder + name */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          {/* IATA logo placeholder (文字占位) */}
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary-50 to-primary text-primary shadow-sm">
            <span className="text-sm font-bold tracking-wider">
              {airline.iata}
            </span>
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-ink-900 group-hover:text-primary">
              {airline.name_cn}
            </div>
            <div className="truncate text-[11px] text-ink-500">
              {airline.name_en}
            </div>
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
            allianceShort === "星空联盟" && "bg-secondary/10 text-secondary",
            allianceShort === "天合联盟" && "bg-primary-50 text-primary-700",
            allianceShort === "寰宇一家" && "bg-warning-50 text-warning-700",
            allianceShort === "无联盟" && "bg-ink-100 text-ink-600"
          )}
        >
          {allianceShort}
        </span>
      </div>

      {/* Hub + fleet */}
      <div className="space-y-1.5 text-xs">
        <div className="flex items-center gap-1.5 text-ink-700">
          <Building2 className="h-3 w-3 shrink-0 text-ink-400" />
          <span className="truncate">
            {mainHub
              ? `${mainHub.city?.name || mainHub.iata}${mainHub.note ? ` · ${mainHub.note}` : ""}`
              : "—"}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-ink-700">
          <Plane className="h-3 w-3 shrink-0 text-ink-400" />
          <span className="tabular-nums">机队 {airline.fleet_size} 架</span>
        </div>
        {airline.hubs.length > 1 && (
          <div className="flex items-center gap-1.5 text-ink-500">
            <Globe className="h-3 w-3 shrink-0 text-ink-400" />
            <span className="truncate">
              另 {airline.hubs.length - 1} 个基地 / 关注点
            </span>
          </div>
        )}
      </div>

      {/* AOG contact (if public) */}
      {airline.aog_contact?.phone && (
        <div className="mt-3 flex items-center gap-1.5 border-t border-ink-100 pt-2 text-[11px] text-ink-500">
          <Phone className="h-3 w-3" />
          <span className="font-mono tabular-nums">
            {airline.aog_contact.phone}
          </span>
        </div>
      )}
    </Link>
  );
}
