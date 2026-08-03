import Link from "next/link";
import type { Metadata } from "next";
import { ChevronLeft } from "lucide-react";
import { NavBar } from "@/components/nav-bar";
import { ExperienceToc } from "@/components/experience-toc";
import { ExperienceContentView } from "@/components/experience-content";
import { ExperienceCard } from "@/components/experience-card";
import { getExperience, getExperiences } from "@/lib/api";
import { cn, fmtDate, normalizeCategory, normalizeExpStatus, STATUS_LABEL, TOPIC_COLOR } from "@/lib/utils";
import type { ExperienceContent } from "@/lib/types";

interface PageProps { params: Promise<{ id: string }> }

function parseContent(markdown: string): ExperienceContent[] {
  if (!markdown.trim()) return [];
  const sections: ExperienceContent[] = [];
  let current: ExperienceContent | null = null;
  for (const line of markdown.split("\n")) {
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      if (current) sections.push(current);
      current = { h: heading[2].trim(), type: "p", text: "" };
    } else {
      if (!current) current = { h: "经验正文", type: "p", text: "" };
      current.text = `${current.text || ""}${current.text ? "\n" : ""}${line}`;
    }
  }
  if (current) sections.push(current);
  return sections.filter((section) => section.h || section.text?.trim());
}

export async function generateStaticParams() {
  return ["b787-windshield-aog", "aog-workflow-r1", "exp-001", "exp-002"].map((id) => ({ id }));
}

export async function generateMetadata(): Promise<Metadata> {
  return { title: "经验详情 · AOG 知识库" };
}

export default async function ExperiencePage({ params }: PageProps) {
  const { id } = await params;
  const decodedId = decodeURIComponent(id);
  const showDebug = process.env.NEXT_PUBLIC_DEBUG === "true";
  const exp = await Promise.race([
    getExperience(decodedId),
    new Promise<null>((resolve) => setTimeout(() => resolve(null), 1000)),
  ]).catch(() => null);

  if (!exp) {
    const { ExperienceDetailClient } = await import("@/components/experience-detail-client");
    return <ExperienceDetailClient id={decodedId} />;
  }

  const all = (await Promise.race([
    getExperiences(),
    new Promise<never[]>((resolve) => setTimeout(() => resolve([]), 1000)),
  ]).catch(() => [])) || [];
  const relatedIds = exp.related || [];
  let related = all.filter((item) => relatedIds.includes(item.id) && item.id !== exp.id);
  for (const item of all) {
    if (related.length >= 3) break;
    if (item.id !== exp.id && (item.category === exp.category || item.topic === exp.topic) && !related.some((candidate) => candidate.id === item.id)) related.push(item);
  }
  related = related.slice(0, 3);

  const topic = normalizeCategory(exp.category || exp.topic);
  const status = STATUS_LABEL[normalizeExpStatus(exp.status)];
  const sections = exp.content?.length ? exp.content : parseContent(exp.content_md || "");

  return (
    <>
      <NavBar active="experiences" />
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <nav className="text-xs text-ink-500"><Link href="/">首页</Link><span className="mx-1">/</span><Link href="/experiences">保障经验</Link><span className="mx-1">/</span><span>{exp.title}</span></nav>
        {showDebug && <div className="mt-3 rounded-md border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">开发诊断：experience_id={decodedId}；生产构建不显示。</div>}
      </div>
      <section className="mx-auto max-w-7xl px-4 pt-4 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-soft">
          <div className="flex gap-2"><span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", TOPIC_COLOR[topic] || "bg-ink-100")}>{topic}</span><span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", status.cls)}>{status.text}</span></div>
          <h1 className="mt-3 text-2xl font-bold text-ink-900 sm:text-3xl">{exp.title}</h1>
          {exp.summary && <p className="mt-2 text-sm text-ink-700">{exp.summary}</p>}
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-ink-500"><span>更新 {fmtDate(exp.updated_at || exp.updated)}</span>{exp.author && <span>作者 {exp.author}</span>}{exp.source_path && <span>来源 {exp.source_path}</span>}</div>
          {(exp.tags || []).length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{exp.tags.map((tag) => <span key={tag} className="rounded bg-ink-50 px-2 py-0.5 text-xs text-ink-500">#{tag}</span>)}</div>}
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8"><div className="grid gap-6 lg:grid-cols-[1fr_240px]"><article className="rounded-2xl border border-ink-100 bg-white p-6 shadow-soft"><ExperienceContentView sections={sections} /></article><aside className="hidden lg:block"><ExperienceToc sections={sections} /></aside></div></section>
      {related.length > 0 && <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8"><h2 className="mb-3 text-lg font-semibold">相关经验</h2><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{related.map((item) => <ExperienceCard key={item.id} exp={item} />)}</div></section>}
      <footer className="border-t border-ink-100 bg-ink-50"><div className="mx-auto max-w-7xl px-4 py-6 text-xs text-ink-500"><Link href="/experiences"><ChevronLeft className="mr-1 inline h-3 w-3" />返回经验列表</Link></div></footer>
    </>
  );
}
