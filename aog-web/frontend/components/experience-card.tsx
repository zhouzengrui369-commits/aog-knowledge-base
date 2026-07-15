import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn, TOPIC_COLOR, fmtDate, normalizeCategory, normalizeExpStatus, STATUS_LABEL } from "@/lib/utils";
import type { Experience } from "@/lib/types";

interface Props {
  exp: Experience;
  className?: string;
}

/** 经验卡片（列表用） */
export function ExperienceCard({ exp, className }: Props) {
  const topic = normalizeCategory(exp.category || exp.topic);
  const st = STATUS_LABEL[normalizeExpStatus(exp.status)];
  return (
    <Link
      href={`/experience/${encodeURIComponent(exp.id)}`}
      className={cn(
        "group flex h-full flex-col rounded-xl border border-ink-100 bg-white p-5 shadow-soft transition hover:border-primary hover:shadow-pop",
        className
      )}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[10px] font-medium",
            TOPIC_COLOR[topic] || "bg-ink-100 text-ink-700"
          )}
        >
          {topic}
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
            st.cls
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", st.dot)} />
          {st.text}
        </span>
      </div>
      <h3 className="text-base font-semibold text-ink-900 group-hover:text-primary">
        {exp.title}
      </h3>
      <p className="mt-1.5 line-clamp-2 text-sm text-ink-500">{exp.summary}</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {(exp.tags || []).slice(0, 3).map((t) => (
          <span key={t} className="rounded bg-ink-50 px-1.5 py-0.5 text-[10px] text-ink-500">
            #{t}
          </span>
        ))}
      </div>
      <div className="mt-auto flex items-center justify-between pt-4 text-[11px] text-ink-500">
        <span>更新 {fmtDate(exp.updated_at || exp.updated)}</span>
        <span className="inline-flex items-center gap-0.5 text-primary group-hover:underline">
          查看详情 <ChevronRight className="h-3 w-3" />
        </span>
      </div>
    </Link>
  );
}
