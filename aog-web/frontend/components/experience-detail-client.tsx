"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { NavBar } from "@/components/nav-bar";
import { ExperienceToc } from "@/components/experience-toc";
import { ExperienceContentView } from "@/components/experience-content";
import { getExperience } from "@/lib/api";
import { cn, fmtDate, normalizeCategory, normalizeExpStatus, STATUS_LABEL, TOPIC_COLOR } from "@/lib/utils";
import type { Experience, ExperienceContent } from "@/lib/types";

function parseContent(markdown: string): ExperienceContent[] {
  if (!markdown.trim()) return [];
  const output: ExperienceContent[] = [];
  let current: ExperienceContent | null = null;
  for (const line of markdown.split("\n")) {
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      if (current) output.push(current);
      current = { h: heading[2].trim(), type: "p", text: "" };
    } else {
      if (!current) current = { h: "经验正文", type: "p", text: "" };
      current.text = `${current.text || ""}${current.text ? "\n" : ""}${line}`;
    }
  }
  if (current) output.push(current);
  return output.filter((section) => section.h || section.text?.trim());
}

export function ExperienceDetailClient({ id }: { id: string }) {
  const [experience, setExperience] = useState<Experience | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    getExperience(id).then((value) => { if (!cancelled) setExperience(value); });
    return () => { cancelled = true; };
  }, [id]);

  const sections = useMemo(() => parseContent(experience?.content_md || ""), [experience?.content_md]);

  if (experience === undefined) return <><NavBar active="experiences" /><div className="mx-auto max-w-7xl px-4 py-8 text-sm text-ink-500">加载中…</div></>;
  if (experience === null) return <><NavBar active="experiences" /><div className="mx-auto max-w-3xl px-4 py-12"><h1 className="text-xl font-semibold">经验未找到或尚未发布</h1><p className="mt-2 text-sm text-ink-500">空壳经验和内部治理记录不会在生产环境展示。</p><Link href="/experiences" className="mt-4 inline-block text-primary">返回经验列表</Link></div></>;

  const category = normalizeCategory(experience.category);
  const status = STATUS_LABEL[normalizeExpStatus(experience.status)];
  return (
    <>
      <NavBar active="experiences" />
      <header className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-soft">
          <div className="flex gap-2"><span className={cn("rounded px-2 py-0.5 text-xs", TOPIC_COLOR[category] || "bg-ink-100")}>{category}</span><span className={cn("rounded px-2 py-0.5 text-xs", status.cls)}>{status.text}</span></div>
          <h1 className="mt-3 text-2xl font-semibold text-ink-900">{experience.title}</h1>
          {experience.summary && <p className="mt-2 text-sm text-ink-600">{experience.summary}</p>}
          <div className="mt-3 text-xs text-ink-500">最后更新：{fmtDate(experience.updated_at || experience.updated)}</div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8"><div className="grid gap-6 lg:grid-cols-[240px,1fr]"><aside className="hidden lg:block"><ExperienceToc sections={sections} /></aside><article className="rounded-2xl border border-ink-100 bg-white p-6 shadow-soft"><ExperienceContentView sections={sections} /></article></div><Link href="/experiences" className="mt-6 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-primary"><ChevronLeft className="h-3 w-3" />返回经验列表</Link></main>
    </>
  );
}
