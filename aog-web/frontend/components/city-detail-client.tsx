"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { NavBar } from "@/components/nav-bar";
import { CityTabs } from "@/components/city-tabs";
import { getCity, getCities } from "@/lib/api";
import { normalizeCityStatus, STATUS_LABEL, cn, fmtDate } from "@/lib/utils";
import {
  Download,
  Bot,
  ChevronLeft,
  AlertTriangle,
  Phone,
  Mail,
  MapPin,
  Clock,
  Building2,
  ChevronRight,
  Package,
  Sparkles,
} from "lucide-react";
import type { City } from "@/lib/types";

/** P0 治本 (D-029, 2026-07-27): 等 NJX 补真 docx 后从此 set 移除 */
const PENDING_CITY_CODES = new Set<string>(["S-上海浦东", "S-上海虹桥"]);

export function CityDetailClient({ code }: { code: string }) {
  const [city, setCity] = useState<City | null | undefined>(undefined);
  const [related, setRelated] = useState<City[]>([]);

  useEffect(() => {
    let cancelled = false;
    // Next.js RSC 把 path segment 二次 encode 传给 client; 二次 decode 拿原始 code
    let normalized = code;
    for (let i = 0; i < 2; i++) {
      try {
        const next = decodeURIComponent(normalized);
        if (next === normalized) break;
        normalized = next;
      } catch {
        break;
      }
    }
    // V8: 容错 - 城市 code 形如 "B-北京大兴" (首字母大写), 但用户可能访问 lowercase
    // 1) 整段尝试 (已经是大写就直接用)
    // 2) lowercase fallback: 拿 "x-西安" 找大写
    // 3) 最终 fallback: 用 name 模糊匹配
    const tryCodes: string[] = [];
    if (normalized.length > 0) {
      const upper = normalized.charAt(0).toUpperCase() + normalized.slice(1);
      tryCodes.push(upper);
      // 如果首字母是 lowercase, 尝试大写化
      if (normalized !== upper) tryCodes.push(upper);
    }
    (async () => {
      let c: City | null = null;
      for (const tc of tryCodes) {
        c = await getCity(tc);
        if (c) break;
      }
      // 最终 fallback: 按 name 模糊匹配
      if (!c) {
        const all = await getCities();
        const normLower = normalized.toLowerCase();
        c =
          all.find((x) => x.code.toLowerCase() === normLower) ||
          all.find((x) => x.name === normalized.slice(2)) || // "x-西安" → "西安"
          all.find((x) => x.name === normalized) ||
          null;
      }
      if (cancelled) return;
      setCity(c);
      if (c) {
        const all = await getCities();
        if (cancelled) return;
        const others = all.filter((x) => x.code !== c!.code);
        const sameRegion = others
          .filter((x) => x.region === c!.region)
          .slice(0, 3);
        const fill = others
          .filter((x) => x.region !== c!.region)
          .slice(0, 3 - sameRegion.length);
        setRelated([...sameRegion, ...fill].slice(0, 3));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  // P0 治本 (D-029, 2026-07-27): S-上海浦东/虹桥 在 02_外战预案/ 目录无真 docx
  //   7/26 PM 误写 stub 已 mavis-trash 清理, UI 直接显示"待补"页
  //   NJX 补真 docx 后从此 PENDING set 移除即可, 走正常 /api/city/{code} 路径
  if (PENDING_CITY_CODES.has(code)) {
    return (
      <>
        <NavBar />
        <div className="mx-auto max-w-3xl px-4 pt-12 sm:px-6 lg:px-8">
          <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-6 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-6 w-6 flex-shrink-0 text-amber-600" />
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-amber-900">
                  预案待补 · {code}
                </h2>
                <p className="mt-2 text-sm leading-6 text-amber-800">
                  该机场的 AOG 应急预案尚未录入。AOG 知识库目前没有 {code.replace(/^[A-Z]-/, "")} 的真实预案数据。
                </p>
                <p className="mt-3 text-sm leading-6 text-amber-700">
                  <strong>为什么待补？</strong>{" "}
                  PM 在 7/26 16:45 误写了一份占位 docx（件号/电话全部由 PM 编造）到{" "}
                  <code className="rounded bg-amber-100 px-1.5 py-0.5 text-xs">
                    AOG知识库/02_外战预案/
                  </code>
                  ，违反 read-only 约束。7/27 上午已清理，并写事故报告到{" "}
                  <code className="rounded bg-amber-100 px-1.5 py-0.5 text-xs">
                    DECISIONS.md D-029
                  </code>
                  。等待 NJX 补真实 docx 后，由 PM 重新跑 build_index。
                </p>
                <p className="mt-3 text-sm leading-6 text-amber-700">
                  <strong>需要支援？</strong>{" "}
                  若您是该机场的航材保障员，请联系 AOG 支援工程师提交真实预案 docx 到{" "}
                  <code className="rounded bg-amber-100 px-1.5 py-0.5 text-xs">
                    AOG知识库/02_外战预案/{code}.docx
                  </code>
                  。
                </p>
              </div>
            </div>
          </div>
          <div className="mt-6">
            <Link
              href="/"
              className="inline-block text-sm text-primary hover:underline"
            >
              ← 返回首页
            </Link>
          </div>
        </div>
      </>
    );
  }

  if (city === undefined) {
    return (
      <>
        <NavBar />
        <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
          <div className="text-sm text-ink-500">加载中…</div>
        </div>
      </>
    );
  }
  if (city === null) {
    return (
      <>
        <NavBar />
        <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
          <div className="text-ink-700">城市未找到</div>
          <Link
            href="/"
            className="mt-2 inline-block text-sm text-primary hover:underline"
          >
            返回首页
          </Link>
        </div>
      </>
    );
  }

  const st = STATUS_LABEL[normalizeCityStatus(city.status)] || {
    cls: "",
    text: city.status,
  };
  // V14: const 计算 try/catch wrap — 防 Frankfurt 等异常 data 触发 client-side exception
  //   - city.contacts[0].phone 是 string[] (SCF API), 不是 string
  //   - 任何字段访问异常 (e.g. city.parts?.length on undefined) 都会被 catch
  //   - 不会让整个 CityDetailClient 崩溃, 报错到 console + 兜底显示错误信息
  let normalized: string;
  let ap: any;
  let partsCount: number;
  let contactsCount: number;
  let firstContact: any;
  let viewCountText: string;
  let fleetCount: number;
  try {
    normalized = normalizeCityStatus(city.status);
    ap = city.airport_obj;
    partsCount =
      city.parts?.length ?? city.parts_mockup?.length ?? 0;
    contactsCount =
      city.contacts?.length ?? city.contacts_mockup?.length ?? 0;
    firstContact = city.contacts?.[0] ?? city.contacts_mockup?.[0];
    // Stat 预计算 — view_count 可能是 null / undefined, toLocaleString 要安全
    viewCountText = (city.view_count ?? 0).toLocaleString();
    fleetCount = city.fleet?.length ?? 0;
  } catch (e) {
    console.error("[CityDetailClient] render compute error:", e);
    return (
      <>
        <NavBar />
        <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
          <div className="rounded-lg border border-warning-200 bg-warning-50 p-6 text-sm text-warning-700">
            <div className="mb-2 font-semibold">数据解析异常</div>
            <div className="text-xs text-warning-600">
              {String(e instanceof Error ? e.message : e)}
            </div>
            <Link
              href="/"
              className="mt-3 inline-block text-sm text-primary hover:underline"
            >
              返回首页
            </Link>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <NavBar />
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <nav className="flex items-center gap-1.5 text-xs text-ink-500">
          <Link href="/" className="hover:text-primary">
            AOG 知识库
          </Link>
          <ChevronRight className="h-3 w-3 text-ink-300" />
          <Link href="/" className="hover:text-primary">
            城市预案
          </Link>
          <ChevronRight className="h-3 w-3 text-ink-300" />
          <span className="text-ink-700">{city.name}</span>
        </nav>
      </div>

      {normalized === "暂停" && (
        <div className="mt-4 border-y border-warning-200 bg-warning-50">
          <div className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-3 text-sm text-warning-700 sm:px-6 lg:px-8">
            <AlertTriangle className="h-4 w-4" />
            <span>
              <strong>该站暂停保障</strong> · 建议参考同地区可替代航站或联系总部协调
            </span>
          </div>
        </div>
      )}

      {/* City hero card */}
      <header className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="rounded-xl border border-ink-100 bg-white p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="mb-2 flex items-center gap-2 text-xs text-ink-500">
                <span className="rounded bg-ink-50 px-1.5 py-0.5 font-mono text-[11px] tracking-wide">
                  {city.iata || "—"}
                </span>
                <span>·</span>
                <span>{city.region}</span>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
                    st.cls
                  )}
                >
                  <span className={cn("h-1.5 w-1.5 rounded-full", st.dot)} />
                  {st.text}
                </span>
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-ink-900 sm:text-4xl">
                {city.name}
              </h1>
              {(ap?.name || city.airport) && (
                <p className="mt-1 text-sm text-ink-500">
                  {ap?.name || city.airport}
                  {ap?.province ? ` · ${ap.province}` : ""}
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-md border border-ink-100 bg-white px-3 py-2 text-sm font-medium text-ink-700 transition hover:border-ink-300 hover:text-ink-900"
              >
                <Bot className="h-4 w-4" />
                AI 问询
              </button>
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-md bg-ink-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-ink-700"
              >
                <Download className="h-4 w-4" />
                下载预案 PDF
              </button>
            </div>
          </div>

          {/* Quick stats row */}
          <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-ink-100 bg-ink-100 sm:grid-cols-4">
            <Stat label="访问次数" value={viewCountText} />
            <Stat label="执飞机型" value={fleetCount} suffix="种" />
            <Stat label="备件项" value={partsCount} suffix="项" />
            <Stat label="联系人" value={contactsCount} suffix="位" />
          </div>
        </div>
      </header>

      {/* Main grid: 2/3 tabs + 1/3 sidebar */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr,300px]">
          {/* Tabs (underline) */}
          <div className="min-w-0">
            <CityTabs city={city} />
          </div>

          {/* Sidebar: key metadata */}
          <aside className="space-y-4">
            {/* 24h 响应 */}
            <div className="rounded-lg border border-ink-100 bg-white p-5">
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-ink-500">
                <Clock className="h-3.5 w-3.5" />
                24h 应急响应
              </div>
              <div className="text-2xl font-semibold tabular-nums text-ink-900">
                ≤ 30
                <span className="ml-1 text-sm font-normal text-ink-500">
                  min 反馈
                </span>
              </div>
              <p className="mt-1.5 text-xs text-ink-500">
                收到 AOG 通知后 30 分钟内首次反馈，4 小时内出保障方案
              </p>
            </div>

            {/* AOG 联系人 */}
            <div className="rounded-lg border border-ink-100 bg-white p-5">
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-ink-500">
                <Phone className="h-3.5 w-3.5" />
                AOG 联系人
              </div>
              {firstContact ? (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-ink-900">
                    {("org" in firstContact && firstContact.org) || "AOG 中心"}
                  </div>
                  {"contact" in firstContact && firstContact.contact && (
                    <div className="text-xs text-ink-500">
                      {firstContact.contact}
                    </div>
                  )}
                  {"phone" in firstContact && firstContact.phone && (
                    <a
                      href={`tel:${Array.isArray(firstContact.phone) ? firstContact.phone[0] : firstContact.phone}`}
                      className="flex items-center gap-1.5 text-sm text-primary hover:underline"
                    >
                      <Phone className="h-3 w-3" />
                      {Array.isArray(firstContact.phone)
                        ? firstContact.phone.join(" / ")
                        : firstContact.phone}
                    </a>
                  )}
                  {"email" in firstContact && firstContact.email && (
                    <a
                      href={`mailto:${firstContact.email}`}
                      className="flex items-center gap-1.5 text-sm text-ink-700 hover:text-primary"
                    >
                      <Mail className="h-3 w-3" />
                      {firstContact.email}
                    </a>
                  )}
                </div>
              ) : (
                <div className="text-sm text-ink-500">请联系 AOG 中心</div>
              )}
            </div>

            {/* 备件位置 */}
            <div className="rounded-lg border border-ink-100 bg-white p-5">
              <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-ink-500">
                <Package className="h-3.5 w-3.5" />
                备件位置
              </div>
              {city.warehouse_mockup?.name ? (
                <div className="space-y-1.5 text-sm">
                  <div className="flex items-start gap-1.5 text-ink-900">
                    <Building2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-500" />
                    <span>{city.warehouse_mockup.name}</span>
                  </div>
                  {city.warehouse_mockup.address && (
                    <div className="flex items-start gap-1.5 text-xs text-ink-500">
                      <MapPin className="mt-0.5 h-3 w-3 shrink-0" />
                      <span>{city.warehouse_mockup.address}</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-sm text-ink-500">该站无独立备件库</div>
              )}
            </div>

            {/* AI 助手入口 */}
            <Link
              href="#chat"
              className="group flex items-center justify-between gap-3 rounded-lg border border-primary-100 bg-primary-50 p-5 transition hover:border-primary"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 text-xs font-medium text-primary-700">
                  <Sparkles className="h-3.5 w-3.5" />
                  AI 知识助手
                </div>
                <p className="mt-1 text-sm text-ink-700">
                  基于 RAG 问答 · 每条回答都附引用
                </p>
              </div>
              <ChevronRight className="h-4 w-4 text-primary transition group-hover:translate-x-0.5" />
            </Link>
          </aside>
        </div>

        {/* Related cities */}
        {related.length > 0 && (
          <section className="mt-10 border-t border-ink-100 pt-8">
            <h3 className="mb-4 text-sm font-medium text-ink-700">相关航站</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {related.map((c) => (
                <Link
                  key={c.code}
                  href={`/city/${encodeURIComponent(c.code)}`}
                  className="group flex items-center justify-between gap-3 rounded-lg border border-ink-100 bg-white p-4 transition hover:border-ink-300"
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ink-900 group-hover:text-primary">
                      {c.name}
                    </div>
                    <div className="mt-0.5 text-xs text-ink-500">
                      {c.region} · {c.iata || "—"}
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-primary" />
                </Link>
              ))}
            </div>
          </section>
        )}

        {city.updated_at && (
          <div className="mt-8 text-center text-xs text-ink-500">
            最后更新 · {fmtDate(city.updated_at)}
          </div>
        )}
        <div className="mt-3 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-primary"
          >
            <ChevronLeft className="h-3 w-3" />
            返回首页
          </Link>
        </div>
      </main>
    </>
  );
}

function Stat({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string | number;
  suffix?: string;
}) {
  return (
    <div className="bg-white p-4">
      <div className="text-2xl font-semibold tabular-nums tracking-tight text-ink-900">
        {value}
        {suffix && (
          <span className="ml-0.5 text-sm font-normal text-ink-500">
            {suffix}
          </span>
        )}
      </div>
      <div className="mt-0.5 text-xs text-ink-500">{label}</div>
    </div>
  );
}
