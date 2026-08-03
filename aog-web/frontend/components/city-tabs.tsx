"use client";

import * as React from "react";
import { Info, Lock, ShieldAlert } from "lucide-react";
import type { City, ContactPermission } from "@/lib/types";
import { cn } from "@/lib/utils";

type TabKey = "plan" | "contacts" | "parts" | "logistics" | "warehouse";

interface ContactViewModel {
  id: string;
  org: string;
  scope: string;
  phone: string;
  email?: string;
  permission: ContactPermission;
  redacted: boolean;
}

function permission(value: unknown): ContactPermission {
  return value === "public" || value === "internal" || value === "restricted" ? value : "restricted";
}

function contacts(city: City): ContactViewModel[] {
  const raw = city.contacts?.length ? city.contacts : city.contacts_mockup || [];
  const seen = new Set<string>();
  const output: ContactViewModel[] = [];
  for (const item of raw as Array<Record<string, unknown>>) {
    const phones = Array.isArray(item.phone)
      ? item.phone.filter((value): value is string => typeof value === "string").join(" / ")
      : typeof item.phone === "string" ? item.phone : "";
    const org = typeof item.org === "string" ? item.org : "未署名单位";
    const email = typeof item.email === "string" ? item.email : undefined;
    const scope = typeof item.scope === "string" ? item.scope : typeof item.role === "string" ? item.role : "";
    const key = `${org}|${phones}|${email || ""}|${scope}`.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    output.push({
      id: key,
      org,
      scope,
      phone: phones,
      email,
      permission: permission(item.permission),
      redacted: item.redacted === true || phones === "REDACTED" || email === "REDACTED",
    });
  }
  return output;
}

function aircraftLabel(model: string): string {
  const normalized = model.trim().toUpperCase();
  if (normalized === "B787" || normalized === "787") return "B787 / 787 / 梦想客机";
  if (normalized.startsWith("A320")) return `${model} / A320 系列`;
  if (normalized.startsWith("A350")) return `${model} / A350 XWB`;
  return model;
}

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "plan", label: "预案正文" },
  { key: "contacts", label: "联系人" },
  { key: "parts", label: "备件清单" },
  { key: "logistics", label: "物流方案" },
  { key: "warehouse", label: "仓储单位" },
];

export function CityTabs({ city }: { city: City }) {
  const [tab, setTab] = React.useState<TabKey>("plan");
  const available = city.data_available !== false;
  if (!available) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
        <div className="flex items-center gap-2 font-semibold text-amber-900"><ShieldAlert className="h-5 w-5" />数据未审核</div>
        <p className="mt-2 text-sm leading-6 text-amber-800">该航站只展示身份、来源与审核状态。联系人、库存、机型、物流和预案正文在审核通过前全部隐藏。</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-ink-100 bg-white">
      <div className="border-b border-ink-100 px-6"><nav className="-mb-px flex flex-wrap gap-6" aria-label="城市详情">
        {tabs.map((item) => <button key={item.key} type="button" onClick={() => setTab(item.key)} className={cn("border-b-2 py-3.5 text-sm font-medium", tab === item.key ? "border-primary text-primary" : "border-transparent text-ink-500 hover:text-ink-900")}>{item.label}</button>)}
      </nav></div>
      <div className="p-6 sm:p-8">
        {tab === "plan" && <PlanPane city={city} />}
        {tab === "contacts" && <ContactsPane city={city} />}
        {tab === "parts" && <PartsPane city={city} />}
        {tab === "logistics" && <LogisticsPane city={city} />}
        {tab === "warehouse" && <WarehousePane city={city} />}
      </div>
    </div>
  );
}

function PlanPane({ city }: { city: City }) {
  const airport = city.airport_obj;
  return <div className="prose-city max-w-none">
    <h2>机场与城市</h2>
    <table><tbody>
      <tr><th className="w-32 bg-ink-50">城市</th><td>{city.name}</td></tr>
      <tr><th className="bg-ink-50">机场</th><td>{airport?.name || city.airport || "—"}</td></tr>
      <tr><th className="bg-ink-50">三字代码</th><td className="font-mono">{airport?.code || city.iata || "—"}</td></tr>
      <tr><th className="bg-ink-50">省份/地区</th><td>{airport?.province || city.region || "—"}</td></tr>
    </tbody></table>
    <h2>执飞机型</h2>
    {city.fleet?.length ? <table><thead><tr><th>机型</th><th>短停</th><th>航后</th></tr></thead><tbody>{city.fleet.map((item) => <tr key={item.model}><td>{aircraftLabel(item.model)}</td><td>{item.short_stay ? "支持" : "未标注"}</td><td>{item.after ? "支持" : "未标注"}</td></tr>)}</tbody></table> : <p className="text-ink-500">暂无已核验机型数据。</p>}
    <h2>预案正文</h2>
    <div className="whitespace-pre-wrap text-sm leading-7 text-ink-700">{city.content_md || "暂无已核验预案正文。"}</div>
  </div>;
}

