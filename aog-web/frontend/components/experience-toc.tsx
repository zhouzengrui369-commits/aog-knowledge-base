"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { slugify } from "@/lib/slugify";
import type { ExperienceContent } from "@/lib/types";

interface Props {
  sections: ExperienceContent[];
}

/** 经验详情 TOC — IntersectionObserver scroll-spy */
export function ExperienceToc({ sections }: Props) {
  const headings = React.useMemo(
    () =>
      sections.map((s) => ({
        h: s.h,
        id: `h-${slugify(s.h)}`,
      })),
    [sections]
  );

  const [active, setActive] = React.useState<string | null>(headings[0]?.id || null);

  React.useEffect(() => {
    if (headings.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setActive(e.target.id);
          }
        }
      },
      { rootMargin: "0px 0px -70% 0px", threshold: 0.1 }
    );
    headings.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [headings]);

  if (headings.length === 0) return null;

  return (
    <div className="sticky top-20 rounded-xl border border-ink-100 bg-ink-50/50 p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">目录</h3>
      <nav className="space-y-1 text-sm">
        {headings.map(({ h, id }) => (
          <a
            key={id}
            href={`#${id}`}
            className={cn(
              "toc-link block rounded px-2 py-1 text-ink-700 hover:bg-white hover:text-primary",
              active === id && "active"
            )}
          >
            {h.replace(/^[一二三四五六七八九十]+、\s*/, "")}
          </a>
        ))}
      </nav>
    </div>
  );
}
