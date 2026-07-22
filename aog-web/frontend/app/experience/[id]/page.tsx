import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
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
import type { City } from "@/lib/types";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateStaticParams() {
  // 跟 T2 mockup 里的 featured 经验对齐, 其他经验 client-side 加载
  const featured = [
    "b787-windshield-aog",
    "aog-workflow-r1",
    "exp-001",
    "exp-002",
  ];
  return featured.map((id) => ({ id }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  // Build-time fix: skip API call, use static metadata to avoid 60s page timeout
  // when SCF backend is slow. The actual title is set client-side by ExperienceDetailClient.
  const { id } = await params;
  return { title: `经验详情 · AOG 知识库` };
}

export default async function ExperiencePage({ params }: PageProps) {
  const { id } = await params;
  // 用 1s timeout 拉数据, 失败 fallback to client component
  const exp = await Promise.race([
    getExperience(decodeURIComponent(id)),
    new Promise<null>((r) => setTimeout(() => r(null), 1000)),
  ]).catch(() => null);
  if (!exp) {
    const { ExperienceDetailClient } = await import("@/components/experience-detail-client");
    return <ExperienceDetailClient id={decodeURIComponent(id)} />;
  }

  const all = (await Promise.race([
    getExperiences(),
    new Promise<any[]>((r) => setTimeout(() => r([]), 1000)),
  ]).catch(() => [])) ?? [];
  const relatedIds = exp.related || [];
  let related = all.filter((e) => relatedIds.includes(e.id) && e.id !== exp.id);
  if (related.length < 3) {
    const sameTopic = all.filter(
      (e) => e.id !== exp.id && (e.category === exp.category || e.topic === exp.topic)
    );
    for (const e of sameTopic) {
      if (related.length >= 3) break;
      if (!related.find((r) => r.id === e.id)) related.push(e);
    }
  }
  related = related.slice(0, 3);

  const topic = normalizeCategory(exp.category || exp.topic);
  const st = STATUS_LABEL[normalizeExpStatus(exp.status)];
  const sections = exp.content || [];

  return (
    <>
      <NavBar />
      <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
        <nav className="text-xs text-ink-500">
          <Link href="/" className="hover:text-primary">
            首页
          </Link>
          <span className="mx-1">/</span>
          <Link href="/experiences" className="hover:text-primary">
            保障经验
          </Link>
          <span className="mx-1">/</span>
          <span className="text-ink-700">{exp.title}</span>
        </nav>
        <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-500">
          <span>相关航站：</span>
          <span className="text-ink-400">（build 时跳过）</span>
        </div>
      </div>

      {/* Article header */}
      <section className="mx-auto max-w-7xl px-4 pt-4 sm:px-6 lg:px-8">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-soft">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                TOPIC_COLOR[topic] || "bg-ink-100 text-ink-700"
              )}
            >
              {topic}
            </span>
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
                st.cls
              )}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", st.dot)} />
              {st.text}
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-ink-900 sm:text-3xl">{exp.title}</h1>
          {exp.summary && <p className="mt-2 text-sm text-ink-700">{exp.summary}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-ink-500">
            <span>
              创建 <span className="text-ink-700">{exp.created || "—"}</span>
            </span>
            <span className="text-ink-300">·</span>
            <span>
              更新 <span className="text-ink-700">{fmtDate(exp.updated_at || exp.updated)}</span>
            </span>
            <span className="text-ink-300">·</span>
            <span>
              作者 <span className="text-ink-700">{exp.author || "—"}</span>
            </span>
            <span className="ml-auto flex items-center gap-2">
              <span className="inline-flex cursor-not-allowed items-center gap-1 rounded-md border border-ink-100 bg-white px-2.5 py-1 text-xs font-medium text-ink-700 opacity-60">
                <Download className="h-3 w-3" /> 下载 docx
              </span>
              <a
                href="#chat"
                className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-white shadow-soft hover:bg-primary-700"
              >
                <Bot className="h-3 w-3" /> 问 AI
              </a>
            </span>
          </div>
          {(exp.tags || []).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {exp.tags!.map((t) => (
                <span key={t} className="rounded bg-ink-50 px-2 py-0.5 text-xs text-ink-500">
                  #{t}
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Body grid: content + TOC */}
      <section className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_240px]">
          <article className="rounded-2xl border border-ink-100 bg-white p-6 shadow-soft">
            <ExperienceContentView sections={sections} />
          </article>
          <aside className="hidden lg:block">
            <ExperienceToc sections={sections} />
          </aside>
        </div>
      </section>

      {/* Related experiences */}
      {related.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
          <h2 className="mb-3 text-lg font-semibold text-ink-900">相关经验</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((r) => (
              <ExperienceCard key={r.id} exp={r} />
            ))}
          </div>
        </section>
      )}

      <footer className="border-t border-ink-100 bg-ink-50">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div>© 2026 AOG 知识库 · v0.1.0-frontend</div>
          <div>
            <Link href="/experiences" className="hover:text-ink-900">
              <ChevronLeft className="mr-0.5 inline h-3 w-3" /> 返回经验列表
            </Link>
          </div>
        </div>
      </footer>
    </>
  );
}

async function RelatedCityChips() {
  // 1s timeout race — build 时 SCF cold start 30-60s 会卡 60s page timeout
  const cities = (await Promise.race([
    getCities(),
    new Promise<City[]>((r) => setTimeout(() => r([]), 1000)),
  ]).catch(() => [])) as City[];
  const featured = cities.filter((c) =>
    ["B-北京大兴", "S-上海浦东", "G-广州白云"].includes(c.code)
  );
  return (
    <>
      {featured.map((c) => (
        <Link
          key={c.code}
          href={`/city/${encodeURIComponent(c.code)}`}
          className="rounded-full bg-ink-50 px-2.5 py-1 hover:bg-primary-50 hover:text-primary"
        >
          {c.name}（{c.region}）
        </Link>
      ))}
    </>
  );
}
