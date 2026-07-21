"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { getExperiences } from "@/lib/api";
import { ExperienceFilter } from "./filter";
import { normalizeCategory, normalizeExpStatus, STATUS_LABEL, TOPIC_COLOR, fmtDate, cn } from "@/lib/utils";
import type { Experience } from "@/lib/types";

export function ExperiencesListClient() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") || "";
  const category = searchParams.get("category") || "";
  const status = searchParams.get("status") || "";

  const [list, setList] = useState<Experience[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await getExperiences();
      if (cancelled) return;
      let l = data ?? [];
      if (q) l = l.filter((e) => (e.title + e.summary + e.content_md).toLowerCase().includes(q.toLowerCase()));
      if (category) l = l.filter((e) => e.category === category);
      if (status) l = l.filter((e) => e.status === status);
      setList(l);
    })();
    return () => { cancelled = true; };
  }, [q, category, status]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <aside className="lg:col-span-1">
          <ExperienceFilter all={[]} initialCategory="" initialStatus="" initialQuery="" />
        </aside>
        <section className="lg:col-span-3">
          {list === null ? (
            <div className="text-ink-500 text-sm py-8 text-center">加载中…</div>
          ) : list.length === 0 ? (
            <div className="text-ink-500 text-sm py-8 text-center">暂无经验记录</div>
          ) : (
            <div className="space-y-3">
              {list.map((e) => {
                const cat = normalizeCategory(e.category);
                const st = normalizeExpStatus(e.status);
                return (
                  <Link
                    key={e.id}
                    href={`/experience/${encodeURIComponent(e.id)}`}
                    className="block rounded-lg border border-surface-3 bg-white p-4 hover:border-primary-300 hover:shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base font-semibold text-ink-900">{e.title}</h3>
                        {e.summary && <p className="mt-1 text-sm text-ink-600 line-clamp-2">{e.summary}</p>}
                        <div className="mt-2 flex items-center gap-2 flex-wrap">
                          <span className={cn("rounded px-2 py-0.5 text-xs", TOPIC_COLOR[cat] || "bg-ink-100 text-ink-700")}>
                            {cat}
                          </span>
                          <span className={cn("rounded px-2 py-0.5 text-xs", STATUS_LABEL[st]?.cls || "")}>
                            {STATUS_LABEL[st]?.text || e.status}
                          </span>
                          {e.tags?.slice(0, 3).map((t) => (
                            <span key={t} className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-ink-600">{t}</span>
                          ))}
                        </div>
                      </div>
                      <div className="text-right text-xs text-ink-500 shrink-0">
                        {e.updated_at && fmtDate(e.updated_at)}
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
