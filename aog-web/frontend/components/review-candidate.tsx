"use client";

import * as React from "react";
import { FileText, Lock, Package, Plane, Route, Warehouse } from "lucide-react";
import type { ReviewCity } from "@/lib/types";

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-ink-200 bg-ink-50 p-5 text-sm text-ink-500">{text}</div>;
}

function ContactRows({ city }: { city: ReviewCity }) {
  const contacts = city.contacts || [];
  if (!contacts.length) return <Empty text="候选来源中没有联系人记录。" />;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {contacts.map((item, index) => {
        const restricted = item.permission !== "public" || item.redacted === true;
        return (
          <div key={`${item.org}-${index}`} className="rounded-lg border border-ink-100 p-4">
            <div className="flex items-center justify-between gap-2">
              <strong className="text-sm">{item.org || "未署名单位"}</strong>
              <span className="rounded bg-ink-100 px-2 py-0.5 text-[10px] text-ink-600">{restricted ? "已脱敏/受限" : "候选公开信息"}</span>
            </div>
            {(item.scope || item.role) && <p className="mt-2 text-xs text-ink-500">{item.scope || item.role}</p>}
            <div className="mt-3 space-y-1 text-xs text-ink-700">
              {restricted ? (
                <div className="flex items-center gap-1 text-amber-800"><Lock className="h-3 w-3" />非公开联系方式保持脱敏</div>
              ) : (
                <>
                  {(item.phone || []).length > 0 && <div>电话候选：{item.phone.join(" / ")}</div>}
                  {item.email && <div>邮箱候选：{item.email}</div>}
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ReviewCandidate({ city }: { city: ReviewCity }) {
  const logistics = Object.entries(city.logistics || {}).filter(([, value]) => Boolean(value));
  return (
    <div className="space-y-6" data-testid="review-candidate-content">
      <section className="rounded-xl border border-ink-100 bg-white p-6">
        <div className="flex items-center gap-2 text-sm font-semibold"><FileText className="h-4 w-4" />候选预案正文</div>
        <div className="mt-4 whitespace-pre-wrap text-sm leading-7 text-ink-700">{city.content_md || "来源存在，但当前没有可读正文。"}</div>
      </section>

      <section className="rounded-xl border border-ink-100 bg-white p-6">
        <div className="flex items-center gap-2 text-sm font-semibold"><Plane className="h-4 w-4" />候选机型</div>
        {city.fleet?.length ? <div className="mt-3 flex flex-wrap gap-2">{city.fleet.map((item) => <span key={item.model} className="rounded bg-ink-50 px-2 py-1 text-xs">{item.model}</span>)}</div> : <div className="mt-3"><Empty text="没有候选机型记录。" /></div>}
      </section>

      <section className="rounded-xl border border-ink-100 bg-white p-6">
        <div className="flex items-center gap-2 text-sm font-semibold"><Package className="h-4 w-4" />候选备件</div>
        {city.parts?.length ? <div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="bg-ink-50 text-left"><th className="p-2">名称</th><th className="p-2">件号</th><th className="p-2">候选库存</th></tr></thead><tbody>{city.parts.map((part, index) => <tr key={`${part.pn}-${index}`} className="border-b border-ink-100"><td className="p-2">{part.name}</td><td className="p-2 font-mono">{part.pn}</td><td className="p-2">{part.stock} {part.unit}</td></tr>)}</tbody></table></div> : <div className="mt-3"><Empty text="没有候选备件记录。" /></div>}
      </section>

      <section className="rounded-xl border border-ink-100 bg-white p-6">
        <div className="mb-4 text-sm font-semibold">候选联系人</div>
        <ContactRows city={city} />
        <p className="mt-3 text-xs text-ink-500">审核模式不提供 tel:/mailto: 操作入口；非公开联系方式继续由后端脱敏。</p>
      </section>

      <section className="rounded-xl border border-ink-100 bg-white p-6">
        <div className="flex items-center gap-2 text-sm font-semibold"><Route className="h-4 w-4" />候选物流</div>
        {logistics.length ? <div className="mt-3 space-y-2">{logistics.map(([key, value]) => <div key={key} className="rounded bg-ink-50 p-3 text-sm"><strong className="mr-2">{key}</strong>{value}</div>)}</div> : <div className="mt-3"><Empty text="没有候选物流记录。" /></div>}
      </section>

      <section className="rounded-xl border border-ink-100 bg-white p-6">
        <div className="flex items-center gap-2 text-sm font-semibold"><Warehouse className="h-4 w-4" />候选仓储</div>
        <p className="mt-3 text-sm text-ink-700">{city.warehouse?.location || "没有候选仓储位置。"}</p>
        {city.warehouse?.main?.length ? <p className="mt-2 text-xs text-ink-500">候选保障：{city.warehouse.main.join("、")}</p> : null}
      </section>
    </div>
  );
}
