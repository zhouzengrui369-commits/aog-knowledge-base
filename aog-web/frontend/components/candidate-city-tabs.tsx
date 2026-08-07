"use client";

import * as React from "react";
import { AlertTriangle, Info, Lock } from "lucide-react";
import type { ReviewCity } from "@/lib/types";

const tabs = [
  ["plan", "预案正文"],
  ["contacts", "联系人"],
  ["parts", "备件清单"],
  ["logistics", "物流方案"],
  ["warehouse", "仓储单位"],
] as const;
type TabKey = (typeof tabs)[number][0];

export function CandidateCityTabs({ city }: { city: ReviewCity }) {
  const [tab, setTab] = React.useState<TabKey>("plan");
  return (
    <div className="overflow-hidden rounded-xl border border-amber-200 bg-white">
      <div className="border-b border-amber-200 bg-amber-50 px-6 py-4 text-sm text-amber-900">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <strong>待核验知识已展开</strong>
            <p className="mt-1 text-xs leading-5">这些内容可以浏览，也可以供 AI 检索并说明“知识库中记载了什么”。当前状态不是 VERIFIED，因此不能当成已确认的执行指令、库存保证或 SLA；实际处置前需要核验。私人和受限联系方式继续脱敏。</p>
          </div>
        </div>
      </div>
      <div className="border-b border-ink-100 px-6">
        <nav className="-mb-px flex flex-wrap gap-6" aria-label="待核验知识详情">
          {tabs.map(([key, label]) => (
            <button key={key} type="button" onClick={() => setTab(key)} className={`border-b-2 py-3.5 text-sm font-medium ${tab === key ? "border-primary text-primary" : "border-transparent text-ink-500 hover:text-ink-900"}`}>{label}</button>
          ))}
        </nav>
      </div>
      <div className="p-6 sm:p-8">
        {tab === "plan" && <Plan city={city} />}
        {tab === "contacts" && <Contacts city={city} />}
        {tab === "parts" && <Parts city={city} />}
        {tab === "logistics" && <Logistics city={city} />}
        {tab === "warehouse" && <Warehouse city={city} />}
      </div>
    </div>
  );
}

function Plan({ city }: { city: ReviewCity }) {
  return <div className="space-y-5">
    <div><h2 className="text-lg font-semibold">预案正文（待核验）</h2><div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-ink-700">{city.content_md || "暂无候选正文。"}</div></div>
    <div><h2 className="text-lg font-semibold">执飞机型（待核验）</h2>{city.fleet?.length ? <div className="mt-3 flex flex-wrap gap-2">{city.fleet.map((item) => <span key={item.model} className="rounded-md bg-ink-50 px-3 py-1.5 text-sm">{item.model}</span>)}</div> : <Empty text="暂无候选机型数据。" />}</div>
  </div>;
}

function Contacts({ city }: { city: ReviewCity }) {
  if (!city.contacts?.length) return <Empty text="暂无可展示联系人；私人和受限联系方式保持脱敏。" />;
  return <div><h2 className="text-lg font-semibold">联系人（候选资料）</h2><p className="mt-1 text-xs text-ink-500">公开联系方式按权限模型展示；内部/受限联系方式不会因为知识可浏览而自动解密。</p><div className="mt-4 grid gap-3 sm:grid-cols-2">{city.contacts.map((item, index) => {
    const restricted = item.permission !== "public" || item.redacted === true || item.phone?.includes("REDACTED");
    return <div key={`${item.org}-${index}`} className="rounded-lg border border-ink-100 p-4"><div className="flex items-center justify-between gap-2"><strong className="text-sm">{item.org || "未署名单位"}</strong><span className="rounded-full bg-ink-100 px-2 py-0.5 text-[10px]">{item.permission === "public" ? "公开" : "受限"}</span></div>{item.scope || item.role ? <p className="mt-2 text-xs text-ink-500">{item.scope || item.role}</p> : null}{restricted ? <p className="mt-3 flex items-center gap-1 text-xs text-amber-800"><Lock className="h-3 w-3" />联系方式已脱敏</p> : <div className="mt-3 text-sm text-ink-700">{item.phone?.length ? <div>{item.phone.join(" / ")}</div> : null}{item.email ? <div>{item.email}</div> : null}</div>}</div>;
  })}</div></div>;
}

function Parts({ city }: { city: ReviewCity }) {
  if (!city.parts?.length) return <Empty text="暂无候选备件数据。" />;
  return <div><h2 className="text-lg font-semibold">备件清单（待核验）</h2><div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="bg-ink-50 text-left"><th className="p-2">名称</th><th className="p-2">件号</th><th className="p-2">记录库存</th><th className="p-2">使用说明</th></tr></thead><tbody>{city.parts.map((part, index) => <tr key={`${part.pn}-${index}`} className="border-b border-ink-100"><td className="p-2">{part.name}</td><td className="p-2 font-mono">{part.pn}</td><td className="p-2">{part.stock} {part.unit}</td><td className="p-2 text-amber-800">候选记录，实际调拨前核验</td></tr>)}</tbody></table></div></div>;
}

function Logistics({ city }: { city: ReviewCity }) {
  const entries = Object.entries(city.logistics || {}).filter(([, value]) => Boolean(value));
  if (!entries.length) return <Empty text="暂无候选物流方案。" />;
  const labels: Record<string, string> = { rail: "铁路", air: "航空", road: "公路" };
  return <div><h2 className="text-lg font-semibold">物流方案（待核验）</h2><div className="mt-4 grid gap-3">{entries.map(([key, value]) => <div key={key} className="rounded-lg border border-ink-100 p-4"><strong>{labels[key] || key}</strong><p className="mt-1 text-sm text-ink-600">{String(value)}</p></div>)}</div></div>;
}

function Warehouse({ city }: { city: ReviewCity }) {
  const location = city.warehouse?.location;
  const main = city.warehouse?.main || [];
  if (!location && !main.length) return <Empty text="暂无候选仓储数据。" />;
  return <div><h2 className="text-lg font-semibold">仓储单位（待核验）</h2><div className="mt-4 rounded-lg border border-ink-100 p-4">{location ? <p className="font-medium">{location}</p> : null}{main.length ? <p className="mt-2 whitespace-pre-wrap text-sm text-ink-600">候选保障：{main.join("、")}</p> : null}<p className="mt-3 text-xs text-amber-800">仓储候选内容已做自由文本联系方式脱敏；实际联络与库存确认前仍需核验。</p></div></div>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-ink-200 bg-ink-50 p-8 text-center text-sm text-ink-500"><Info className="mx-auto mb-2 h-5 w-5" />{text}</div>;
}
