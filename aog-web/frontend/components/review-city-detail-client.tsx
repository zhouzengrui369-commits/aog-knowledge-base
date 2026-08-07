"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, ChevronLeft, FileCheck2, ShieldCheck } from "lucide-react";
import { NavBar } from "@/components/nav-bar";
import { ReviewCandidate } from "@/components/review-candidate";
import { getReviewCity } from "@/lib/review-api";
import type { ReviewCity } from "@/lib/types";

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

function value(value: unknown, fallback = "未记录"): string {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

export function ReviewCityDetailClient({ code }: { code: string }) {
  const [city, setCity] = React.useState<ReviewCity | null | undefined>(undefined);

  React.useEffect(() => {
    let cancelled = false;
    void getReviewCity(decodeCode(code)).then((data) => {
      if (!cancelled) setCity(data);
    });
    return () => { cancelled = true; };
  }, [code]);

  if (city === undefined) return <><NavBar active="review" /><div className="mx-auto max-w-7xl px-4 py-12 text-sm text-ink-500">正在读取候选知识…</div></>;
  if (city === null) return <><NavBar active="review" /><div className="mx-auto max-w-3xl px-4 py-12"><h1 className="text-xl font-semibold">无法读取审核内容</h1><p className="mt-2 text-sm text-ink-500">请确认已登录、本地后端运行正常且该知识记录存在。</p><Link href="/review" className="mt-4 inline-block text-primary hover:underline">返回知识审核</Link></div></>;

  const review = city.review;
  const pending = !review.operational_eligible;

  return (
    <>
      <NavBar active="review" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Link href="/review" className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-primary"><ChevronLeft className="h-3 w-3" />返回知识审核</Link>

        <div className={`mt-5 rounded-xl border p-5 ${pending ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}>
          <div className="flex items-start gap-3">
            {pending ? <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" /> : <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />}
            <div><div className="font-semibold">{pending ? "审核浏览模式：候选内容可读，但不可用于实际处置" : "已核验记录：审核信息可复核"}</div><p className="mt-1 text-sm leading-6">{pending ? "该页面只用于人工核对来源和候选内容。AOG AI 仍不会把它作为 VERIFIED 上下文，R5 也不会在这里修改审核状态。" : "该记录已具备 operational / AI eligibility；本页面仍保持只读。"}</p></div>
          </div>
        </div>

        <header className="mt-6 rounded-2xl border border-ink-100 bg-white p-6 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary"><FileCheck2 className="h-4 w-4" />Review ID · {review.review_id}</div><h1 className="mt-2 text-3xl font-bold text-ink-900">{city.name} <span className="font-mono text-xl text-ink-400">{city.iata || "—"}</span></h1><p className="mt-2 text-sm text-ink-500">{city.code} · {city.region} · 状态 {review.review_status}</p></div>
            <div className="rounded-lg border border-ink-100 bg-ink-50 px-4 py-3 text-right"><div className="text-[11px] text-ink-400">Operational / AI</div><div className={`mt-1 text-sm font-semibold ${review.operational_eligible ? "text-emerald-700" : "text-amber-800"}`}>{review.operational_eligible ? "可用 / 可用" : "不可用 / 不可用"}</div></div>
          </div>

          <div className="mt-6 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">来源</div><div className="mt-1 break-words text-ink-700">{value(review.source_document || review.source_location)}</div></div>
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">版本</div><div className="mt-1 text-ink-700">{value(review.source_version)}</div></div>
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">置信度</div><div className="mt-1 text-ink-700">{review.confidence == null ? "未记录" : `${Math.round(review.confidence * 100)}%`}</div></div>
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">PII 分类</div><div className="mt-1 text-ink-700">{value(review.pii_classification)}</div></div>
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">更新时间</div><div className="mt-1 text-ink-700">{value(review.updated_at)}</div></div>
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">上次审核</div><div className="mt-1 text-ink-700">{value(review.reviewed_at)}</div></div>
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">审核人</div><div className="mt-1 text-ink-700">{value(review.reviewed_by)}</div></div>
            <div className="rounded-lg bg-ink-50 p-3"><div className="text-ink-400">R5 权限</div><div className="mt-1 text-ink-700">只读，不改 verification status</div></div>
          </div>
        </header>

        <div className="mt-6"><ReviewCandidate city={city} /></div>
      </main>
    </>
  );
}
