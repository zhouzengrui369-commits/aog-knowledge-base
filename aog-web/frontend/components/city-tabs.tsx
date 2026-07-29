"use client";

import * as React from "react";
import { Lock, ShieldAlert, Info } from "lucide-react";
import { cn, LOGISTICS_ICON, METHOD_COLOR } from "@/lib/utils";
import { getToken } from "./auth-gate";
import type { City, ContactPermission } from "@/lib/types";

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
  const ap = city?.airport_obj;
  return (
    <div className="prose-city max-w-none">
      <h2>一、机场信息</h2>
      <table>
        <tbody>
          <tr>
            <th className="bg-ink-50 w-32">机场名称</th>
            <td>{ap?.name || city?.airport || "—"}</td>
          </tr>
          <tr>
            <th className="bg-ink-50">省份/地区</th>
            <td>{ap?.province || "—"}</td>
          </tr>
          <tr>
            <th className="bg-ink-50">三字代码</th>
            <td className="font-mono">{ap?.code || city?.iata || "—"}</td>
          </tr>
          <tr>
            <th className="bg-ink-50">地区</th>
            <td>{city?.region || "—"}</td>
          </tr>
        </tbody>
      </table>

      <h2>二、吉祥执飞机型</h2>
      {city?.fleet && city.fleet.length > 0 ? (
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
              <tr key={f?.model}>
                <td className="font-medium">{f?.model || "—"}</td>
                <td>{f?.short_stay ? "√" : "×"}</td>
                <td>{f?.after ? "√" : "×"}</td>
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

// D-030: 按 permission 分组的 contacts 渲染
//   - public:     正常显示
//   - internal:   半透明 + "内部" 徽章
//   - restricted: 折叠 + "受限" 徽章 + 未登录显示登录提示
function ContactCard({
  c,
  i,
  isAuthed,
}: {
  c: any;
  i: number;
  isAuthed: boolean;
}) {
  const perm: ContactPermission = (c?.permission as ContactPermission) || "public";
  const isRestricted = perm === "restricted" && !isAuthed;
  // ★ P0-6: 脱敏显示 (Owner 7/29 授权, D-044-E)
  // backend _decode_city 已把 restricted/redacted contact 的 phone/email 替换为 "REDACTED"
  // 前端再 check: 如果 contact 显式标 redacted=true, 显 REDACTED 标
  const isRedacted = !!c?.redacted;

  return (
    <div
      className={cn(
        "rounded-lg border bg-white p-4",
        perm === "internal" && "border-ink-100 opacity-70",
        perm === "restricted" && "border-amber-200",
        isRestricted && "bg-amber-50/50",
        isRedacted && "border-red-200 bg-red-50/40",
      )}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-semibold text-ink-900">{c.org}</div>
        <div className="flex items-center gap-1">
          {c.method && (
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium",
                METHOD_COLOR[c.method] || "bg-ink-100 text-ink-700",
              )}
            >
              {c.method}
            </span>
          )}
          {perm === "internal" && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-ink-100 px-2 py-0.5 text-[10px] font-medium text-ink-700">
              <Info size={10} />
              内部
            </span>
          )}
          {perm === "restricted" && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
              <ShieldAlert size={10} />
              受限
            </span>
          )}
          {/* ★ P0-6: 脱敏标志 (Owner 7/29 授权) */}
          {isRedacted && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-800">
              <ShieldAlert size={10} />
              已脱敏
            </span>
          )}
        </div>
      </div>
      {c.scope && <p className="mb-2 text-xs text-ink-500">{c.scope}</p>}
      {c.contact && (
        <div className="mb-1 text-xs text-ink-700">
          <span className="text-ink-500">联系人：</span>
          {c.contact}
        </div>
      )}
      {/* ★ P0-6: 脱敏或受限 → 不显示 phone/email */}
      {c.phone && !isRestricted && !isRedacted && (
        <div className="mb-1 text-xs text-ink-700">
          <span className="text-ink-500">电话：</span>
          <a href={`tel:${c.phone}`} className="text-primary hover:underline">
            {c.phone}
          </a>
        </div>
      )}
      {c.email && !isRestricted && !isRedacted && (
        <div className="text-xs text-ink-700">
          <span className="text-ink-500">邮箱：</span>
          <a href={`mailto:${c.email}`} className="text-primary hover:underline">
            {c.email}
          </a>
        </div>
      )}
      {/* ★ P0-6: 脱敏/受限 → 占位提示 */}
      {(isRedacted || isRestricted) && (
        <div className="mt-1 text-xs text-ink-400 italic">
          联系方式已脱敏 / 需登录后查看
        </div>
      )}
      {isRestricted && (
        <div className="mt-2 flex items-center gap-1.5 rounded-md bg-amber-100/60 px-2 py-1.5 text-[11px] text-amber-900">
          <Lock size={11} />
          <span>受限供应商联系人 — 需登录后查看完整信息</span>
        </div>
      )}
    </div>
  );
}

