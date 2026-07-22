"use client";

import * as React from "react";
import { cn, LOGISTICS_ICON, METHOD_COLOR } from "@/lib/utils";
import type { City } from "@/lib/types";

type TabKey = "plan" | "contacts" | "parts" | "logistics" | "warehouse";

const TABS: { key: TabKey; label: string }[] = [
  { key: "plan", label: "预案正文" },
  { key: "contacts", label: "联系人" },
  { key: "parts", label: "备件清单" },
  { key: "logistics", label: "物流方案" },
  { key: "warehouse", label: "仓储单位" },
];

interface Props {
  city: City;
}

/**
 * 城市详情 5-Tab (Vercel / Linear underline 风格)
 *  - active tab 2px primary underline
 *  - tab 内容: .prose-city typography (globals.css 已有)
 */
export function CityTabs({ city }: Props) {
  const [tab, setTab] = React.useState<TabKey>("plan");
  return (
    <div className="rounded-xl border border-ink-100 bg-white">
      <div className="border-b border-ink-100 px-6">
        <nav className="-mb-px flex flex-wrap gap-6" aria-label="Tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                "relative border-b-2 py-3.5 text-sm font-medium transition",
                tab === t.key
                  ? "border-primary text-primary"
                  : "border-transparent text-ink-500 hover:text-ink-900"
              )}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

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
  const ap = city.airport_obj;
  return (
    <div className="prose-city max-w-none">
      <h2>一、机场信息</h2>
      <table>
        <tbody>
          <tr>
            <th className="bg-ink-50 w-32">机场名称</th>
            <td>{ap?.name || city.airport || "—"}</td>
          </tr>
          <tr>
            <th className="bg-ink-50">省份/地区</th>
            <td>{ap?.province || "—"}</td>
          </tr>
          <tr>
            <th className="bg-ink-50">三字代码</th>
            <td className="font-mono">{ap?.code || city.iata || "—"}</td>
          </tr>
          <tr>
            <th className="bg-ink-50">地区</th>
            <td>{city.region}</td>
          </tr>
        </tbody>
      </table>

      <h2>二、吉祥执飞机型</h2>
      {city.fleet && city.fleet.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>机型</th>
              <th>短停</th>
              <th>航后</th>
            </tr>
          </thead>
          <tbody>
            {city.fleet.map((f) => (
              <tr key={f.model}>
                <td className="font-medium">{f.model}</td>
                <td>{f.short_stay ? "√" : "×"}</td>
                <td>{f.after ? "√" : "×"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-ink-500">该航站无详细机队数据，请参考其他基础信息。</p>
      )}

      <h2>三、航材保障预案</h2>
      <p>下表汇总关键航材清单，含件号 / 库存 / 保障方案。</p>
      <p className="text-xs text-ink-500">
        提示：库存为该航站自营库存；× 表示无库存，需协议求援。
      </p>
    </div>
  );
}

function ContactsPane({ city }: { city: City }) {
  const contacts = city.contacts_mockup || [];
  if (contacts.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-8 text-center text-sm text-ink-500">
        该航站暂无详细联系人信息，建议直接联系 AOG 中心。
      </div>
    );
  }
  return (
    <div className="prose-city max-w-none">
      <h2>当地及周边资源</h2>
      <p>当自营航材不足时，可按以下联系方式求援 / 中介 / 互援。</p>
      <div className="not-prose mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {contacts.map((c, i) => (
          <div
            key={i}
            className="rounded-lg border border-ink-100 bg-white p-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <div className="text-sm font-semibold text-ink-900">
                {c.org}
              </div>
              {c.method && (
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-medium",
                    METHOD_COLOR[c.method] || "bg-ink-100 text-ink-700"
                  )}
                >
                  {c.method}
                </span>
              )}
            </div>
            {c.scope && <p className="mb-2 text-xs text-ink-500">{c.scope}</p>}
            {c.contact && (
              <div className="mb-1 text-xs text-ink-700">
                <span className="text-ink-500">联系人：</span>
                {c.contact}
              </div>
            )}
            {c.phone && (
              <div className="mb-1 text-xs text-ink-700">
                <span className="text-ink-500">电话：</span>
                <a
                  href={`tel:${c.phone}`}
                  className="text-primary hover:underline"
                >
                  {c.phone}
                </a>
              </div>
            )}
            {c.email && (
              <div className="text-xs text-ink-700">
                <span className="text-ink-500">邮箱：</span>
                <a
                  href={`mailto:${c.email}`}
                  className="text-primary hover:underline"
                >
                  {c.email}
                </a>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PartsPane({ city }: { city: City }) {
  const parts = city.parts_mockup || [];
  if (parts.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-8 text-center text-sm text-ink-500">
        该航站暂无详细备件清单，请参考其他基础信息。
      </div>
    );
  }
  return (
    <div className="prose-city max-w-none">
      <h2>航材备件清单</h2>
      <div className="not-prose mt-4 overflow-x-auto rounded-lg border border-ink-100">
        <table className="w-full text-sm">
          <thead className="bg-ink-50 text-xs uppercase text-ink-500">
            <tr>
              <th className="px-3 py-2 text-left">名称</th>
              <th className="px-3 py-2 text-left">件号</th>
              <th className="px-3 py-2 text-left">库存</th>
              <th className="px-3 py-2 text-left">保障方案</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {parts.map((p, i) => (
              <tr key={i}>
                <td className="px-3 py-2 font-medium text-ink-900">
                  {p.name}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-ink-700">
                  {p.pn}
                </td>
                <td className="px-3 py-2">
                  {p.stock ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-success-50 px-2 py-0.5 text-[11px] font-medium text-success-700">
                      √ 库存
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-warning-50 px-2 py-0.5 text-[11px] font-medium text-warning-700">
                      × 缺件
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-ink-700">{p.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LogisticsPane({ city }: { city: City }) {
  const logs = city.logistics_mockup || [];
  if (logs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-8 text-center text-sm text-ink-500">
        暂无详细物流方案。
      </div>
    );
  }
  return (
    <div className="prose-city max-w-none">
      <h2>物流方案</h2>
      <p>从其他基地 / 国际件库到本场的主要运输方式与时效参考。</p>
      <div className="not-prose mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {logs.map((l, i) => (
          <div
            key={i}
            className="rounded-lg border border-ink-100 bg-white p-4"
          >
            <div className="mb-1 flex items-center gap-2">
              <span className="text-xl">{LOGISTICS_ICON[l.type] || "📦"}</span>
              <div className="text-sm font-semibold text-ink-900">
                {l.type}
              </div>
            </div>
            <p className="text-xs text-ink-500">{l.note}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function WarehousePane({ city }: { city: City }) {
  const w = city.warehouse_mockup;
  if (!w?.name) {
    return (
      <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-8 text-center text-sm text-ink-500">
        该航站暂无详细仓储单位信息。
      </div>
    );
  }
  return (
    <div className="prose-city max-w-none">
      <h2>仓储单位</h2>
      <div className="not-prose mt-4 rounded-xl border border-ink-100 bg-ink-50 p-5">
        <div className="text-base font-semibold text-ink-900">{w.name}</div>
        {w.address && (
          <div className="mt-1 text-sm text-ink-700">地址：{w.address}</div>
        )}
        {w.phone && (
          <div className="mt-1 text-sm text-ink-700">
            电话：
            <a
              href={`tel:${w.phone}`}
              className="text-primary hover:underline"
            >
              {w.phone}
            </a>
          </div>
        )}
        {w.owners && (
          <div className="mt-1 text-sm text-ink-700">负责人：{w.owners}</div>
        )}
      </div>
    </div>
  );
}
