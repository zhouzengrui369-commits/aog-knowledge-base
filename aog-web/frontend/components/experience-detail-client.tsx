"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { NavBar } from "@/components/nav-bar";
import { ExperienceToc } from "@/components/experience-toc";
import { ExperienceContentView } from "@/components/experience-content";
import { getExperience, getExperiences, getCities } from "@/lib/api";
import { ExperienceCard } from "@/components/experience-card";
import {
  normalizeCategory,
  normalizeExpStatus,
  STATUS_LABEL,
  TOPIC_COLOR,
  fmtDate,
  cn,
} from "@/lib/utils";
import { Download, Bot, ChevronLeft, Sparkles } from "lucide-react";
import type { Experience, ExperienceContent } from "@/lib/types";

/** 简化的内容分段 (从 markdown 文本) */
function parseContent(md: string): ExperienceContent[] {
  if (!md) return [];
  const lines = md.split("\n");
  const sections: ExperienceContent[] = [];
  let cur: ExperienceContent | null = null;
  for (const line of lines) {
    const m = line.match(/^(#{2,4})\s+(.+)$/);
    if (m) {
      if (cur) sections.push(cur);
      cur = { h: m[2].trim(), type: "p", text: "" };
    } else if (cur) {
      cur.text = (cur.text || "") + (cur.text ? "\n" : "") + line;
    }
  }
  if (cur) sections.push(cur);
  return sections;
}

export function ExperienceDetailClient({ id }: { id: string }) {
  const [exp, setExp] = useState<Experience | null | undefined>(undefined);
  const [related, setRelated] = useState<Experience[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const e = await getExperience(id);
      if (cancelled) return;
      setExp(e);
      if (e) {
        const all = await getExperiences();
        if (cancelled) return;
        const relatedIds = e.related || [];
        let r = all.filter((x) => relatedIds.includes(x.id) && x.id !== e.id);
        if (r.length < 3) {
          const same = all.filter(
            (x) => x.id !== e.id && (x.category === e.category || x.topic === e.topic)
          );
          for (const x of same) {
            if (r.length < 3 && !r.find((y) => y.id === x.id)) r.push(x);
            if (r.length >= 3) break;
          }
        }
        setRelated(r.slice(0, 3));
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  if (exp === undefined) {
    return (
      <>
        <NavBar active="experiences" />
        <div className="mx-auto max-w-7xl px-4 pt-6 text-ink-500 text-sm">加载中…</div>
      </>
    );
  }
  if (exp === null) {
    return (
      <>
        <NavBar active="experiences" />
        <div className="mx-auto max-w-7xl px-4 pt-6">
          <div className="text-ink-700">经验未找到</div>
          <Link href="/experiences" className="text-sm text-primary hover:underline mt-2 inline-block">
            返回经验列表
          </Link>
        </div>
      </>
    );
  }

  const cat = normalizeCategory(exp.category);
  const st = normalizeExpStatus(exp.status);
  const sections = useMemo(() => parseContent(exp.content_md || ""), [exp.content_md]);

  return (
    <>
      <NavBar active="experiences" />
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <nav className="text-xs text-ink-500">
          <Link href="/" className="hover:text-primary">首页</Link>
          <span className="mx-1">/</span>
          <Link href="/experiences" className="hover:text-primary">保障经验</Link>
          <span className="mx-1">/</span>
          <span className="text-ink-700">{exp.title}</span>
        </nav>
      </div>

      <header className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-ink-900">{exp.title}</h1>
          {exp.summary && <p className="text-sm text-ink-500">{exp.summary}</p>}
          <div className="flex gap-2 flex-wrap items-center">
            <span className={cn("rounded px-2 py-0.5 text-xs", TOPIC_COLOR[cat] || "bg-ink-100 text-ink-700")}>
              {cat}
            </span>
            <span className={cn("rounded px-2 py-0.5 text-xs", STATUS_LABEL[st]?.cls || "")}>
              {STATUS_LABEL[st]?.text || exp.status}
            </span>
            {exp.tags?.map((t) => (
              <span key={t} className="rounded-full bg-surface-2 px-2.5 py-0.5 text-xs text-ink-600">{t}</span>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <aside className="lg:col-span-1">
            <ExperienceToc sections={sections} />
          </aside>
          <article className="lg:col-span-2 prose prose-sm max-w-none">
            <ExperienceContentView sections={sections} />
          </article>
          <aside className="space-y-4">
            <div className="rounded-lg border border-surface-3 bg-white p-4 space-y-2">
              <h3 className="text-sm font-semibold text-ink-800">应急操作</h3>
              <button className="w-full flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm text-white hover:bg-primary-600">
                <Sparkles className="h-4 w-4" />
                AI 问询
              </button>
              <button className="w-full flex items-center justify-center gap-2 rounded-md border border-surface-3 bg-white px-3 py-2 text-sm text-ink-700 hover:bg-surface-2">
                <Download className="h-4 w-4" />
                下载 PDF
              </button>
            </div>
            {related.length > 0 && (
              <div className="rounded-lg border border-surface-3 bg-white p-4 space-y-3">
                <h3 className="text-sm font-semibold text-ink-800">相关经验</h3>
                {related.map((r) => (
                  <Link key={r.id} href={`/experience/${encodeURIComponent(r.id)}`} className="block rounded-md p-2 hover:bg-surface-2">
                    <div className="text-sm font-medium text-ink-800">{r.title}</div>
                    <div className="text-xs text-ink-500">{r.category} · {r.status}</div>
                  </Link>
                ))}
              </div>
            )}
          </aside>
        </div>
        {exp.updated_at && (
          <div className="mt-8 text-xs text-ink-500 text-center">
            最后更新：{fmtDate(exp.updated_at)}
          </div>
        )}
        <div className="mt-4 text-center">
          <Link href="/experiences" className="text-sm text-ink-500 hover:text-primary">
            <ChevronLeft className="mr-0.5 inline h-3 w-3" /> 返回经验列表
          </Link>
        </div>
      </main>
    </>
  );
}