function ContactsPane({ city }: { city: City }) {
  // D-030: 受限 contact 需登录 — 检查 token
  const [isAuthed, setIsAuthed] = React.useState(false);
  React.useEffect(() => {
    setIsAuthed(!!getToken());
  }, []);

  // V14: 兼容 SCF 真实 API (city.contacts: Array<{org, phone:string[], role, email, permission}>) + mockup
  const rawContacts =
    (city?.contacts && city.contacts.length > 0
      ? city.contacts.map((c: any) => ({
          org: c?.org,
          scope: c?.role,
          method: c?.role,
          contact: undefined,
          phone: Array.isArray(c?.phone) ? c.phone.join(" / ") : c?.phone,
          email: c?.email,
          permission: c?.permission as ContactPermission | undefined,
        }))
      : null) ||
    city?.contacts_mockup ||
    [];
  if (rawContacts.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-8 text-center text-sm text-ink-500">
        该航站暂无详细联系人信息，建议直接联系 AOG 中心。
      </div>
    );
  }
  // D-030: 按 permission 分组 (public 在前, internal 半透明, restricted 受限)
  const publicContacts = rawContacts.filter(
    (c) => (c.permission || "public") === "public",
  );
  const internalContacts = rawContacts.filter((c) => c.permission === "internal");
  const restrictedContacts = rawContacts.filter((c) => c.permission === "restricted");
  const otherContacts = rawContacts.filter(
    (c) => !["public", "internal", "restricted"].includes(c.permission || "public"),
  );
  // 老 mockup 数据无 permission 字段时, 全部塞 public
  const legacyContacts = otherContacts;

  return (
    <div className="prose-city max-w-none">
      <h2>当地及周边资源</h2>
      <p>当自营航材不足时，可按以下联系方式求援 / 中介 / 互援。</p>
      <p className="text-xs text-ink-500">
        D-030: 联系人按权限分级 — 公开 (航司 desk) / 内部 (库房手机, 半透明) / 受限 (供应商, 需登录)
      </p>

      {publicContacts.length + legacyContacts.length > 0 && (
        <>
          <h3 className="mt-6 text-base font-semibold text-ink-900">公开联系 (航司 desk)</h3>
          <div className="not-prose mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {[...publicContacts, ...legacyContacts].map((c, i) => (
              <ContactCard key={`pub-${i}`} c={c} i={i} isAuthed={isAuthed} />
            ))}
          </div>
        </>
      )}

      {internalContacts.length > 0 && (
        <>
          <h3 className="mt-6 text-base font-semibold text-ink-900">
            内部联系 (库房/负责人)
          </h3>
          <div className="not-prose mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {internalContacts.map((c, i) => (
              <ContactCard key={`int-${i}`} c={c} i={i} isAuthed={isAuthed} />
            ))}
          </div>
        </>
      )}

      {restrictedContacts.length > 0 && (
        <>
          <h3 className="mt-6 text-base font-semibold text-ink-900">
            受限联系 (供应商商务)
          </h3>
          {!isAuthed && (
            <div className="mt-2 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <Lock size={12} />
              <span>受限供应商联系人需登录后查看。密码入口在页面右上角 / 访问被拦截时弹出。</span>
            </div>
          )}
          <div className="not-prose mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {restrictedContacts.map((c, i) => (
              <ContactCard key={`rst-${i}`} c={c} i={i} isAuthed={isAuthed} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function PartsPane({ city }: { city: City }) {
  // V14: 兼容 SCF 真实 API (city.parts) + mockup
  const parts =
    (city?.parts && city.parts.length > 0
      ? city.parts.map((p: any) => ({
          name: p?.name,
          pn: p?.pn,
          stock: (p?.stock ?? 0) > 0,
          note: `${p?.unit || ""} ${p?.name || ""}`.trim(),
        }))
      : null) ||
    city?.parts_mockup ||
    [];
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
  // V14: 兼容 SCF 真实 API (city.logistics: {rail, air, road}) + mockup
  let logs = city?.logistics_mockup || [];
  if (logs.length === 0 && city?.logistics) {
    const lg = city.logistics;
    if (lg.rail) logs.push({ type: "铁路/海运", note: lg.rail });
    if (lg.air) logs.push({ type: "航空", note: lg.air });
    if (lg.road) logs.push({ type: "陆运", note: lg.road });
  }
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
  // V14: 兼容 SCF 真实 API (city.warehouse: {location, main[]}) + mockup
  let w: { name?: string; address?: string; phone?: string; owners?: string } | undefined =
    city?.warehouse_mockup;
  if (!w && city?.warehouse) {
    const wh = city.warehouse;
    w = {
      name: wh?.main?.[0] || wh?.location || "—",
      address: wh?.location,
      phone: undefined,
      owners: wh?.main?.slice(1).join(" / "),
    };
  }
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
