"use client";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getExperiences } from "@/lib/api";
import { ExperienceRow } from "@/components/experience-row";
import {
  Search,
  ChevronRight,
  Layers,
  Sparkles,
  BookOpen,
  Briefcase,
  Wrench,
  GraduationCap,
  ClipboardList,
  Settings2,
  FileText,
} from "lucide-react";
import { cn, fmtDate } from "@/lib/utils";
import type { Experience, ExperienceCategory } from "@/lib/types";

const CATEGORIES: { key: ExperienceCategory | "all"; label: string; icon: any }[] = [
  { key: "all", label: "全部", icon: Layers },
  { key: "流程", label: "流程", icon: ClipboardList },
  { key: "规范", label: "规范", icon: BookOpen },
  { key: "案例", label: "案例", icon: Briefcase },
  { key: "培训", label: "培训", icon: GraduationCap },
  { key: "技术", label: "技术", icon: Wrench },
  { key: "管理", label: "管理", icon: Settings2 },
];

export function ExperiencesListClient() {
  const sp = useSearchParams();
  const router = useRouter();
  const q = sp.get("q") || "";
  const cat = sp.get("category") || "all";

  const [list, setList] = useState<Experience[] | null>(null);
  const [search, setSearch] = useState(q);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await getExperiences();
      if (cancelled) return;
      setList(data ?? []);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Sync search input to URL (debounce)
  useEffect(() => {
    if (search === q) return;
    const t = setTimeout(() => {
      const params = new URLSearchParams(sp.toString());
      if (search) params.set("q", search);
      else params.delete("q");
      router.replace(`/experiences?${params.toString()}`, { scroll: false });
    }, 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  // Filter (live, client-side)
  const filtered = useMemo(() => {
    if (!list) return [];
    const k = (q || "").trim().toLowerCase();
    return list.filter((e) => {
      if (cat !== "all" && e.category !== cat && e.topic !== cat) return false;
      if (k) {
        const hay = `${e.title} ${e.summary} ${(e.tags || []).join(" ")}`.toLowerCase();
        if (!hay.includes(k)) return false;
      }
      return true;
    });
  }, [list, q, cat]);

  // Stats
  const stats = useMemo(() => {
    if (!list) return null;
    const total = list.length;
    const cats = new Set(list.map((e) => e.category || e.topic).filter(Boolean)).size;
    const latest = list
      .map((e) => e.updated_at || e.updated)
      .filter(Boolean)
      .sort()
      .pop();
    const byCat: Record<string, number> = {};
    for (const e of list) {
      const k = e.category || e.topic || "未分类";
      byCat[k] = (byCat[k] || 0) + 1;
    }
    return { total, cats, latest, byCat };
  }, [list]);

  const setCategory = (next: string) => {
    const params = new URLSearchParams(sp.toString());
    if (next && next !== "all") params.set("category", next);
    else params.delete("category");
    router.replace(`/experiences?${params.toString()}`, { scroll: false });
  };

  return (
    <main>
      {/* Header — 标题 + 统计 bar */}
      <section className="border-b border-ink-100 bg-gradient-to-b from-ink-50 to-white">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
          <div className="mb-1 text-xs font-medium uppercase tracking-wider text-ink-500">
            Knowledge Base
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink-900 sm:text-4xl">
            保障经验
          </h1>
          <p className="mt-2 max-w-xl text-sm text-ink-500">
            实战经验库 · 流程 / 规范 / 案例 / 培训 / 技术 / 管理
          </p>

          {stats && (
            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-ink-100 pt-5 text-xs text-ink-500">
              <span>
                共{" "}
                <span className="font-medium text-ink-900 tabular-nums">
                  {stats.total}
                </span>{" "}
                个经验
              </span>
              <span className="text-ink-300">·</span>
              <span>
                <span className="font-medium text-ink-900 tabular-nums">
                  {stats.cats}
                </span>{" "}
                个类别
              </span>
              {stats.latest && (
                <>
                  <span className="text-ink-300">·</span>
                  <span>
                    最近更新{" "}
                    <span className="font-medium text-ink-900 tabular-nums">
                      {fmtDate(stats.latest)}
                    </span>
                  </span>
                </>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Body: 2-col (sidebar + list) */}
      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[220px,1fr]">
          {/* Sidebar: category filter */}
          <aside className="lg:sticky lg:top-20 lg:self-start">
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-ink-500">
              分类
            </h3>
            <nav className="space-y-0.5">
              {CATEGORIES.map((c) => {
                const count = stats?.byCat[c.label] || 0;
                const active = cat === c.key || (c.key === "all" && cat === "all");
                const Icon = c.icon;
                return (
                  <button
                    key={c.key}
                    type="button"
                    onClick={() => setCategory(c.key as string)}
                    className={cn(
                      "group flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-sm transition",
                      active
                        ? "bg-primary-50 text-primary"
                        : "text-ink-700 hover:bg-ink-50"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        active ? "text-primary" : "text-ink-500"
                      )}
                      strokeWidth={1.5}
                    />
                    <span className="flex-1">{c.label}</span>
                    <span
                      className={cn(
                        "text-xs tabular-nums",
                        active ? "text-primary" : "text-ink-300"
                      )}
                    >
                      {c.key === "all" ? stats?.total ?? 0 : count}
                    </span>
                  </button>
                );
              })}
            </nav>

            <div className="mt-6 rounded-lg border border-ink-100 bg-ink-50/50 p-4">
              <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-ink-700">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                用 AI 总结
              </div>
              <p className="text-xs text-ink-500">
                在对话框中问「B787 风挡怎么处理？」，AI 会综合多个经验回答。
              </p>
            </div>
          </aside>

          {/* Right: search + list */}
          <div>
            {/* Search input */}
            <div className="mb-5 flex items-center gap-3">
              <div className="relative flex-1">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-500">
                  <Search className="h-4 w-4" />
                </span>
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索标题、摘要、标签…"
                  className="block w-full rounded-md border border-ink-100 bg-white py-2 pl-9 pr-3 text-sm placeholder:text-ink-500 focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10"
                />
              </div>
              <div className="shrink-0 text-xs text-ink-500">
                {list === null
                  ? "加载中…"
                  : `${filtered.length} / ${list.length} 条`}
              </div>
            </div>

            {/* List */}
            {list === null ? (
              <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-8 text-center text-sm text-ink-500">
                加载中…
              </div>
            ) : filtered.length === 0 ? (
              <div className="rounded-lg border border-dashed border-ink-100 bg-ink-50 p-12 text-center">
                <FileText className="mx-auto h-8 w-8 text-ink-300" />
                <p className="mt-3 text-sm text-ink-700">没有匹配的经验</p>
                <p className="mt-1 text-xs text-ink-500">
                  试试其他关键词或清空筛选条件
                </p>
              </div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-ink-100 bg-white">
                <ul className="divide-y divide-ink-100">
                  {filtered.map((e) => (
                    <li key={e.id}>
                      <ExperienceRow exp={e} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
