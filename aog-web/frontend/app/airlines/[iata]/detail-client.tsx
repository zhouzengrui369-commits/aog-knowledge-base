"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Building2,
  Globe,
  Phone,
  Mail,
  Plane,
  ChevronRight,
  ChevronLeft,
  AlertTriangle,
  CheckCircle2,
  MapPin,
  Hash,
  Users,
} from "lucide-react";
import { getAirline, getAirlines } from "@/lib/api";
import { cn, fmtDate } from "@/lib/utils";
import type { Airline, AirlineHub, City } from "@/lib/types";

export function AirlineDetailClient({ iata }: { iata: string }) {
  const [airline, setAirline] = useState<Airline | null | undefined>(undefined);
  const [allAirlines, setAllAirlines] = useState<Airline[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [a, all] = await Promise.all([
        getAirline(iata),
        getAirlines(),
      ]);
      if (cancelled) return;
      setAirline(a);
      setAllAirlines(all ?? []);
    })();
    return () => {
      cancelled = true;
    };
  }, [iata]);

  if (airline === undefined) {
    return (
      <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
        <div className="text-sm text-ink-500">加载中…</div>
      </div>
    );
  }

  if (airline === null) {
    return (
      <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
        <div className="rounded-lg border border-ink-100 bg-white p-6">
          <div className="text-ink-700">未找到 IATA = {iata} 的航司</div>
          <Link
            href="/airlines"
            className="mt-3 inline-block text-sm text-primary hover:underline"
          >
            返回航司列表
          </Link>
        </div>
      </div>
    );
  }

  // 容错: hub 结构异常不崩
  let safeHubs: AirlineHub[] = [];
  let safeAirlines: Airline[] = [];
  try {
    safeHubs = Array.isArray(airline.hubs) ? airline.hubs : [];
    safeAirlines = Array.isArray(allAirlines) ? allAirlines : [];
  } catch (e) {
    console.error("[AirlineDetailClient] render error:", e);
  }

  const hubCount = safeHubs.filter((h) => h.type === "hub").length;
  const focusCount = safeHubs.filter((h) => h.type === "focus").length;
  const allianceShort = airline.alliance?.startsWith("无")
    ? "无联盟"
    : airline.alliance;

  // 同联盟 + 随机推荐 3 个其它航司
  const related = safeAirlines
    .filter((a) => a.iata !== airline.iata)
    .filter((a) => {
      const a1 = a.alliance?.startsWith("无") ? "无" : a.alliance;
      const a2 = airline.alliance?.startsWith("无") ? "无" : airline.alliance;
      return a1 === a2;
    })
    .slice(0, 3);

  return (
    <main className="mx-auto max-w-7xl px-4 pt-6 pb-12 sm:px-6 lg:px-8">
      {/* Breadcrumb */}
      <nav className="mb-4 flex items-center gap-1.5 text-xs text-ink-500">
        <Link href="/" className="hover:text-primary">
          AOG 知识库
        </Link>
        <ChevronRight className="h-3 w-3 text-ink-300" />
        <Link href="/airlines" className="hover:text-primary">
          航司互援资源
        </Link>
        <ChevronRight className="h-3 w-3 text-ink-300" />
        <span className="text-ink-700">
          {airline.name_short || airline.name_cn}
        </span>
      </nav>

      {/* Hero card */}
      <header className="rounded-xl border border-ink-100 bg-white p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2 text-xs text-ink-500">
              <span className="rounded bg-ink-50 px-1.5 py-0.5 font-mono text-[11px] tracking-wide">
                {airline.iata}
              </span>
              <span>·</span>
              <span className="font-mono tracking-wide">{airline.icao}</span>
              <span>·</span>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
                  allianceShort === "星空联盟" && "bg-secondary/10 text-secondary",
                  allianceShort === "天合联盟" && "bg-primary-50 text-primary-700",
                  allianceShort === "寰宇一家" && "bg-warning-50 text-warning-700",
                  allianceShort === "无联盟" && "bg-ink-100 text-ink-600"
                )}
              >
                {allianceShort}
              </span>
              {airline.verified && (
                <span className="inline-flex items-center gap-0.5 rounded-full bg-success-50 px-2 py-0.5 text-[11px] font-medium text-success-700">
                  <CheckCircle2 className="h-3 w-3" />
                  已核验
                </span>
              )}
            </div>
            <h1 className="flex items-center gap-3 text-3xl font-semibold tracking-tight text-ink-900 sm:text-4xl">
              {/* IATA logo placeholder */}
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary-50 to-primary text-primary shadow-sm">
                <span className="text-base font-bold tracking-wider">
                  {airline.iata}
                </span>
              </span>
              {airline.name_cn}
            </h1>
            <p className="mt-1 text-sm text-ink-500">
              {airline.name_en}
              {airline.name_short && (
                <span className="ml-2 text-ink-400">
                  · 简称: {airline.name_short}
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Quick stats */}
        <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-ink-100 bg-ink-100 sm:grid-cols-4">
          <Stat
            label="机队规模"
            value={airline.fleet_size.toLocaleString()}
            suffix="架"
            icon={<Plane className="h-3.5 w-3.5" />}
          />
          <Stat
            label="主基地"
            value={hubCount}
            suffix="个"
            icon={<Building2 className="h-3.5 w-3.5" />}
          />
          <Stat
            label="关注点"
            value={focusCount}
            suffix="个"
            icon={<MapPin className="h-3.5 w-3.5" />}
          />
          <Stat
            label="联盟"
            value={allianceShort}
            icon={<Globe className="h-3.5 w-3.5" />}
          />
        </div>
      </header>

      {/* Body grid */}
      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[1fr,320px]">
        {/* Hubs (left) */}
        <section>
          <h2 className="mb-4 text-base font-semibold text-ink-900">
            基地机场
          </h2>
          {safeHubs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-6 text-center text-sm text-ink-500">
              暂无基地数据
            </div>
          ) : (
            <ul className="space-y-2">
              {safeHubs.map((h, i) => (
                <HubRow key={`${h.iata}-${i}`} hub={h} />
              ))}
            </ul>
          )}
        </section>

        {/* Sidebar: 联系方式 + 数据来源 (right) */}
        <aside className="space-y-4">
          {airline.aog_contact &&
            (airline.aog_contact.phone || airline.aog_contact.email) && (
              <div className="rounded-lg border border-ink-100 bg-white p-5">
                <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-ink-500">
                  <Phone className="h-3.5 w-3.5" />
                  AOG 联系
                </div>
                <div className="space-y-2">
                  {airline.aog_contact.phone && (
                    <a
                      href={`tel:${airline.aog_contact.phone.replace(/\s/g, "")}`}
                      className="flex items-start gap-1.5 text-sm text-primary hover:underline"
                    >
                      <Phone className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span className="font-mono tabular-nums">
                        {airline.aog_contact.phone}
                      </span>
                    </a>
                  )}
                  {airline.aog_contact.email && (
                    <a
                      href={`mailto:${airline.aog_contact.email}`}
                      className="flex items-start gap-1.5 text-sm text-ink-700 hover:text-primary"
                    >
                      <Mail className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{airline.aog_contact.email}</span>
                    </a>
                  )}
                </div>
                <p className="mt-3 text-[11px] text-ink-400">
                  * 公开资料 · 来源航司官网 / 民航局 / 行业资料
                </p>
              </div>
            )}

          {airline.headquarters && (
            <div className="rounded-lg border border-ink-100 bg-white p-5">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-ink-500">
                <MapPin className="h-3.5 w-3.5" />
                总部
              </div>
              <div className="text-sm text-ink-900">{airline.headquarters}</div>
            </div>
          )}

          {airline.website && (
            <div className="rounded-lg border border-ink-100 bg-white p-5">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-ink-500">
                <Globe className="h-3.5 w-3.5" />
                官网
              </div>
              <a
                href={`https://${airline.website.replace(/^https?:\/\//, "")}`}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all text-sm text-primary hover:underline"
              >
                {airline.website}
              </a>
            </div>
          )}

          {/* 数据来源 */}
          {airline.data_source && (
            <div className="rounded-lg border border-ink-100 bg-ink-50/50 p-5">
              <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-ink-500">
                <Hash className="h-3 w-3" />
                数据来源
              </div>
              <div className="text-xs text-ink-700">{airline.data_source}</div>
              {airline.verified_at && (
                <div className="mt-1.5 text-[10px] text-ink-500">
                  核验日期 · {fmtDate(airline.verified_at)}
                </div>
              )}
            </div>
          )}
        </aside>
      </div>

      {/* Related airlines (same alliance) */}
      {related.length > 0 && (
        <section className="mt-10 border-t border-ink-100 pt-8">
          <h3 className="mb-4 text-sm font-medium text-ink-700">
            同联盟其它航司
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {related.map((a) => (
              <Link
                key={a.iata}
                href={`/airlines/${encodeURIComponent(a.iata)}`}
                className="group flex items-center justify-between gap-3 rounded-lg border border-ink-100 bg-white p-4 transition hover:border-ink-300"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-gradient-to-br from-primary-50 to-primary text-xs font-bold text-primary">
                    {a.iata}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-ink-900 group-hover:text-primary">
                      {a.name_short || a.name_cn}
                    </div>
                    <div className="truncate text-[11px] text-ink-500">
                      {a.iata} ·{" "}
                      {a.alliance.startsWith("无") ? "无联盟" : a.alliance}
                    </div>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-primary" />
              </Link>
            ))}
          </div>
        </section>
      )}

      <div className="mt-8 text-center">
        <Link
          href="/airlines"
          className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-primary"
        >
          <ChevronLeft className="h-3 w-3" />
          返回航司列表
        </Link>
      </div>
    </main>
  );
}

