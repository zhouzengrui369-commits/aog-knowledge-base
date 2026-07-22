import Link from "next/link";
import { ChevronRight, BookOpen } from "lucide-react";
import { cn, TOPIC_COLOR, fmtDate, normalizeCategory, normalizeExpStatus, STATUS_LABEL } from "@/lib/utils";
import type { Experience } from "@/lib/types";

interface Props {
  exp: Experience;
  className?: string;
}

/**
 * 经验列表行 (Vercel / Linear 风格)
 *  - 横向 dense 布局: icon + title + summary + tags + date + chevron
 *  - 不用 grid 卡墙, 一行一条
 */
export function ExperienceRow({ exp, className }: Props) {
  const topic = normalizeCategory(exp.category || exp.topic);
  const st = STATUS_LABEL[normalizeExpStatus(exp.status)];
  return (
    <Link
      href={`/experience/${encodeURIComponent(exp.id)}`}
      className={cn(
        "group flex items-center gap-4 px-5 py-4 transition hover:bg-ink-50/60",
        className
      )}
    >
      {/* Icon (subtle) */}
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-ink-100 text-ink-500 transition group-hover:border-primary group-hover:text-primary">
        <BookOpen className="h-4 w-4" strokeWidth={1.5} />
      </span>

      {/* Main content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <h3 className="truncate text-sm font-semibold text-ink-900 transition group-hover:text-primary">
            {exp.title}
          </h3>
          {exp.tags && exp.tags.length > 0 && (
            <span className="hidden truncate text-xs text-ink-500 sm:inline">
              {exp.tags
                .slice(0, 2)
                .map((t) => `#${t}`)
                .join(" ")}
            </span>
          )}
        </div>
        {exp.summary && (
          <p className="mt-0.5 line-clamp-1 text-xs text-ink-500">
            {exp.summary}
          </p>
        )}
      </div>

      {/* Topic pill */}
      <span
        className={cn(
          "hidden shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium sm:inline-flex",
          TOPIC_COLOR[topic] || "bg-ink-100 text-ink-700"
        )}
      >
        {topic}
      </span>

      {/* Date */}
      <span className="hidden shrink-0 text-xs tabular-nums text-ink-500 lg:inline">
        {fmtDate(exp.updated_at || exp.updated)}
      </span>

      {/* Chevron */}
      <ChevronRight className="h-4 w-4 shrink-0 text-ink-300 transition group-hover:translate-x-0.5 group-hover:text-primary" />
    </Link>
  );
}