function ContactsPane({ city }: { city: City }) {
  const rows = contacts(city);
  if (!rows.length) return <Empty text="暂无已核验联系人。" />;
  return <div><h2 className="text-lg font-semibold text-ink-900">当地及周边资源</h2><p className="mt-1 text-xs text-ink-500">公开联系方式直接展示；内部和受限联系方式由后端脱敏。重复记录已按单位、电话、邮箱和职责去重。</p><div className="mt-4 grid gap-3 sm:grid-cols-2">{rows.map((item) => <div key={item.id} className={cn("rounded-lg border p-4", item.permission === "public" ? "border-ink-100" : "border-amber-200 bg-amber-50/40")}>
    <div className="flex items-center justify-between gap-2"><strong className="text-sm text-ink-900">{item.org}</strong><span className="rounded-full bg-ink-100 px-2 py-0.5 text-[10px] text-ink-700">{item.permission === "public" ? "公开" : item.permission === "internal" ? "内部" : "受限"}</span></div>
    {item.scope && <p className="mt-2 text-xs text-ink-500">{item.scope}</p>}
    {item.redacted || item.permission !== "public" ? <p className="mt-3 flex items-center gap-1 text-xs text-amber-800"><Lock className="h-3 w-3" />联系方式已脱敏</p> : <div className="mt-3 space-y-1 text-sm">{item.phone && <a href={`tel:${item.phone.split(" / ")[0]}`} className="block text-primary hover:underline">{item.phone}</a>}{item.email && <a href={`mailto:${item.email}`} className="block text-primary hover:underline">{item.email}</a>}</div>}
  </div>)}</div></div>;
}

function PartsPane({ city }: { city: City }) {
  if (!city.parts?.length) return <Empty text="暂无已核验备件数据。" />;
  return <div><h2 className="text-lg font-semibold">备件清单</h2><div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="bg-ink-50 text-left"><th className="p-2">名称</th><th className="p-2">件号</th><th className="p-2">库存</th><th className="p-2">位置档位</th></tr></thead><tbody>{city.parts.map((part, index) => <tr key={`${part.pn}-${index}`} className="border-b border-ink-100"><td className="p-2">{part.name}</td><td className="p-2 font-mono">{part.pn}</td><td className="p-2">{part.stock} {part.unit}</td><td className="p-2">{part.stock > 0 ? "本站库存" : "协议求援 / 位置待确认"}</td></tr>)}</tbody></table></div></div>;
}

function LogisticsPane({ city }: { city: City }) {
  const rows = city.logistics ? Object.entries(city.logistics) : [];
  if (!rows.some(([, value]) => value)) return <Empty text="暂无已核验物流方案。" />;
  const labels: Record<string, string> = { rail: "铁路", air: "航空", road: "公路" };
  return <div><h2 className="text-lg font-semibold">物流方案</h2><div className="mt-4 grid gap-3">{rows.map(([key, value]) => value ? <div key={key} className="rounded-lg border border-ink-100 p-4"><strong>{labels[key] || key}</strong><p className="mt-1 text-sm text-ink-600">{value}</p></div> : null)}</div></div>;
}

function WarehousePane({ city }: { city: City }) {
  const location = city.warehouse?.location || city.warehouse_mockup?.address || city.warehouse_mockup?.name;
  if (!location) return <Empty text="暂无已核验仓储单位。" />;
  return <div><h2 className="text-lg font-semibold">仓储单位</h2><div className="mt-4 rounded-lg border border-ink-100 p-4"><p className="font-medium">{location}</p>{city.warehouse?.main?.length ? <p className="mt-2 text-sm text-ink-600">主要保障：{city.warehouse.main.join("、")}</p> : null}</div></div>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-ink-200 bg-ink-50 p-8 text-center text-sm text-ink-500"><Info className="mx-auto mb-2 h-5 w-5" />{text}</div>;
}
