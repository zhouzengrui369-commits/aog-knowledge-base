"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FileText, Search } from "lucide-react";
import { getExperiences } from "@/lib/api";
import { ExperienceRow } from "@/components/experience-row";
import { cn, fmtDate } from "@/lib/utils";
import type { Experience, ExperienceCategory } from "@/lib/types";

const CATEGORIES: Array<{ key: ExperienceCategory | "all"; label: string }> = [
  { key: "all", label: "全部" },
  { key: "流程", label: "流程" },
  { key: "规范", label: "规范" },
  { key: "案例", label: "案例" },
  { key: "培训", label: "培训" },
  { key: "技术", label: "技术" },
  { key: "管理", label: "管理" },
];

export function ExperiencesListClient() {
  const params = useSearchParams();
  const router = useRouter();
  const query = params.get("q") || "";
  const category = params.get("category") || "all";
  const [list, setList] = useState<Experience[] | null>(null);
  const [search, setSearch] = useState(query);

  useEffect(() => {
    let cancelled = false;
    getExperiences().then((rows) => { if (!cancelled) setList(rows ?? []); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (search === query) return;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(params.toString());
      if (search.trim()) next.set("q", search.trim()); else next.delete("q");
      router.replace(`/experiences?${next.toString()}`, { scroll: false });
    }, 200);
    return () => window.clearTimeout(timer);
  }, [search, query, params, router]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (list || []).filter((item) => {
      if (category !== "all" && item.category !== category && item.topic !== category) return false;
      if (!needle) return true;
      return `${item.title} ${item.summary} ${(item.tags || []).join(" ")}`.toLowerCase().includes(needle);
    });
  }, [list, query, category]);

  const stats = useMemo(() => {
    if (!list) return null;
    const byCategory: Record<string, number> = {};
    for (const item of list) byCategory[item.category || item.topic || "未分类"] = (byCategory[item.category || item.topic || "未分类"] || 0) + 1;
    const latest = list.map((item) => item.updated_at || item.updated).filter(Boolean).sort().pop();
    return { total: list.length, byCategory, latest };
  }, [list]);

  function setCategory(nextCategory: string) {
    const next = new URLSearchParams(params.toString());
    if (nextCategory === "all") next.delete("category"); else next.set("category", nextCategory);
    router.replace(`/experiences?${next.toString()}`, { scroll: false });
  }

  return (
    <main>
      <section className="border-b border-ink-100 bg-gradient-to-b from-ink-50 to-white">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="text-xs font-medium uppercase tracking-wider text-ink-500">Knowledge Base</div>
          <h1 className="mt-1 text-3xl font-semibold text-ink-900 sm:text-4xl">保障经验</h1>
          <p className="mt-2 text-sm text-ink-500">只展示通过内容发布门的真实经验；空壳、导出记录和内部治理记录不会出现在公共列表。</p>
          {stats && <div className="mt-5 flex gap-5 border-t border-ink-100 pt-4 text-xs text-ink-500"><span><strong className="text-ink-900">{stats.total}</strong> 条可发布经验</span>{stats.latest && <span>最近更新 {fmtDate(stats.latest)}</span>}</div>}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[220px,1fr]">
          <aside className="lg:sticky lg:top-20 lg:self-start">
            <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-500">分类</h2>
            <nav className="space-y-1">{CATEGORIES.map((item) => {
              const active = category === item.key || (item.key === "all" && category === "all");
              const count = item.key === "all" ? stats?.total || 0 : stats?.byCategory[item.key] || 0;
              return <button key={item.key} type="button" onClick={() => setCategory(item.key)} className={cn("flex w-full items-center justify-between rounded-md px-3 py-2 text-sm", active ? "bg-primary-50 text-primary" : "text-ink-700 hover:bg-ink-50")}><span>{item.label}</span><span className="text-xs tabular-nums">{count}</span></button>;
            })}</nav>
          </aside>

          <div>
            <div className="mb-5 flex items-center gap-3">
              <div className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-400" /><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索标题、摘要或标签" className="w-full rounded-md border border-ink-100 py-2 pl-9 pr-3 text-sm focus:border-primary focus:outline-none" /></div>
              <span className="text-xs text-ink-500">{list === null ? "加载中" : `${filtered.length} / ${list.length}`}</span>
            </div>
            {list === null ? <Empty text="正在读取真实经验…" /> : filtered.length === 0 ? <Empty text="没有匹配的可发布经验" /> : <ul className="divide-y divide-ink-100 overflow-hidden rounded-xl border border-ink-100 bg-white">{filtered.map((item) => <li key={item.id}><ExperienceRow exp={item} /></li>)}</ul>}
          </div>
        </div>
      </section>
    </main>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-ink-200 bg-ink-50 p-12 text-center"><FileText className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm text-ink-600">{text}</p></div>;
}
