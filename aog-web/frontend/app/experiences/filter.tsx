"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { ExperienceCard } from "@/components/experience-card";
import { cn } from "@/lib/utils";
import type { Experience } from "@/lib/types";

const TOPICS = ["全部", "流程", "规范", "案例", "培训", "技术", "管理"];
const STATUSES = ["全部", "active", "paused", "retired"];

interface Props {
  all: Experience[];
  initialCategory: string;
  initialStatus: string;
  initialQuery: string;
}

export function ExperienceFilter({ all, initialCategory, initialStatus, initialQuery }: Props) {
  const router = useRouter();
  const sp = useSearchParams();
  const [topic, setTopic] = React.useState(initialCategory);
  const [status, setStatus] = React.useState(initialStatus);
  const [q, setQ] = React.useState(initialQuery);

  // Sync URL
  React.useEffect(() => {
    const params = new URLSearchParams();
    if (topic !== "all") params.set("category", topic);
    if (status !== "all") params.set("status", status);
    if (q) params.set("q", q);
    const qs = params.toString();
    router.replace(qs ? `/experiences?${qs}` : "/experiences", { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic, status, q]);

  const filtered = React.useMemo(() => {
    const k = q.trim().toLowerCase();
    return all.filter((e) => {
      if (topic !== "all" && e.category !== topic && e.topic !== topic) return false;
      if (status !== "all" && e.status !== status) return false;
      if (k) {
        const hay = `${e.title} ${e.summary} ${(e.tags || []).join(" ")}`.toLowerCase();
        if (!hay.includes(k)) return false;
      }
      return true;
    });
  }, [all, topic, status, q]);

  return (
    <>
      {/* Filter bar */}
      <div className="mb-6 flex flex-wrap items-center gap-2 rounded-lg border border-ink-100 bg-white p-3 shadow-soft">
        <span className="text-xs font-medium text-ink-500">主题：</span>
        {TOPICS.map((t) => (
          <button
            key={t}
            type="button"
            data-active={topic === (t === "全部" ? "all" : t)}
            data-topic={t === "全部" ? "all" : t}
            onClick={() => setTopic(t === "全部" ? "all" : t)}
            className={cn(
              "topic-pill rounded-full border border-ink-100 bg-white px-3 py-1 text-xs font-medium text-ink-700 transition",
              topic === (t === "全部" ? "all" : t) && "!bg-primary !text-white !border-primary"
            )}
          >
            {t}
          </button>
        ))}
        <span className="mx-2 hidden h-4 w-px bg-ink-100 sm:inline-block" />
        <span className="text-xs font-medium text-ink-500">状态：</span>
        {STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            data-active={status === s}
            onClick={() => setStatus(s)}
            className={cn(
              "topic-pill rounded-full border border-ink-100 bg-white px-3 py-1 text-xs font-medium text-ink-700 transition",
              status === s && "!bg-primary !text-white !border-primary"
            )}
          >
            {s === "all" ? "全部" : s === "active" ? "现行" : s === "paused" ? "暂停" : "已废止"}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <form
            onSubmit={(e) => e.preventDefault()}
            className="relative w-full sm:w-64"
          >
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-500">
              <Search className="h-4 w-4" />
            </span>
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索标题 / 全文关键词"
              className="w-full rounded-md border border-ink-100 bg-white py-1.5 pl-9 pr-3 text-sm placeholder:text-ink-500 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </form>
          <span className="hidden text-xs text-ink-500 sm:inline">
            共 <span className="font-semibold text-ink-700">{filtered.length}</span> 条
          </span>
        </div>
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-ink-100 bg-ink-50 p-10 text-center text-sm text-ink-500">
          没有匹配的经验。试试更宽泛的关键词，或切换主题筛选。
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((e) => (
            <ExperienceCard key={e.id} exp={e} />
          ))}
        </div>
      )}
    </>
  );
}