function Stat({
  label,
  value,
  suffix,
  icon,
}: {
  label: string;
  value: string | number;
  suffix?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="bg-white p-4">
      <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-ink-500">
        {icon}
        {label}
      </div>
      <div className="text-2xl font-semibold tabular-nums tracking-tight text-ink-900">
        {value}
        {suffix && (
          <span className="ml-0.5 text-sm font-normal text-ink-500">
            {suffix}
          </span>
        )}
      </div>
    </div>
  );
}

function HubRow({ hub }: { hub: AirlineHub }) {
  const isHub = hub.type === "hub";
  const city = hub.city;
  const cityName = city?.name || hub.iata;
  const cityStatus = city?.status;
  const isPaused = cityStatus === "暂停" || cityStatus === "已废";

  const inner = (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg border bg-white p-4 transition",
        isHub
          ? "border-ink-100 hover:border-primary"
          : "border-ink-100 hover:border-ink-300"
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <div
          className={cn(
            "grid h-10 w-10 shrink-0 place-items-center rounded-md",
            isHub
              ? "bg-primary-50 text-primary-700"
              : "bg-ink-50 text-ink-700"
          )}
        >
          <Building2 className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-sm font-medium text-ink-900">
            {cityName}
            {isPaused && (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-warning-50 px-1.5 py-0.5 text-[10px] font-medium text-warning-700">
                <AlertTriangle className="h-2.5 w-2.5" />
                {cityStatus}
              </span>
            )}
          </div>
          <div className="mt-0.5 text-xs text-ink-500 tabular-nums">
            {hub.iata}
            {hub.note ? ` · ${hub.note}` : ""}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
            isHub
              ? "bg-primary text-white"
              : "bg-ink-100 text-ink-700"
          )}
        >
          {isHub ? "主基地" : "关注点"}
        </span>
        {city && !isPaused && (
          <ChevronRight className="h-4 w-4 text-ink-300" />
        )}
      </div>
    </div>
  );

  // 有 city + 非暂停 → 可跳 city detail
  if (city && !isPaused) {
    return (
      <li>
        <Link href={`/city/${encodeURIComponent(city.code)}`}>{inner}</Link>
      </li>
    );
  }

  // city 缺失 / 暂停 → 纯文本
  return <li>{inner}</li>;
}
