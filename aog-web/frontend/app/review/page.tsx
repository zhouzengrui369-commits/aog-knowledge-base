"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, Bot, FileSearch, RefreshCw, ShieldCheck } from "lucide-react";
import { NavBar } from "@/components/nav-bar";
import { getReviewCities } from "@/lib/review-api";
import type { ReviewCitySummary, ReviewStatus } from "@/lib/types";

const FILTERS: Array<{ value: "ALL" | ReviewStatus; label: string }> = [
  { value: "ALL", label: "全部待审核" },
  { value: "UNVERIFIED", label: "待核验" },
  { value: "STALE", label: "已过期" },
  { value: "MISSING", label: "缺失" },
  { value: "REDACTED", label: "已脱敏" },
  { value: "FIXTURE", label: "测试数据" },
];

function statusLabel(status: ReviewStatus): string {
  const labels: Record<ReviewStatus, string> = {
    VERIFIED: "已核验",
    UNVERIFIED: "待核验",
    STALE: "已过期",
    MISSING: "缺失",
    FIXTURE: "测试数据",
    REDACTED: "已脱敏",
  };
  return labels[status];
}

export default function ReviewPage() {
  const [items, setItems] = React.useState<ReviewCitySummary[] | null>(null);
  const [failed, setFailed] = React.useState(false);
  const [filter, setFilter] = React.useState<"ALL" | ReviewStatus>("ALL");

  const load = React.useCallback(async () => {
    setFailed(false);
    const data = await getReviewCities();
    if (!data) {
      setFailed(true);
      setItems([]);
      return;
    }
    setItems(data);
  }, []);

  React.useEffect(() => { void load(); }, [load]);

  const visible = (items || []).filter((item) => filter === "ALL" || item.review_status === filter);
  const withContent = visible.filter((item) => item.has_candidate_content).length;
  const operationalReady = visible.filter((item) => item.operational_eligible).length;

  return (
    <>
      <NavBar active="review" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary"><FileSearch className="h-4 w-4" />知识审核</div>
            <h1 className="mt-2 text-3xl font-bold text-ink-900">待审核知识可见、可检索、可核对</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-ink-600">未核验不等于知识不存在。登录后，候选内容可以浏览，也可以供 AI 检索并按来源状态转述；只有 VERIFIED 才能被当成已确认的执行依据。</p>
          </div>
          <button type="button" onClick={() => void load()} className="inline-flex items-center gap-2 rounded-md border border-ink-200 px-3 py-2 text-sm hover:border-primary hover:text-primary"><RefreshCw className="h-4 w-4" />刷新</button>
        </div>

        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <div className="flex items-start gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div><strong>知识可见 / AI 可检索 ≠ 已核验执行依据</strong><p className="mt-1 text-xs leading-5">R5 仍是只读审核浏览，不提供一键批准、批量改状态或数据源写回。AI 可以回答“待核验资料中记载了什么”，但不得把待核验库存、时效、联系人或预案写成已确认指令。非公开联系方式继续脱敏。</p></div></div>
        </div>

        <div className="mt-6 flex flex-wrap gap-2" aria-label="审核状态筛选">
          {FILTERS.map((item) => <button key={item.value} type="button" onClick={() => setFilter(item.value)} className={`rounded-full border px-3 py-1.5 text-xs ${filter === item.value ? "border-primary bg-primary-50 text-primary" : "border-ink-200 bg-white text-ink-600"}`}>{item.label}</button>)}
        </div>

        {items === null && <div className="mt-8 text-sm text-ink-500">正在读取审核队列…</div>}
        {failed && <div className="mt-8 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">审核队列读取失败。请确认已登录且本地后端正在运行，然后重试。</div>}

        {items !== null && !failed && (
          <>
            <div className="mt-6 grid gap-3 sm:grid-cols-4">
              <div className="rounded-lg border border-ink-100 bg-white p-4"><div className="text-xs text-ink-500">当前筛选</div><div className="mt-1 text-2xl font-semibold">{visible.length}</div></div>
              <div className="rounded-lg border border-ink-100 bg-white p-4"><div className="text-xs text-ink-500">有候选正文/结构</div><div className="mt-1 text-2xl font-semibold">{withContent}</div></div>
              <div className="rounded-lg border border-ink-100 bg-white p-4"><div className="text-xs text-ink-500">可供 AI 状态感知检索</div><div className="mt-1 flex items-center gap-2 text-2xl font-semibold"><Bot className="h-5 w-5 text-primary" />{withContent}</div><div className="mt-1 text-[11px] text-ink-400">回答必须携带核验状态</div></div>
              <div className="rounded-lg border border-ink-100 bg-white p-4"><div className="text-xs text-ink-500">已核验执行依据</div><div className="mt-1 flex items-center gap-2 text-2xl font-semibold"><ShieldCheck className="h-5 w-5 text-ink-300" />{operationalReady}</div><div className="mt-1 text-[11px] text-ink-400">待审核队列默认排除 VERIFIED</div></div>
            </div>

            <div className="mt-6 grid gap-3">
              {visible.map((item) => (
                <Link key={item.review_id} href={`/review/city/${encodeURIComponent(item.code)}`} className="rounded-xl border border-ink-100 bg-white p-5 shadow-soft transition hover:border-primary hover:shadow-md">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div><div className="text-lg font-semibold text-ink-900">{item.name} <span className="font-mono text-sm text-ink-400">{item.iata || "—"}</span></div><div className="mt-1 text-xs text-ink-500">{item.code} · {item.region}</div></div>
                    <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">{statusLabel(item.review_status)}</span>
                  </div>
                  <div className="mt-4 grid gap-2 text-xs text-ink-600 sm:grid-cols-3"><div><span className="text-ink-400">来源：</span>{item.source_document || item.source_location || "未记录"}</div><div><span className="text-ink-400">版本：</span>{item.source_version || "未记录"}</div><div><span className="text-ink-400">候选内容：</span>{item.has_candidate_content ? "可阅读 / 可供 AI 检索" : "无正文/结构"}</div></div>
                  <div className="mt-3 text-xs font-medium text-primary">打开只读审核内容 →</div>
                </Link>
              ))}
              {visible.length === 0 && <div className="rounded-lg border border-dashed border-ink-200 p-8 text-center text-sm text-ink-500">当前筛选没有待审核记录。</div>}
            </div>
          </>
        )}
      </main>
    </>
  );
}
